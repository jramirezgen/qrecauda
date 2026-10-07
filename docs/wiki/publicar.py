# -*- coding: utf-8 -*-
"""publicar — lleva los artefactos generados de un repo a la wiki de su proyecto.

Cada artefacto vive en **dos** sitios y ninguno sobra:

| sitio | qué es |
|---|---|
| `<repo>/docs/wiki/` | la **fuente**: el generador, la biblioteca y el artefacto |
| `<vault>/wiki/<PROYECTO>/` | donde de verdad **se abre, se filtra y se anota** |

El vault es la casa del mapa porque Obsidian no abre un `.canvas` que vive en el
sistema de ficheros de WSL. El repo es la casa del generador porque el mapa
**no se edita a mano: se genera**.

⛔ **El defecto que la numeración cierra.** Los dos primeros canvas se
publicaron sueltos en `wiki/ELEMENT/`, mezclados con las notas. Con dos todavía
se distinguen; con ocho, no — y el orden en que hay que leerlos (primero el
pipeline, después el lazo) no está escrito en ninguna parte. Por eso el destino
**no** es el nombre del fichero de origen: se construye de `n` + `titulo` del
manifiesto, y `n` es la única fuente de la numeración.

Tres reglas del vault se vuelven compuerta aquí, no buena intención:

1. **la numeración es densa y única** — `1..N` sin huecos ni repetidos, o no se
   publica: un `03` sin `02` es una pieza perdida, no un orden;
2. **lo que se publica está validado** — la compuerta de legibilidad del canvas
   corre antes de copiar, no después;
3. **una nota nueva se indexa en la misma operación** — la ficha y el índice se
   siembran aquí, pero el eslabón que un humano tiene que poner (la nota puerta
   del proyecto enlazando el índice) **se comprueba y no se falsifica**.

Uso:  python3 docs/wiki/publicar.py [docs/wiki] [--simulacro]
"""
from __future__ import annotations

import json
import shutil
import os
import subprocess
import importlib.util
import sys
from datetime import date
from pathlib import Path

#: La carpeta de este publicador, que es también la de los generadores
#: vendorizados a los que llama. Se nombra una vez: `sys.path` y
#: `_correr_generadores` tienen que mirar exactamente al mismo sitio.
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import wiki_repo_lib as W       # noqa: E402
from canvas_lib import validar   # noqa: E402
from archivar import archivar   # noqa: E402
import generar_incidencias as GI  # noqa: E402

HOY = date.today().isoformat()
EXCLUIR = ("_PRIVADO", "raw", ".git", "node_modules", ".obsidian")

#: El lockfile. El manifiesto guarda la **intención** (qué número, qué
#: procedencia) y se escribe a mano; esto guarda lo **observado** (qué huella se
#: publicó por última vez) y se genera. Separarlos es lo que evita reescribir el
#: fichero que edita una persona en cada corrida — y es el modelo que ya usan
#: `package-lock.json` y `Cargo.lock` por la misma razón.
LOCK = "wiki.lock.json"
PRIMERA_VERSION = 1
"""Un mapa que ya está publicado y nunca se archivó es su versión 1: la que
lleva ahí desde antes de que este archivo existiera."""

#: El valor de `situacion:` que el vocabulario CERRADO de `generar_incidencias`
#: usa para «cerrada» (ver Regla 6 de SKILL.md). La palabra que usa la gente al
#: hablar —«cerrar una incidencia»— y la palabra que el frontmatter acepta
#: —`resuelta`, no `cerrada`— no son la misma, y esta constante es el único
#: sitio donde se tiende ese puente: todo lo demás se llama por su nombre real.
SITUACION_CERRADA = GI.SITUACIONES[3]
assert SITUACION_CERRADA == "resuelta", (
    "el vocabulario de generar_incidencias cambió de orden: revisar el puente")

#: La clave, dentro de `wiki.lock.json`, donde se observa `situacion:` de cada
#: incidencia la última vez que se publicó — sólo si el proyecto activó
#: `git_commit_al_cerrar_incidencia`. Es lo que hace detectable la TRANSICIÓN
#: (no sólo el valor actual): sin un "antes" contra el que comparar, publicar
#: no puede saber si una incidencia YA estaba resuelta o se acaba de cerrar.
CLAVE_INCIDENCIAS = "incidencias"


# --------------------------------------------------------------------------
# Dominio: qué se publica y dónde. Sin E/S, para poder probarlo sin vault.
# --------------------------------------------------------------------------

def nombre_publicado(item: dict, extension: str) -> str:
    return f"{item['n']:02d} — {item['titulo']}{extension}"


