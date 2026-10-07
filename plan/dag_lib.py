# -*- coding: utf-8 -*-
"""El DAG de un proyecto como contrato verificable. Extraído de AQUERONTE (plan/reglas.py y
scripts/generar_estado.py), que es el estándar de oro de los tres repos (2026-10-05).

Stdlib pura y SIN política: lo que es de un proyecto (su hoja, lo que exige cubrir, sus decisiones
congeladas, sus repos hermanos, sus frases de alarma) vive en `plan/dag.json` y llega como `Config`.
Se vendoriza copiándolo; el test de divergencia del repo consumidor vigila que no se edite la copia.

Formato del plan (`plan/plan.json`, generado por el `construir_dag.py` de cada proyecto, nunca a mano):
    {"proyecto", "version_plan", "fecha", "nodos": [...], "degradaciones": {id: motivo}}
    nodo = {id, fase, tipo, titulo, depende_de, entrega, hecho_cuando, cubre, estado, evidencia?, veredicto?}
El estado vive en `registro/nodos.jsonl` (append-only; manda la última línea de cada nodo).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field, fields
from pathlib import Path

VOCABULARIO = {"pendiente", "en_curso", "hecho", "juzgado", "pausado", "bloqueado"}
CERRADO = {"hecho", "juzgado"}                        # juzgado desbloquea sea cual sea el veredicto
AVANZADO = CERRADO | {"en_curso", "bloqueado", "pausado"}   # nada de esto se apoya en lo no cerrado
JUZGABLE = {"corrida", "medicion"}                    # producen lo que un juez mira
CON_RUTA = JUZGABLE | {"eureka", "preinscripcion"}    # su entrega se comprueba en un commit
PROTEGIDO = CON_RUTA                                  # reetiquetarlo o borrarlo exige declararlo
CAMPOS_NODO = {"nodo", "estado", "evidencia", "nota", "fecha", "veredicto"}
FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CITA = re.compile(r"\bD-\d{3}\b")
EXTERNO = re.compile(r"^(?P<repo>[\w.-]+)@(?P<tag>[\w.+-]+)$")
SHA = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(frozen=True)
class Config:
    """La política de UN proyecto. Una clave desconocida en dag.json aborta: un error de tecleo no se ignora."""
    proyecto: str
    hoja: str                                          # la única hoja del DAG (la release final)
    requerido: list = field(default_factory=list)      # lo que algún nodo debe cubrir
    congeladas: list = field(default_factory=list)     # registro, no plan: un nodo abierto no las cita
    externos: dict = field(default_factory=dict)       # REPO -> ruta del clon (nodos `externo`)
    alarma: str = ""                                   # regex: frases que un nodo abierto no puede contener
    eureka: str = r"^E\d+[a-z]?$"
    prefijos_ruta: list = field(default_factory=lambda: ["docs", "plan", "tests", "scripts", "src", "registro",
                                                         "spikes", "inputs", "declaraciones"])
    tipos_con_ruta_abiertos: list = field(default_factory=lambda: ["adaptador"])
    hecho_max: int = 800
    historia_desde: int = 1                            # primera version_plan que lleva `degradaciones`

    @classmethod
    def leer(cls, ruta: Path) -> "Config":
        datos = json.loads(Path(ruta).read_text())
        sobran = set(datos) - {f.name for f in fields(cls)}
        if sobran:
            raise ValueError(f"{ruta}: claves desconocidas {sorted(sobran)}")
        return cls(**datos)

    def ruta_re(self):
        return re.compile(r"(?<![\w~/.])((?:" + "|".join(map(re.escape, self.prefijos_ruta)) +
                          r")/[^\s,;)«»{<…*#]*)")


# ── git, sin heredar GIT_* (un hook que corre esto apuntaría a otro repo) ──────────────────────────
def _git(raiz, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    r = subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True, env=env)
    return r.stdout if r.returncode == 0 else None


def ficheros_del_commit(raiz, sha):
    if not SHA.match(str(sha or "")):
        return None
    salida = _git(raiz, "show", "--format=", "--name-only", sha)
    return None if salida is None else salida.split()


def rutas_de_entrega(entrega, conf=None):
    return [m.rstrip("/.") or m for m in (conf or Config("", "")).ruta_re().findall(entrega)]


def toca(ficheros, ruta):
    return any(f == ruta or f.startswith(ruta.rstrip("/") + "/") for f in ficheros)


# ── estructura ────────────────────────────────────────────────────────────────────────────────
def ancestros(nodos):
    por_id = {x["id"]: x for x in nodos}
    memo: dict = {}

    def de(i, pila=()):
        if i in memo:
            return memo[i]
        if i in pila:
            raise ValueError(f"ciclo: {' → '.join(pila + (i,))}")
        s = set()
        for d in por_id[i]["depende_de"]:
            if d in por_id:
                s |= {d} | de(d, pila + (i,))
        memo[i] = s
        return s
    return {i: de(i) for i in por_id}


def profundidad(nodos):
    por_id = {x["id"]: x for x in nodos}
    memo: dict = {}

    def p(i):
        if i not in memo:
            memo[i] = 1 + max((p(d) for d in por_id[i]["depende_de"]), default=-1)
        return memo[i]
    return {i: p(i) for i in por_id}


def listos(nodos):
    """Pendientes con todas sus dependencias cerradas, los menos profundos primero."""
    por_id = {x["id"]: x for x in nodos}
    prof = profundidad(nodos)
    return sorted((x for x in nodos if x["estado"] == "pendiente"
                   and all(por_id[d]["estado"] in CERRADO for d in x["depende_de"])),
                  key=lambda x: (prof[x["id"]], x["id"]))


# ── nodos que viven en otro repo ──────────────────────────────────────────────────────────────
def _externo(x, conf):
    """Un `externo` cierra sólo si el otro repo tiene el tag y, en ese tag, su registro da el nodo cerrado."""
    m = EXTERNO.match(str(x.get("evidencia", "")))
    destino = x["entrega"].partition("#")[2]
    if not m or m["repo"] not in conf.externos:
        return [f"{x['id']}: evidencia de un externo es REPO@tag con REPO en dag.json/externos"]
    raiz = Path(conf.externos[m["repo"]]).expanduser()
    if _git(raiz, "rev-parse", "-q", "--verify", f"refs/tags/{m['tag']}") is None:
        return [f"{x['id']}: {m['repo']} no tiene el tag {m['tag']}"]
    texto = _git(raiz, "show", f"{m['tag']}:registro/nodos.jsonl") or ""
    ultimo = {}
    for linea in texto.splitlines():
        if linea.strip():
            y = json.loads(linea)
            ultimo[y["nodo"]] = y["estado"]
    if ultimo.get(destino) not in CERRADO:
        return [f"{x['id']}: {destino} no está cerrado en {m['repo']}@{m['tag']} ({ultimo.get(destino)})"]
    return []


# ── las reglas ────────────────────────────────────────────────────────────────────────────────
def validar(nodos, raiz, conf: Config, anterior=None, degradaciones=None) -> list[str]:
    fallos = []
    ids = [x["id"] for x in nodos]
    if len(ids) != len(set(ids)):
        return [f"ids repetidos: {sorted({i for i in ids if ids.count(i) > 1})}"]
    por_id = {x["id"]: x for x in nodos}
    for x in nodos:
        fallos += [f"{x['id']} depende de {d}, que no existe" for d in x["depende_de"] if d not in por_id]
    if fallos:
        return fallos
    try:
        anc = ancestros(nodos)
    except ValueError as e:
        return [str(e)]
    eureka = re.compile(conf.eureka)
    alarma = re.compile(conf.alarma, re.I) if conf.alarma else None
    congeladas = set(conf.congeladas)

    usados = {d for x in nodos for d in x["depende_de"]}
    hojas = sorted(set(por_id) - usados)
    if hojas != [conf.hoja]:
        fallos.append(f"la única hoja debe ser {conf.hoja}: {hojas}")

    for x in nodos:
        i, estado, tipo = x["id"], x["estado"], x["tipo"]
        if estado not in VOCABULARIO:
            fallos.append(f"{i}: estado fuera del vocabulario: {estado}")
        if estado in AVANZADO:
            fallos += [f"{i} está {estado} sobre {d} ({por_id[d]['estado']})"
                       for d in x["depende_de"] if por_id[d]["estado"] not in CERRADO]
        rutas = rutas_de_entrega(x["entrega"], conf)
        if estado not in CERRADO:
            texto = " ".join((x["titulo"], x["entrega"], x["hecho_cuando"]))
            citadas = (set(x["cubre"]) | set(CITA.findall(texto))) & congeladas
            if citadas:
                fallos.append(f"{i} está abierto y cita decisiones congeladas: {sorted(citadas)}")
            if alarma and (m := alarma.search(texto)):
                fallos.append(f"{i} está abierto y cita una frase de alarma: «{m.group(0)}»")
            if len(x["hecho_cuando"]) > conf.hecho_max:
                fallos.append(f"{i}: hecho_cuando de {len(x['hecho_cuando'])} caracteres > {conf.hecho_max}")
            if tipo in conf.tipos_con_ruta_abiertos and not rutas:
                fallos.append(f"{i} es {tipo} abierto y su entrega no nombra ninguna ruta del repo")
        if tipo in CON_RUTA and not rutas:
            fallos.append(f"{i} es {tipo} y su entrega no nombra ninguna ruta del repo")
        if estado == "juzgado" and tipo != "eureka":
            fallos.append(f"{i}: juzgado sólo vale para un eureka")
        if estado == "juzgado" and x.get("veredicto") != f"registro/veredictos.jsonl#{i}":
            fallos.append(f"{i}: juzgado exige `veredicto` = registro/veredictos.jsonl#{i}")
        if estado in CERRADO and tipo == "externo":
            fallos += _externo(x, conf)
        elif estado in CERRADO:
            ficheros = ficheros_del_commit(raiz, x.get("evidencia"))
            if ficheros is None:
                fallos.append(f"{i} está {estado} sin un commit que lo pruebe: {x.get('evidencia')!r}")
            elif rutas and not any(toca(ficheros, r) for r in rutas):
                fallos.append(f"{i}: su evidencia {x['evidencia']} no toca ninguna ruta de su entrega {rutas}")
        if tipo in JUZGABLE and not any(eureka.match(c) for c in x["cubre"]):
            fallos.append(f"{i} es {tipo} y no declara qué eureka alimenta")

    # cada eureka: exactamente una preinscripción; sus juzgables descienden de ella; él depende de uno
    for e in (x for x in nodos if x["tipo"] == "eureka"):
        pre = [x["id"] for x in nodos if x["tipo"] == "preinscripcion" and e["id"] in x["cubre"]]
        if len(pre) != 1:
            fallos.append(f"{e['id']} debe tener exactamente una de sus preinscripciones: {pre}")
            continue
        juz = [x["id"] for x in nodos if x["tipo"] in JUZGABLE and e["id"] in x["cubre"]]
        fallos += [f"{j} alimenta {e['id']} y no desciende de su preinscripción {pre[0]}"
                   for j in juz if pre[0] not in anc[j]]
        if juz and not set(juz) & anc[e["id"]]:
            fallos.append(f"{e['id']} tiene juzgables {juz} y no depende de él")

    # cada release, una revisión adversarial PROPIA: no vale la que ya sirvió a una release anterior
    releases = [x["id"] for x in nodos if x["tipo"] == "release"]
    for r in releases:
        previas = {p for p in releases if p in anc[r]}
        gastadas = set().union(*(anc[p] for p in previas)) if previas else set()
        frescas = {a for a in anc[r] - gastadas if por_id[a]["tipo"] == "revision"}
        if not frescas:
            fallos.append(f"{r} no desciende de ninguna revisión adversarial propia (tipo revision, "
                          f"posterior a {sorted(previas) or 'nada'})")

    cubierto = {c for x in nodos for c in x["cubre"]}
    fallos += [f"nadie cubre {c}" for c in sorted(set(conf.requerido) - congeladas - cubierto)]
    if anterior is not None:
        fallos += comparar(anterior, nodos, degradaciones or {})
    return fallos


def comparar(anterior, nodos, degradaciones) -> list[str]:
    """Un nodo protegido no se borra, no cambia de tipo ni deja de cubrir un eureka sin declararlo."""
    nuevo = {x["id"]: x for x in nodos}
    fallos = []
    for x in anterior:
        i = x["id"]
        if x["tipo"] not in PROTEGIDO or i in degradaciones:
            continue
        if i not in nuevo:
            fallos.append(f"{i} ({x['tipo']}) desapareció: borrado no declarado en degradaciones")
            continue
        y = nuevo[i]
        if y["tipo"] != x["tipo"]:
            fallos.append(f"{i}: {x['tipo']} → {y['tipo']}, degradación no declarada")
        perdidos = {c for c in x["cubre"] if c.startswith("E")} - set(y["cubre"])
        if perdidos:
            fallos.append(f"{i} dejó de cubrir {sorted(perdidos)}")
        if x["tipo"] == "preinscripcion":
            ganados = {c for c in y["cubre"] if c.startswith("E")} - set(x["cubre"])
            if ganados:
                fallos.append(f"{i}: una preinscripción ganó {sorted(ganados)} (se sella una por eureka)")
    return fallos


def versiones_del_plan(raiz, ruta="plan/plan.json"):
    commits = (_git(raiz, "log", "--reverse", "--format=%H", "--", ruta) or "").split()
    return [(c, json.loads(t)) for c in commits if (t := _git(raiz, "show", f"{c}:{ruta}"))]


def validar_historia(versiones, desde=1) -> list[str]:
    """Cada versión commiteada frente a la anterior: no se burla commiteando generador y plan juntos."""
    fallos = []
    for (_, a), (c, b) in zip(versiones, versiones[1:]):
        if b.get("version_plan", 0) < desde:
            continue
        retiradas = set(a.get("degradaciones", {})) - set(b.get("degradaciones", {}))
        if retiradas:
            fallos.append(f"{c[:7]}: retiró degradaciones declaradas {sorted(retiradas)}")
        fallos += [f"{c[:7]}: {f}" for f in comparar(a["nodos"], b["nodos"], b.get("degradaciones", {}))]
    return fallos


# ── registro append-only ──────────────────────────────────────────────────────────────────────
def leer_registro(raiz, nombre="nodos.jsonl"):
    ruta = Path(raiz) / "registro" / nombre
    return [json.loads(x) for x in ruta.read_text().splitlines() if x.strip()] if ruta.exists() else []


def estado_de_nodos(raiz) -> dict:
    """nodo → (estado, evidencia, nota, veredicto); manda la última línea de cada nodo."""
    return {x["nodo"]: (x["estado"], x.get("evidencia"), x.get("nota", ""), x.get("veredicto"))
            for x in leer_registro(raiz)}


def aplicar_registro(nodos, raiz):
    """El plan dice QUÉ; el registro dice EN QUÉ ESTADO. Devuelve copias con el estado del registro."""
    estado = estado_de_nodos(raiz)
    salida = []
    for x in nodos:
        y = dict(x)
        if x["id"] in estado:
            y["estado"], ev, nota, ver = estado[x["id"]]
            y.update({k: v for k, v in (("evidencia", ev), ("nota_estado", nota), ("veredicto", ver)) if v})
        salida.append(y)
    return salida


def validar_registro(raiz, conf: Config | None = None) -> list[str]:
    fallos = []
    try:
        lineas = leer_registro(raiz)
    except json.JSONDecodeError as e:
        return [f"nodos.jsonl: JSON inválido ({e})"]
    for n, x in enumerate(lineas, 1):
        donde = f"nodos.jsonl:{n}"
        fallos += [f"{donde}: campo fuera de esquema {k}" for k in sorted(set(x) - CAMPOS_NODO)]
        if not {"nodo", "estado", "fecha"} <= set(x):
            fallos.append(f"{donde}: faltan nodo, estado o fecha")
            continue
        if x["estado"] not in VOCABULARIO:
            fallos.append(f"{donde}: estado {x['estado']!r} fuera del vocabulario")
        if not FECHA.match(str(x["fecha"])):
            fallos.append(f"{donde}: fecha no es AAAA-MM-DD")
    return fallos


def violaciones_append_only(raiz, carpeta="registro", sufijo=".jsonl", rectificadas=None) -> list[str]:
    """Cada versión commiteada de <carpeta>/*<sufijo>, y el disco, extiende a la anterior sin tocarla.
    Sólo se exime una transición (ruta, commit de 7 cifras) declarada en `rectificadas`, con su motivo."""
    raiz, exentas = Path(raiz), rectificadas or {}
    rutas = set((_git(raiz, "log", "--all", "--format=", "--name-only", "--", f"{carpeta}/") or "").split())
    rutas |= {str(p.relative_to(raiz)) for p in (raiz / carpeta).glob(f"*{sufijo}")}
    fallos = []
    for ruta in sorted(r for r in rutas if r.endswith(sufijo) and Path(r).parent == Path(carpeta)):
        commits = (_git(raiz, "log", "--reverse", "--format=%H", "--", ruta) or "").split()
        versiones = [(c[:7], _git(raiz, "show", f"{c}:{ruta}")) for c in commits]
        disco = raiz / ruta
        versiones.append(("disco", disco.read_text() if disco.exists() else None))
        for (_, antes), (donde, despues) in zip(versiones, versiones[1:]):
            if antes is None or (ruta, donde) in exentas:
                continue
            previas = antes.splitlines()
            if despues is None:
                fallos.append(f"{ruta}: desaparece en {donde}")
            elif despues.splitlines()[:len(previas)] != previas:
                fallos.append(f"{ruta}: una línea ya escrita cambia o desaparece en {donde}")
    return fallos


# ── ESTADO.md ─────────────────────────────────────────────────────────────────────────────────
def estado_md(plan, conf: Config) -> str:
    nodos = plan["nodos"]
    cuenta = {e: sum(x["estado"] == e for x in nodos) for e in sorted(VOCABULARIO)}
    s = [f"# ESTADO de {conf.proyecto}", "",
         "> GENERADO por `dag.py estado` desde `plan/plan.json` y `registro/`. No se edita a mano.", "",
         f"Plan v{plan.get('version_plan')} · {plan.get('fecha')}", "",
         f"## Nodos del plan ({len(nodos)})", "", "| estado | nodos |", "|---|---|"]
    s += [f"| {e} | {n} |" for e, n in cuenta.items() if n]
    s += ["", "## En curso, bloqueados y pausados", ""]
    s += [f"- **{x['id']}** ({x['estado']}) {x['titulo']} — {x.get('nota_estado', '')}"
          for x in nodos if x["estado"] in {"en_curso", "bloqueado", "pausado"}] or ["- ninguno"]
    s += ["", "## Listos", ""]
    s += [f"- **{x['id']}** {x['titulo']}" for x in listos(nodos)] or ["- ninguno"]
    s += ["", "## Hechos y juzgados", "", "| nodo | estado | evidencia | título |", "|---|---|---|---|"]
    s += [f"| {x['id']} | {x['estado']} | `{x.get('evidencia')}` | {x['titulo']} |"
          for x in nodos if x["estado"] in CERRADO]
    return "\n".join(s) + "\n"