def problemas_de_numeracion(items: list[dict], que: str) -> list[str]:
    """`1..N` sin huecos ni repetidos. Un hueco es una pieza perdida."""
    ns = [i["n"] for i in items]
    P = []
    if len(set(ns)) != len(ns):
        P.append(f"{que}: números repetidos {sorted(ns)}")
    if ns and sorted(ns) != list(range(1, len(ns) + 1)):
        P.append(f"{que}: la numeración tiene huecos — {sorted(ns)} "
                 f"debería ser {list(range(1, len(ns) + 1))}")
    if any(n < 1 for n in ns):
        P.append(f"{que}: hay un número menor que 1")
    return P


# --------------------------------------------------------------------------
# Siembra: la ficha de un mapa y el índice de la carpeta
# --------------------------------------------------------------------------

def _lista_yaml(valores) -> str:
    return "[" + ", ".join(valores) + "]"


def ficha_de(item: dict, titular: str, fm: dict) -> str:
    nombre = nombre_publicado(item, "")
    return f"""---
tags: [mapa, canvas, {titular.lower()}]
area: {_lista_yaml(fm["area"])}
tema: {_lista_yaml(fm["tema"])}
creado: {HOY}
actualizado: {HOY}
fuente: "{item['generador']} — el mapa se genera, no se dibuja a mano"
resumen: "{item['mapea']}"
mapa_n: {item['n']}
generador: "{item['generador']}"
---

# {nombre}

{item['mapea'].capitalize()}.

![[{nombre}.canvas]]

## Cómo se regenera

```bash
python3 {item['generador']} docs/wiki/{item['fuente']}
python3 docs/wiki/publicar.py
```

El mapa **no se edita a mano**: si algo está mal dibujado, se arregla el
generador y se vuelve a publicar. Un mapa retocado a mano se desincroniza del
sistema que dibuja, y un mapa desincronizado es peor que ninguno porque se
sigue creyendo.

## Relacionado

- [[00 — Mapas de {titular}]] — todos los mapas, con su número y su orden de lectura
"""


def indice_de_mapas(items: list[dict], titular: str, proyecto: str, fm: dict) -> str:
    filas = "\n".join(
        f"| `{i['n']:02d}` | [[{nombre_publicado(i, '')}]] | {i['mapea']} |"
        for i in sorted(items, key=lambda x: x["n"]))
    return f"""---
tags: [indice, mapa, canvas, {titular.lower()}]
area: {_lista_yaml(fm["area"])}
tema: {_lista_yaml(fm["tema"])}
creado: {HOY}
actualizado: {HOY}
fuente: "docs/wiki/wiki.json — la numeración vive ahí y en ningún otro sitio"
resumen: "Los {len(items)} mapas de {titular}, numerados y en su orden de lectura."
submapa: true
---

# Mapas de {titular}

Los mapas de ingeniería de **{titular}**, en **JSON Canvas** — el formato nativo
de Obsidian. Se leen en el orden del número: el `01` da el sistema entero, y los
siguientes entran en una pieza.

| # | mapa | qué dibuja |
|---|---|---|
{filas}

## Las reglas de esta carpeta

1. **El mapa se genera, no se dibuja.** Cada uno tiene su script en el repo, y
   un test compara el `.canvas` publicado **byte a byte** con lo que ese script
   produce.
2. **El número lo da `docs/wiki/wiki.json`.** Numeración densa: `1..N` sin
   huecos. Renumerar es editar ese fichero y republicar, nunca renombrar aquí.
3. **La ficha acompaña al mapa.** El `.canvas` no tiene frontmatter, así que no
   se puede filtrar ni etiquetar; su ficha `.md` sí, y es donde se anota.
4. **Los huecos se dibujan igual que lo que funciona.** Un mapa que sólo enseña
   las flechas verdes miente sobre el estado del sistema.

## Relacionado

- [[{proyecto}]]
"""


# --------------------------------------------------------------------------
# El estado de un artefacto: quién lo movió desde la última publicación
# --------------------------------------------------------------------------

def _leer_json_lock(origen: Path) -> dict:
    ruta = origen / LOCK
    if not ruta.is_file():
        return {}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {}


def _leer_lock(origen: Path) -> dict:
    return _leer_json_lock(origen).get("adoptado", {})


def _leer_incidencias_lock(origen: Path) -> dict:
    """`{inc: situacion}` tal y como quedó observado la última vez que se
    publicó. Ausente si el proyecto nunca activó
    `git_commit_al_cerrar_incidencia` — no es un fallo, es que nadie lo pidió.
    """
    return _leer_json_lock(origen).get(CLAVE_INCIDENCIAS, {})


def _escribir_lock(origen: Path, adoptado: dict,
                   incidencias: dict | None = None) -> None:
    datos = {
        "_que_es": "GENERADO por publicar.py — no se edita a mano. Por artefacto, "
                   "las huellas canónicas del repo Y de la bóveda tal y como "
                   "quedaron la última vez. Hacen falta las dos: con una sola, "
                   "adoptar una edición manual la dejaba pisable en la corrida "
                   "siguiente, porque «la bóveda está donde la dejamos» se leía "
                   "como «avanzó el generador».",
        "adoptado": dict(sorted(adoptado.items())),
    }
    if incidencias is not None:
        datos["_incidencias"] = ("`situacion:` de cada incidencia, observada la "
                                 "última vez — sólo existe si el proyecto activó "
                                 "`git_commit_al_cerrar_incidencia`. Sin este "
                                 "'antes', publicar no puede distinguir una "
                                 "incidencia que YA estaba resuelta de una que "
                                 "se acaba de cerrar.")
        datos[CLAVE_INCIDENCIAS] = dict(sorted(incidencias.items()))
    (origen / LOCK).write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sellar(adoptado: dict, item: dict, texto_repo: str, destino: Path,
            version: int | None = None) -> bool:
    """Deja escrito dónde quedaron los dos lados. Devuelve si el lock cambió.

    Se llama SIEMPRE que la corrida termina bien para ese artefacto —haya escrito
    o no—, porque lo que el lock registra no es «lo que publiqué» sino «el punto
    desde el que mediré la próxima vez». Sellar sólo al escribir dejaría un
    artefacto adoptado sin punto de partida, y volvería a salir `sin_adoptar`
    en cada corrida.
    """
    h_vault = _huella_en_disco(destino)
    if h_vault is None:
        return False
    previo = adoptado.get(item["fuente"], {})
    nuevo = {"repo": W.huella_de(destino.name, texto_repo),
             "vault": h_vault, "sellado": HOY,
             # La versión NO se declara a mano: sube sola cuando el archivador
             # guardó la anterior. Ver `docs/wiki/archivar.py`.
             "version": version if version is not None
             else previo.get("version", PRIMERA_VERSION)}
    if ((previo.get("repo"), previo.get("vault"), previo.get("version"))
            == (nuevo["repo"], nuevo["vault"], nuevo["version"])):
        return False
    adoptado[item["fuente"]] = nuevo
    return True


def _huella_en_disco(ruta: Path) -> str | None:
    if not ruta.is_file():
        return None
    return W.huella_de(ruta.name, ruta.read_text(encoding="utf-8", errors="ignore"))


def _decidir(item: dict, texto_repo: str, destino: Path, adoptado: dict,
             descartar: frozenset = frozenset()) -> tuple[str, str, bool, bool]:
    """(procedencia, situación, ¿se escribe?, ¿es fallo?) para un artefacto.

    Un manifiesto sin `procedencia` se trata como `generado`: es lo que hacían
    todos los artefactos antes de que esta clave existiera, y cambiar el
    comportamiento por omisión sería romper lo que ya funcionaba.

    `descartar` es el equivalente de `git checkout -- <ruta>`: el usuario mira
    la divergencia, decide que manda el generador, y **nombra** el artefacto. No
    hay forma global de hacerlo, a diferencia de `--adoptar`: adoptar no destruye
    nada y descartar sí.
    """
    procedencia = item.get("procedencia", W.GENERADO)
    previo = adoptado.get(item["fuente"], {})
    h_repo = W.huella_de(destino.name, texto_repo)
    situacion = W.situacion(h_repo, _huella_en_disco(destino),
                            previo.get("repo"), previo.get("vault"))
    if procedencia == W.MANUAL:
        if item["fuente"] in descartar:
            # No hay generador que pueda mandar: no existe versión a la que
            # volver, así que descartar sólo borraría trabajo sin restaurar nada.
            print(f"✗ {item['fuente']}: es `manual` — no se puede descartar lo "
                  f"que ningún generador produce.")
            print("   Si de verdad quieres empezarlo de cero, bórralo tú desde "
                  "Obsidian; el sistema no borra lo que no sabe rehacer.")
            return procedencia, situacion, False, True
        # No es un fallo que difiera: es de quien lo dibujó. Sólo se numera, se
        # le pone ficha y se indexa.
        return procedencia, situacion, False, False
    if item["fuente"] in descartar:
        return procedencia, situacion, True, False
    return (procedencia, situacion,
            W.se_publica(procedencia, situacion),
            situacion in W.PROBLEMATICAS)


def _correr_generadores(bases, origen: Path, simulacro: bool) -> int:
    """Corre el generador que cada Base declara. Devuelve cuántos fallaron.

    El generador se busca **junto a este publicador**, no en `origen`: los tres
    viven vendorizados en la misma carpeta y con el mismo `main(argv)`, y a
    `origen` sólo se le pide el manifiesto. Así una bóveda de juguete —o un
    proyecto cuyo `docs/wiki/` es un enlace— usa la copia que le corresponde.

    Un `generador` declarado que no existe **es un fallo**, no un aviso: el
    manifiesto estaría prometiendo un índice que nadie puede escribir.
    """
    fallos = 0
    for item in sorted(bases, key=lambda x: x["n"]):
        declarado = item.get("generador")
        if not declarado:
            continue
        modulo = AQUI / f"{Path(declarado).stem}.py"
        if not modulo.is_file():
            print(f"  ✗ {item['fuente']} declara `{declarado}` y aquí no hay "
                  f"ningún {modulo.name}: el índice de esa Base no lo puede "
                  f"escribir nadie.")
            fallos += 1
            continue
        spec = importlib.util.spec_from_file_location(modulo.stem, modulo)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fallos += mod.main([str(origen)] + (["--simulacro"] if simulacro else []))
    return fallos


def _explicar_negativa(nombre: str, situacion: str, generador: str,
                       fuente: str) -> None:
    print(f"✗ {nombre}: {situacion} — {W.EXPLICACION.get(situacion, '')}")
    print("   La bóveda NO se ha tocado. Tres salidas, y hay que elegir una:")
    print(f"     · llevar el cambio al generador ({generador}) y republicar")
    print("     · adoptarlo tal cual:  python3 docs/wiki/publicar.py --adoptar")
    print("     · descartarlo:         borrar el fichero de la bóveda y republicar")


# --------------------------------------------------------------------------
# Regla 6: commit automático al cerrar una incidencia
#
# Ver SKILL.md — Regla 6. Activado por proyecto con
# `git_commit_al_cerrar_incidencia: true` en `wiki.json` (por defecto `false`:
# un proyecto que ya usa esta skill no ve cambiar su comportamiento porque la
# skill aprendió una capacidad nueva).
#
# Lo que esto NO hace, a propósito — alcance acotado, igual que Alejandría en
# la Regla 5: no crea una rama por incidencia ni abre un Pull Request. Es sólo
# el commit. Queda anotado como pendiente, no como resuelto.
# --------------------------------------------------------------------------

def _carpeta_incidencias(raiz_proyecto: Path, manifiesto: dict) -> Path | None:
    especifica = manifiesto["estructura"].get("incidencias")
    return raiz_proyecto / especifica if especifica else None


def _incidencias_actuales(carpeta: Path, titular: str) -> dict[str, dict]:
    """`{inc: {"situacion":…, "ruta":…, "fm":…}}` tal y como están HOY en la
    bóveda. Las incidencias son notas manuales (Regla 2): publicar nunca las
    escribe, sólo las lee para saber si alguna cambió de `situacion`.
    """
    if not carpeta.is_dir():
        return {}
    salida: dict[str, dict] = {}
    for ruta, fm in GI.leer(carpeta, titular):
        ident = str(fm.get("inc") or "")
        if ident:
            salida[ident] = {"ruta": ruta, "situacion": fm.get("situacion"),
                              "fm": fm}
    return salida


def _recien_cerradas(actuales: dict[str, dict], anteriores: dict) -> list[tuple[str, dict]]:
    """Las que HOY están `resuelta` y la última publicación no las vio así.

    Una incidencia nueva que nace ya `resuelta` también cuenta: `anteriores`
    no la conocía, así que para este sistema el cierre ocurrió ahora — que es
    justo lo que hay que commitear.
    """
    return [(ident, info) for ident, info in actuales.items()
            if info["situacion"] == SITUACION_CERRADA
            and anteriores.get(ident) != SITUACION_CERRADA]


def _titulo_corto(ruta: Path, tope: int = 60) -> str:
    """El título de una incidencia sin su prefijo `INC-###`, para el commit.

    El vault nombra el fichero `INC-009 — Título`, así que el título es lo que
    va después del guion largo. Sin ese separador (una incidencia mal
    nombrada, o el nombre del fichero en un caso de prueba) se usa el nombre
    entero antes que dejar el mensaje sin nada que decir.
    """
    stem = ruta.stem
    titulo = stem.split(" — ", 1)[1].strip() if " — " in stem else stem
    return titulo if len(titulo) <= tope else titulo[:tope - 1].rstrip() + "…"


def _mensaje_de_cierre(cerradas: list[tuple[str, dict]],
                       hay_base_de_incidencias: bool) -> str:
    """`wiki: cierra INC-009 (título corto) — regenera mapa N y base de
    incidencias`. Con varias a la vez, se listan todas y los mapas se
    deduplican y se ordenan — un commit, no uno por incidencia, porque el
    `.base` del tablero y `wiki.lock.json` los tocan todas igual.
    """
    refs = [f"{ident} ({_titulo_corto(info['ruta'])})" for ident, info in cerradas]
    ns_mapas = sorted({info["fm"].get("mapa_n") for _, info in cerradas
                       if info["fm"].get("mapa_n")})
    partes = [f"mapa {n}" for n in ns_mapas]
    if hay_base_de_incidencias:
        partes.append("base de incidencias")
    cuerpo = " y ".join(partes) if partes else "el tablero de incidencias"
    return f"wiki: cierra {', '.join(refs)} — regenera {cuerpo}"


def _rutas_a_commitear(origen: Path, cerradas: list[tuple[str, dict]],
                       mapas: list[dict], bases: list[dict],
                       titular_inc: str) -> list[Path]:
    """Lo que el commit lleva DENTRO del repo de código.

    ⛔ **Lo que se queda fuera, a propósito.** La nota de la incidencia vive
    sólo en la bóveda (Regla 2: se edita a mano, ahí, y nunca se duplica al
    repo) — el repo de código no tiene working tree sobre `/mnt/f/OBSIDIAN`,
    así que no hay fichero que darle a `git add`. El commit la referencia por
    `INC-###` y título en el mensaje; no puede llevar su contenido. Es la
    misma clase de límite que la Regla 5 declaró para Alejandría: una cosa que
    esta capacidad NO hace, dicha, no callada.
    """
    rutas = {origen / LOCK}
    ns_mapas = {info["fm"].get("mapa_n") for _, info in cerradas
               if info["fm"].get("mapa_n")}
    for m in mapas:
        if m["n"] in ns_mapas:
            rutas.add(origen / m["fuente"])
    for b in bases:
        if b.get("titulo") == f"Incidencias de {titular_inc}":
            rutas.add(origen / b["fuente"])
    return sorted(p for p in rutas if p.is_file())


def _coautoria(manifiesto: dict) -> str | None:
    """Quién firma como coautor el commit del cierre, o `None` si nadie lo dijo.

    Sale de `coautoria_commit` en `wiki.json` y, si falta, de la variable de
    entorno `WIKI_COAUTORIA`. **Nunca de una constante**: la primera versión
    llevaba el nombre de un modelo concreto escrito aquí, y esa firma se habría estampado en
    los commits de un proyecto trabajado con otro modelo — una atribución falsa
    en la historia de git, que es justo lo que no se puede corregir después.
    Sin ninguna de las dos, el commit sale sin trailer: callar es mejor que
    inventar quién firmó.
    """
    valor = manifiesto.get("coautoria_commit") or os.environ.get("WIKI_COAUTORIA")
    return valor.strip() if valor and valor.strip() else None


def _commit_por_cierre(origen: Path, cerradas: list[tuple[str, dict]],
                       mapas: list[dict], bases: list[dict],
                       titular_inc: str, coautoria: str | None = None) -> None:
    try:
        resultado = subprocess.run(
            ["git", "-C", str(origen), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"  ⚠ cierre detectado pero no se pudo ubicar el repo de git: {e}")
        return
    repo = Path(resultado.stdout.strip())

    rutas = _rutas_a_commitear(origen, cerradas, mapas, bases, titular_inc)
    if not rutas:
        return
    hay_base = any(r.name.endswith(".base") for r in rutas)
    mensaje = _mensaje_de_cierre(cerradas, hay_base)
    if coautoria:
        mensaje += f"\n\nCo-Authored-By: {coautoria}\n"

    subprocess.run(["git", "-C", str(repo), "add", "--"]
                  + [str(p) for p in rutas], check=True)
    # `-- <rutas>`: el commit lleva SÓLO lo que la publicación tocó. Sin la
    # lista, `git commit` se lleva todo lo que haya en el índice — incluido lo
    # que alguien dejó preparado para otro commit —, y lo firma como un cierre.
    hecho = subprocess.run(["git", "-C", str(repo), "commit", "-m", mensaje, "--"]
                          + [str(p) for p in rutas],
                          capture_output=True, text=True)
    if hecho.returncode != 0:
        # Nada que commitear no es un fallo de publicar: puede que un commit
        # anterior ya llevara exactamente este contenido.
        if "nothing to commit" not in hecho.stdout:
            print(f"  ⚠ git commit del cierre no se pudo hacer: "
                 f"{hecho.stdout.strip()} {hecho.stderr.strip()}")
        return
    for ident, _ in cerradas:
        print(f"  ✓ commit automático: cierra {ident}")


# --------------------------------------------------------------------------
# Publicación
# --------------------------------------------------------------------------

def publicar(origen: Path, simulacro: bool = False, adoptar: bool = False,
             descartar=()) -> int:
    manifiesto = json.loads((origen / "wiki.json").read_text(encoding="utf-8"))
    proyecto = manifiesto["proyecto"]
    vault = Path(manifiesto["vault"])
    raiz_proyecto = vault / "wiki" / proyecto
    mapas = manifiesto.get("mapas", [])
    bases = manifiesto.get("bases", [])

    if not vault.is_dir():
        print(f"✗ el vault no está montado: {vault}")
        print("  en WSL:  sudo mount -t drvfs F: /mnt/f")
        return 2

    problemas = (problemas_de_numeracion(mapas, "mapas")
                 + problemas_de_numeracion(bases, "bases"))
    if problemas:
        for p in problemas:
            print(f"✗ {p}")
        return 1

    titular = manifiesto["estructura"].get("mapas_de", proyecto)
    fm = manifiesto["frontmatter"]
    dir_mapas = raiz_proyecto / manifiesto["estructura"]["mapas"]
    dir_bases = raiz_proyecto / manifiesto["estructura"]["bases"]
    # Dónde se archivan las versiones SÍ es dato del proyecto (a diferencia del
    # número, que es generado). Si no está declarado, cuelga de los mapas.
    dir_versiones = raiz_proyecto / manifiesto["estructura"].get(
        "versiones", manifiesto["estructura"]["mapas"] + "/Versiones")
    marca = " · simulacro" if simulacro else ""
    fallos = 0
    adoptado = _leer_lock(origen)
    descartar = frozenset(descartar)
    lock_cambio = False

    # --- mapas -----------------------------------------------------------
    for item in sorted(mapas, key=lambda x: x["n"]):
        ruta = origen / item["fuente"]
        if not ruta.is_file():
            print(f"✗ no existe {ruta}")
            fallos += 1
            continue
        texto_repo = ruta.read_text(encoding="utf-8")
        canvas = json.loads(texto_repo)
        nombre = nombre_publicado(item, ".canvas")
        destino = dir_mapas / nombre
        procedencia, situacion, escribe, falla = _decidir(
            item, texto_repo, destino, adoptado, descartar)

        # La compuerta de legibilidad es DURA para lo generado y AVISO para lo
        # manual. Un canvas que dibuja una persona casi siempre la incumple —el
        # corredor de 60 px que motivó la compuerta es el que pone Obsidian por
        # defecto—, así que exigirla aquí anularía por la puerta de atrás el
        # permiso de dibujar a mano.
        duros = [str(p) for p in validar(canvas, libres=item.get("libres", [])) if p.duro]
        if duros:
            cabeza = "✗" if procedencia == W.GENERADO else "⚠"
            print(f"{cabeza} {item['fuente']} no pasa su compuerta de legibilidad:")
            for d in duros:
                print("   " + d)
            if procedencia == W.GENERADO:
                fallos += 1
                continue

        if falla and not adoptar:
            _explicar_negativa(nombre, situacion, item["generador"],
                               item["fuente"])
            fallos += 1
            continue

        n = sum(1 for x in canvas["nodes"] if x.get("type") == "text")
        g = sum(1 for x in canvas["nodes"] if x.get("type") == "group")
        version = adoptado.get(item["fuente"], {}).get("version", PRIMERA_VERSION)
        # El archivado se CALCULA también en simulacro: un ensayo que callara que
        # va a nacer una versión estaría ocultando justo lo que hay que revisar
        # antes de tocar la bóveda.
        archivado = archivar(destino, texto_repo, item, dir_versiones, version,
                             fm, simulacro=simulacro) if escribe else None
        if archivado is not None:
            print(f"  ↳ archiva v{version} → {archivado['fichero']} "
                  f"({archivado['nacen']} nodos nacen · "
                  f"{archivado['mueren']} mueren · "
                  f"{archivado['cambian']} cambian de texto){marca}")
        if not simulacro:
            dir_mapas.mkdir(parents=True, exist_ok=True)
            if escribe:
                # Nunca se pisa un diseño sin guardarlo primero. Y si el guardado
                # no dejó fichero en disco, NO se pisa: perder el anterior para
                # publicar el nuevo es exactamente lo que esto impide.
                if archivado is not None:
                    if not (dir_versiones / archivado["fichero"]).is_file():
                        print(f"✗ {nombre}: no se pudo archivar la versión "
                              f"v{version} en {dir_versiones}. La bóveda NO se "
                              f"ha tocado: publicar encima perdería ese diseño.")
                        fallos += 1
                        continue
                    version += 1
                shutil.copy2(ruta, destino)
            ficha = dir_mapas / nombre_publicado(item, ".md")
            if not ficha.exists():
                ficha.write_text(ficha_de(item, titular, fm), encoding="utf-8")
            lock_cambio |= _sellar(adoptado, item, texto_repo, destino, version)
        # El sello dice qué pasó DE VERDAD. Un descarte y una adopción dejan el
        # lock igual y son lo contrario: uno tira lo de la bóveda y el otro lo
        # conserva. Decir «adoptado» en los dos casos sería mentir en la única
        # línea que el usuario va a leer.
        if item["fuente"] in descartar:
            sello = f" · descartado lo de la bóveda ({situacion}), manda el generador"
        else:
            sello = {W.MANUAL: " · manual, no se toca",
                     W.ADOPTADO: " · difiere del generador, adoptado",
                     W.EDITADO_A_MANO: " · ADOPTADO tal cual",
                     W.SIN_ADOPTAR: " · ADOPTADO tal cual",
                     W.CONFLICTO: " · ADOPTADO tal cual"}.get(
                procedencia if procedencia == W.MANUAL else situacion, "")
        print(f"✓ {nombre}  ({n} nodos · {g} grupos · {len(canvas['edges'])} "
              f"aristas){sello}{marca}")

    if mapas and not simulacro:
        (dir_mapas / f"00 — Mapas de {titular}.md").write_text(
            indice_de_mapas(mapas, titular, proyecto, fm), encoding="utf-8")

    # --- los índices, antes que las Bases que transcluyen -----------------
    # `wiki.json` declara un `generador` por Base, y publicar sólo lo NOMBRABA:
    # copiaba el `.base` y, si faltaba, preguntaba «¿corriste su generador?».
    # El índice —la lista de `[[enlaces]]`, que es la única arista del grafo
    # hacia esas notas, porque una Base es una consulta y no deja enlace— se
    # quedaba con lo de la última vez que alguien lo corrió a mano. Mordió dos
    # veces: la v2 del lazo nació sin índice (2026-09-08) e `INC-016` salió como
    # no indexada el día siguiente, con la nota ya escrita y publicada.
    #
    # Va aquí, ANTES del bucle de Bases, porque un índice transcluye la Base que
    # ese bucle publica a continuación. Y corre siempre: un generador sabe mejor
    # que este script si tiene algo que hacer —`generar_versiones` dice «no se
    # ha archivado ningún diseño» y devuelve 0—, así que la condición no se
    # adivina desde fuera.
    fallos += _correr_generadores(bases, origen, simulacro)

    # --- bases -----------------------------------------------------------
    for item in sorted(bases, key=lambda x: x["n"]):
        ruta = origen / item["fuente"]
        if not ruta.is_file():
            print(f"✗ no existe {ruta} — ¿corriste su generador?")
            fallos += 1
            continue
        texto_repo = ruta.read_text(encoding="utf-8")
        destino = dir_bases / item["fuente"]
        _, situacion, escribe, falla = _decidir(item, texto_repo, destino,
                                                adoptado, descartar)
        if falla and not adoptar:
            _explicar_negativa(item["fuente"], situacion, item["generador"],
                               item["fuente"])
            fallos += 1
            continue
        if not simulacro:
            dir_bases.mkdir(parents=True, exist_ok=True)
            if escribe:
                shutil.copy2(ruta, destino)
            lock_cambio |= _sellar(adoptado, item, texto_repo, destino)
        vistas = sum(1 for l in texto_repo.splitlines()
                     if l.startswith("  - type:"))
        print(f"✓ {item['fuente']}  ({vistas} vistas · {item['tabula']}){marca}")

    # --- Regla 6: commit automático al cerrar una incidencia --------------
    # Sólo si el proyecto lo pidió (`git_commit_al_cerrar_incidencia`, por
    # defecto `false`) y declara dónde vive el tablero. La detección compara
    # contra lo que la ÚLTIMA publicación vio, no contra un valor fijo: sin
    # ese "antes" no hay transición que observar, sólo un valor actual.
    incidencias_snapshot = None
    cerradas = []
    carpeta_inc = _carpeta_incidencias(raiz_proyecto, manifiesto)
    if (manifiesto.get("git_commit_al_cerrar_incidencia", False)
            and carpeta_inc is not None):
        titular_inc = manifiesto["estructura"].get("incidencias_de", proyecto)
        anteriores_inc = _leer_incidencias_lock(origen)
        actuales_inc = _incidencias_actuales(carpeta_inc, titular_inc)
        incidencias_snapshot = {ident: info["situacion"]
                                for ident, info in actuales_inc.items()}
        # ATALANTA INC-067 (2026-09-23): un generador que abortó —p. ej. el
        # tablero rechazó una `resuelta` sin `hito`— dejaba seguir hasta aquí y
        # se firmaba como cerrada una incidencia que el propio tablero rechazó.
        # Con fallos no se commitea NI se avanza el «antes»: si el lock guardara
        # la `resuelta` rechazada, la publicación buena siguiente no vería la
        # transición y el cierre no se commitearía nunca.
        if fallos:
            print(f"  ✗ Regla 6: {fallos} generador(es) fallaron — no se commitea "
                  f"ningún cierre y el lock conserva la situación anterior.")
            incidencias_snapshot = (anteriores_inc if CLAVE_INCIDENCIAS
                                    in _leer_json_lock(origen) else None)
        if incidencias_snapshot is not None and incidencias_snapshot != anteriores_inc:
            lock_cambio = True
        # Primera activación: el lock aún no guarda ningún «antes». Comparar
        # contra `{}` tomaría por recién cerradas TODAS las que ya estaban
        # `resuelta` — y firmaría cierres que ocurrieron hace semanas. Esta
        # publicación sólo toma la línea base; los cierres cuentan desde aquí.
        primera_vez = CLAVE_INCIDENCIAS not in _leer_json_lock(origen)
        if primera_vez:
            print(f"  · Regla 6: primera observación del tablero "
                  f"({len(incidencias_snapshot)} incidencias) — línea base, sin commit")
        elif not simulacro and not fallos:
            cerradas = _recien_cerradas(actuales_inc, anteriores_inc)

    if lock_cambio and not simulacro:
        _escribir_lock(origen, adoptado, incidencias_snapshot)

    if cerradas:
        _commit_por_cierre(origen, cerradas, mapas, bases,
                           manifiesto["estructura"].get("incidencias_de", proyecto),
                           _coautoria(manifiesto))

    # --- el eslabón que pone el humano -----------------------------------
    fallos += _comprobar_indexado(raiz_proyecto, proyecto, titular, mapas, bases)
    return 1 if fallos else 0


def _comprobar_indexado(raiz: Path, proyecto: str, titular: str,
                        mapas, bases) -> int:
    """La cadena índice → proyecto → carpeta. Lo que se siembra no se comprueba.

    La ficha y el índice de mapas los escribe este script, así que exigir que el
    canvas «esté enlazado» sería una compuerta que siempre pasa. Lo que un
    humano sí tiene que poner —y por tanto lo único que vale comprobar— es el
    enlace desde la nota puerta hacia esos índices. Cuál es esa puerta lo decide
    `puerta_de`, no este bucle.
    """
    especifica = raiz / titular / f"{titular}.md"
    puerta = especifica if especifica.is_file() else raiz / f"{proyecto}.md"
    if not puerta.is_file():
        print(f"⚠ no hay nota puerta {puerta.name}: nadie llega a esta carpeta")
        return 1
    texto = puerta.read_text(encoding="utf-8", errors="ignore")
    faltan = []
    if mapas and f"00 — Mapas de {titular}" not in texto:
        faltan.append(f"- [[00 — Mapas de {titular}|🗺️ los mapas]] — "
                      f"{len(mapas)} canvas, numerados y en orden de lectura")
    for b in sorted(bases, key=lambda x: x["n"]):
        # El nombre del índice de una base es dato del proyecto, no del
        # publicador: tenerlo escrito aquí («00 — Ecuaciones de ELEMENT») fue lo
        # que impidió vendorizar este fichero, y por eso la copia de la skill
        # divergió 163 líneas sin que nada lo notara.
        indice = b.get("indice")
        if indice and indice not in texto:
            faltan.append(f"- [[{indice}|{b.get('gancho', b['titulo'])}]] — {b['tabula']}")
    if faltan:
        print(f"✗ {puerta.name} no enlaza lo que se acaba de publicar.")
        print("  Añade estas líneas (regla dura: se indexa en la misma operación):")
        for f in faltan:
            print("    " + f)
        return 1
    print(f"✓ {puerta.name} enlaza los índices de esta carpeta")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    simulacro = "--simulacro" in argv
    adoptar = "--adoptar" in argv
    #: Todo lo que sigue a `--descartar` y no es otra bandera. Exige nombres a
    #: propósito: `--descartar` a secas no descarta nada y sale con fallo.
    descartar, tomando = [], False
    sueltos = []
    for a in argv:
        if a.startswith("--"):
            tomando = a == "--descartar"
        elif tomando:
            descartar.append(a)
        else:
            sueltos.append(a)
    if "--descartar" in argv and not descartar:
        print("✗ --descartar exige el nombre del artefacto, p. ej. "
              "`--descartar apolo_lazo_de_control.canvas`.")
        print("  No hay descarte global: adoptar no destruye nada y esto sí.")
        return 1
    origen = Path(sueltos[0] if sueltos else "docs/wiki").resolve()
    return publicar(origen, simulacro, adoptar, descartar)


if __name__ == "__main__":
    raise SystemExit(main())
