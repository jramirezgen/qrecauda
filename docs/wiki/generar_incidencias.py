# -*- coding: utf-8 -*-
"""El tablero de incidencias del wiki repo: la Base, el índice y la compuerta.

⛔ **Por qué `situacion:` y no `estado:`.** Medido el 2026-09-08 sobre el vault:
`estado:` lo llevan **998 notas** con tres vocabularios incompatibles a la vez
(`validada`/`vivo` en `wiki/`, `sin-verificar` en `alejandria/`). El desplegable
de propiedades de Obsidian es **global al vault**, así que meter ahí un sexto
vocabulario dejaría el selector inservible para todo el mundo. `situacion`,
`peso`, `hito`, `bloqueado_por` y `nodo` estaban en **0 notas**: son libres.

⛔ **Por qué el índice lista los enlaces aunque haya Base.** Una Base es una
**consulta**: Obsidian la resuelve al dibujarla y no deja ni un `[[ ]]` en el
fichero. Con sólo la transclusión, las incidencias salían «no indexadas» en
`vault_audit.py` — el mismo defecto que ya pagó el índice de ecuaciones. La
Base es la vista filtrable; la lista es la arista.

**Las incidencias las escribes tú, en Obsidian, a mano.** Este script no
siembra ninguna: las lee, comprueba que el tablero no sea decorativo, y
regenera lo que sí es derivado (la Base y el índice). Una incidencia es
`procedencia: manual` por naturaleza — su contenido nunca se sobrescribe.

**Las tres reglas que impiden que el tablero mienta**, y que son la diferencia
entre un tablero y una lista de deseos:

  1. `situacion` obligatoria y del vocabulario cerrado;
  2. `bloqueada` exige `bloqueado_por` apuntando a una incidencia **que exista**
     — «estoy bloqueado» sin decir por qué es una excusa, no un estado;
  3. `resuelta` exige `hito` — algo se cierra *en* una entrega, o no se cerró.

Uso:  python3 docs/wiki/generar_incidencias.py [docs/wiki] [--simulacro]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from base_lib import (Base, Vista, con_etiqueta, en_carpeta,  # noqa: E402
                      etiquetas_de, informe, y)

HOY = date.today().isoformat()

#: Vocabulario CERRADO. Añadir un valor es una decisión, no una improvisación:
#: en cuanto hay dos palabras para lo mismo el tablero deja de poder filtrarse.
SITUACIONES = ("abierta", "en_curso", "bloqueada", "resuelta", "descartada")

#: Las que siguen pendientes. Se nombra lo que cuenta como deuda, en un sitio.
VIVAS = ("abierta", "en_curso", "bloqueada")

PESOS = (1, 2, 3, 4, 5)

#: Vocabulario CERRADO, por la misma razón que `situacion`: en cuanto hay dos
#: palabras para lo mismo, el tablero deja de poder filtrarse.
#:
#: ⛔ **Por qué hacía falta.** El tablero nació sabiendo describir **defectos**
#: —«qué está MAL, no qué hacer», dice la plantilla— y el 2026-09-08 entró un
#: RFC de arquitectura que no denuncia ninguna avería: propone cómo debería ser
#: el pipeline. Sin `tipo` sólo había dos salidas, y las dos malas: mentir en el
#: título llamándolo defecto, o dejarlo fuera del tablero — que es donde estaba,
#: sin frontmatter, reportado como nota ajena.
#:
#: `defecto` algo no hace lo que dice · `rfc` una propuesta de arquitectura ·
#: `mejora` funciona y podría hacer más.
TIPOS = ("defecto", "rfc", "mejora")

#: Las casillas del cuerpo. Un RFC con 13 puntos y una incidencia de una línea
#: se veían idénticos en el índice.
_CASILLA = re.compile(r"^\s*[-*+]\s+\[([ xX])\]", re.M)

#: El identificador. Monótono y **nunca reutilizado**, como los `AL-####` de
#: Alejandría y como los `#N` de GitHub — NO denso, a diferencia de los mapas.
#:
#: ⛔ La numeración densa (`1..N` sin huecos) es correcta para una colección
#: cerrada que alguien ordena: si falta el `03`, se perdió una pieza. Un tablero
#: es lo contrario: se le añade por el final, se descarta por el medio, y una
#: incidencia citada en un commit tiene que seguir queriendo decir lo mismo
#: dentro de un año. Renumerar rompería la cita.
INC = re.compile(r"^INC-\d{3}$")
INDICE = "00 — Incidencias de {titular}"

#: La plantilla vive FUERA de la carpeta, en la raíz del wiki repo y con el
#: nombre que el vault ya usa (`_PLANTILLA Proyecto.md`).
#:
#: ⛔ Dentro, la Base la tabulaba como una incidencia más: lleva la etiqueta a
#: propósito —para que una copia funcione sin tocar nada— y el filtro sólo sabe
#: de carpeta y etiqueta. Es el mismo defecto que ya tuvo el índice de las
#: ecuaciones, que salía como una fila con todas las columnas en blanco.
PLANTILLA = "_PLANTILLA Incidencia"


# --------------------------------------------------------------------------
# Leer lo que el usuario escribió
# --------------------------------------------------------------------------

def frontmatter(texto: str) -> dict:
    """El frontmatter como dict de escalares y listas. Sin dependencias.

    No es un parser de YAML: es el subconjunto que este tablero usa (escalar,
    lista en línea, lista en bloque). Cualquier otra cosa se devuelve como texto
    crudo, y la compuerta la rechazará por no estar en el vocabulario — que es
    mejor que adivinar.
    """
    if not texto.startswith("---"):
        return {}
    fin = texto.find("\n---", 3)
    if fin < 0:
        return {}
    fm: dict = {}
    clave = None
    for linea in texto[3:fin].splitlines():
        if not linea.strip():
            continue
        if linea.startswith("  - ") and clave:
            fm.setdefault(clave, [])
            if isinstance(fm[clave], list):
                fm[clave].append(_valor(linea[4:]))
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", linea)
        if not m:
            continue
        clave, crudo = m.group(1), m.group(2).strip()
        if crudo.startswith("[") and crudo.endswith("]"):
            fm[clave] = [_valor(v) for v in crudo[1:-1].split(",") if v.strip()]
        elif crudo == "":
            # ⛔ Vacío es AUSENTE, no lista vacía. Devolver `[]` hacía que
            # `hito:` sin rellenar valiera `"[]"` al pasarlo a texto —o sea,
            # verdadero— y `resuelta` sin hito pasaba la compuerta. La regla
            # existía y no protegía nada.
            fm[clave] = None
        else:
            fm[clave] = _valor(crudo)
    return fm


def _valor(v: str):
    v = v.strip().strip('"').strip("'").strip()
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def casillas_de(texto: str) -> tuple[int, int]:
    """`(hechas, total)` de las casillas `- [ ]` / `- [x]` del cuerpo.

    ⛔ Va en el índice **generado** y nunca de vuelta al frontmatter de la nota.
    Un conteo derivado escrito en una nota viva se desincroniza en cuanto
    alguien marca una casilla —y encima pisa lo que escribió una persona—, que
    es exactamente el error que este repo ya pagó con los conteos del vault.
    """
    marcas = _CASILLA.findall(texto)
    return sum(1 for m in marcas if m.lower() == "x"), len(marcas)


def _enlazadas(valor) -> list[str]:
    """Los `[[destinos]]` de un campo, venga como lista o como escalar."""
    if valor is None:
        return []
    crudo = valor if isinstance(valor, list) else [valor]
    salida = []
    for v in crudo:
        salida += [d.split("|")[0].strip()
                   for d in re.findall(r"\[\[([^\]]+)\]\]", str(v))]
    return salida


#: La etiqueta que hace de una nota una incidencia. Es la MISMA que filtra la
#: Base, y por eso se declara una vez: el índice y la tabla tienen que ver el
#: mismo conjunto o uno de los dos miente.
ETIQUETA = "incidencia"


def _candidatas(carpeta: Path, titular: str) -> list[Path]:
    fuera = {INDICE.format(titular=titular), PLANTILLA}
    return sorted((p for p in carpeta.glob("*.md") if p.stem not in fuera),
                  key=lambda p: p.name)


def leer(carpeta: Path, titular: str) -> list[tuple[Path, dict]]:
    """Las incidencias de la carpeta: las que llevan la etiqueta.

    Carpeta **y** etiqueta, igual que el filtro de la Base. Sólo la carpeta
    metía en el índice cualquier `.md` que cayera ahí — el 2026-09-08 unos
    apuntes sueltos salieron como `- ``None`` [[1.]] — ``None`` · peso None`,
    mientras la tabla, que sí exige la etiqueta, no los mostraba.
    """
    return [(p, frontmatter(p.read_text(encoding="utf-8", errors="ignore")))
            for p in _candidatas(carpeta, titular)
            if ETIQUETA in etiquetas_de(p)]


def ajenas(carpeta: Path, titular: str) -> list[Path]:
    """Notas que viven en la carpeta y no son incidencias.

    No entran al tablero, pero tampoco desaparecen sin decirlo: una nota en la
    carpeta equivocada es un hecho que alguien tiene que ver.
    """
    return [p for p in _candidatas(carpeta, titular)
            if ETIQUETA not in etiquetas_de(p)]


# --------------------------------------------------------------------------
# La compuerta: un tablero que no se comprueba es una lista de deseos
# --------------------------------------------------------------------------

def problemas_de(incidencias: list[tuple[Path, dict]]) -> list[str]:
    existen = {p.stem for p, _ in incidencias}
    P: list[str] = []
    vistos: dict[str, str] = {}
    for ruta, fm in incidencias:
        n = ruta.stem
        ident = str(fm.get("inc", ""))
        if not INC.match(ident):
            P.append(f"{n}: `inc: {ident!r}` no tiene la forma INC-###")
        elif ident in vistos:
            P.append(f"{n}: `inc: {ident}` ya lo lleva «{vistos[ident]}» — un "
                     f"identificador se asigna una vez y no se reutiliza")
        else:
            vistos[ident] = n
        s = fm.get("situacion")
        if s not in SITUACIONES:
            P.append(f"{n}: `situacion: {s!r}` no está en {list(SITUACIONES)}")
            continue
        if s == "bloqueada":
            destinos = _enlazadas(fm.get("bloqueado_por", []))
            if not destinos:
                P.append(f"{n}: `bloqueada` sin `bloqueado_por` — «estoy "
                         f"bloqueado» sin decir por qué es una excusa, no un estado")
            for d in destinos:
                if d not in existen:
                    P.append(f"{n}: `bloqueado_por: [[{d}]]` no existe en el tablero")
        if s == "resuelta" and not str(fm.get("hito") or "").strip():
            P.append(f"{n}: `resuelta` sin `hito` — algo se cierra EN una "
                     f"entrega, o no se cerró")
        tipo = fm.get("tipo")
        if tipo not in TIPOS:
            P.append(f"{n}: `tipo: {tipo!r}` no está en {list(TIPOS)}")
        peso = fm.get("peso")
        if peso not in PESOS:
            P.append(f"{n}: `peso: {peso!r}` no está en {list(PESOS)}")
        if fm.get("nodo") and not fm.get("mapa_n"):
            P.append(f"{n}: declara `nodo: {fm['nodo']}` sin `mapa_n` — un id de "
                     f"nodo no dice nada sin decir de qué mapa")
    return P


# --------------------------------------------------------------------------
# Lo derivado: la Base y el índice
# --------------------------------------------------------------------------

def base_de(carpeta: Path, titular: str) -> Base:
    """Cuatro vistas, una por pregunta que de verdad se hace sobre un tablero.

    Toma la carpeta **absoluta**: la relativa depende de qué se abrió como
    bóveda, y en este disco hay dos que contienen `wiki/ELEMENT/`. Pasarla
    relativa fue lo que dejó las cuatro vistas en blanco el 2026-09-08.
    """
    return Base(
        nombre=f"Incidencias de {titular}",
        # Carpeta **y** etiqueta, y la etiqueta en singular a propósito: el
        # índice de la carpeta lleva `incidencias` (plural), así que no se
        # tabula a sí mismo. Sólo la carpeta lo metía como una fila con todas
        # las columnas vacías — el mismo defecto que ya tuvo el de ecuaciones.
        filtros=y(en_carpeta(carpeta), con_etiqueta("incidencia")),
        propiedades={
            "inc": "#",
            "tipo": "Tipo",
            "situacion": "Situación",
            "peso": "Peso",
            "hito": "Hito",
            "bloqueado_por": "Bloqueada por",
            "mapa_n": "Mapa",
            "nodo": "Nodo",
            "file.name": "Incidencia",
        },
        vistas=[
            Vista(tipo="table", nombre="Vivas por peso",
                  orden=["inc", "tipo", "peso", "file.name", "situacion",
                         "hito", "mapa_n"],
                  filtros={"and": ['situacion != "resuelta"',
                                   'situacion != "descartada"']}),
            # Un defecto se arregla y un RFC se decide: mezclados en una sola
            # lista, lo segundo parece deuda y se pospone para siempre.
            Vista(tipo="table", nombre="Por tipo",
                  orden=["tipo", "inc", "peso", "file.name", "situacion"],
                  agrupar_por=("tipo", "ASC")),
            Vista(tipo="table", nombre="Por hito",
                  orden=["hito", "peso", "inc", "file.name", "situacion"],
                  agrupar_por=("hito", "ASC")),
            Vista(tipo="table", nombre="Bloqueadas",
                  orden=["inc", "file.name", "bloqueado_por", "peso", "hito"],
                  filtros={"and": ['situacion == "bloqueada"']}),
            Vista(tipo="cards", nombre="Fichas",
                  orden=["file.name", "tipo", "situacion", "peso"]),
        ],
    )


def siguiente_id(incidencias) -> str:
    """El primer `INC-###` libre. Monótono: nunca rellena un hueco."""
    usados = [int(str(fm.get("inc", "INC-000"))[4:] or 0)
              for _, fm in incidencias if INC.match(str(fm.get("inc", "")))]
    return f"INC-{max(usados, default=0) + 1:03d}"


def indice_de(base_rel: str, incidencias, titular: str, fm_vault: dict,
              indice_de_mapas: str | None = None) -> str:
    vivas = [(p, fm) for p, fm in incidencias if fm.get("situacion") in VIVAS]
    # Por identificador, no por nombre de fichero: el orden de un tablero es el
    # orden en que aparecieron las cosas, y renombrar una incidencia no puede
    # moverla de sitio en su propio índice.
    def _renglon(ruta, fm) -> str:
        hechas, total = casillas_de(ruta.read_text(encoding="utf-8",
                                                   errors="ignore"))
        return (f"- `{fm.get('inc')}` [[{ruta.stem}]] — `{fm.get('tipo')}` · "
                f"`{fm.get('situacion')}` · peso {fm.get('peso')}"
                + (f" · hito `{fm['hito']}`"
                   if str(fm.get("hito") or "").strip() else "")
                + (f" · **{hechas}/{total}** casillas" if total else ""))

    lista = "\n".join(
        _renglon(ruta, fm)
        for ruta, fm in sorted(incidencias,
                               key=lambda par: str(par[1].get("inc", "")))
    ) or "*(el tablero está vacío)*"
    por_tipo = ", ".join(
        f"{sum(1 for _, fm in incidencias if fm.get('tipo') == t)} `{t}`"
        for t in TIPOS)
    area = "[" + ", ".join(fm_vault["area"]) + "]"
    tema = "[" + ", ".join(fm_vault["tema"]) + "]"
    # El índice de mapas es dato del proyecto (sale de `mapas_de`), no de este
    # generador: tenerlo escrito aquí es lo que impidió vendorizar `publicar.py`
    # y lo dejó divergir 163 líneas sin que nada lo notara.
    enlace_mapas = (f"- [[{indice_de_mapas}]] — los canvas a los que `mapa_n` y "
                    f"`nodo` apuntan\n" if indice_de_mapas else "")
    return f"""---
tags: [indice, incidencias, {titular.lower()}]
area: {area}
tema: {tema}
creado: {HOY}
actualizado: {HOY}
fuente: "docs/wiki/generar_incidencias.py sobre las notas de esta carpeta"
resumen: "El tablero de incidencias de {titular}: {len(vivas)} vivas de {len(incidencias)}."
submapa: true
---

# Incidencias de {titular}

**{len(vivas)} vivas** de {len(incidencias)}. La siguiente libre es
**`{siguiente_id(incidencias)}`**. Una incidencia se escribe **aquí, a mano, en
Obsidian** — copiando [[{PLANTILLA}]]. Ningún script las siembra ni las
sobrescribe: son tuyas.

![[{base_rel}]]

## Las {len(incidencias)} incidencias

Una Base es una **consulta**: Obsidian la resuelve al dibujarla y no deja ningún
enlace en el fichero, así que sin esta lista el grafo del vault no tendría por
dónde llegar a estas notas. La tabla de arriba es para **filtrar**; esta lista
es la **arista**.

{lista}

Por tipo: {por_tipo}.

## Qué es cada cosa: `tipo:`

| `tipo` | qué significa |
|---|---|
| `defecto` | algo no hace lo que dice que hace |
| `rfc` | una propuesta de arquitectura, no una avería |
| `mejora` | funciona, y podría hacer más |

⛔ Esta columna nació el 2026-09-08, cuando entró un RFC de arquitectura al
tablero. Sin ella sólo había dos salidas y las dos malas: llamarlo «defecto» en
el título, o dejarlo fuera del tablero — que es donde estaba. **Un defecto se
arregla y un RFC se decide**; mezclados en una sola lista, lo segundo parece
deuda y se pospone para siempre.

## El vocabulario, y por qué es `situacion:` y no `estado:`

| `situacion` | qué significa |
|---|---|
| `abierta` | está descrita y nadie la ha empezado |
| `en_curso` | alguien está dentro ahora mismo |
| `bloqueada` | no puede avanzar hasta que otra se cierre |
| `resuelta` | cerrada, y en un hito concreto |
| `descartada` | se decidió no hacerla, y la nota dice por qué |

`estado:` estaba ocupado: **998 notas** del vault lo usan con tres vocabularios
incompatibles a la vez, y el desplegable de propiedades de Obsidian es **global**
— un sexto vocabulario ahí dejaría el selector inservible para todos. `situacion`,
`peso`, `hito`, `bloqueado_por` y `nodo` estaban en 0 notas.

## Las tres reglas que impiden que esto sea una lista de deseos

1. `situacion` sale del vocabulario cerrado de arriba, o la compuerta falla.
2. **`bloqueada` exige `bloqueado_por`** apuntando a una incidencia que exista.
   «Estoy bloqueado» sin decir por qué es una excusa, no un estado.
3. **`resuelta` exige `hito`.** Algo se cierra *en* una entrega, o no se cerró.

Además, `nodo` sin `mapa_n` falla: un id de nodo no dice nada sin decir de qué
mapa. Y con los dos, la incidencia queda **anclada al canvas**: se puede ir del
tablero al dibujo y al revés.

Las **casillas** de cada renglón (`hechas/total`) se cuentan del cuerpo de la
nota — las `- [ ]` y `- [x]` que escribiste tú. Se publican **aquí**, en el
índice generado, y **nunca** se escriben de vuelta a tu frontmatter: un conteo
derivado guardado en una nota viva se desincroniza en cuanto marcas una casilla,
y encima pisa lo que escribió una persona.

```bash
python3 docs/wiki/generar_incidencias.py docs/wiki   # comprueba y regenera
```

## Relacionado

{enlace_mapas}- [[{titular}]]
"""


def plantilla_de(titular: str, fm_vault: dict) -> str:
    area = "[" + ", ".join(fm_vault["area"]) + "]"
    tema = "[" + ", ".join(fm_vault["tema"]) + "]"
    return f"""---
tags: [incidencia, {titular.lower()}]
area: {area}
tema: {tema}
creado: {HOY}
actualizado: {HOY}
fuente: "escrita a mano"
inc: INC-000
situacion: abierta
tipo: defecto
peso: 3
hito: ""
bloqueado_por: []
mapa_n:
nodo:
---

# (título: qué está MAL, no qué hacer)

> Cambia `inc: INC-000` por el siguiente libre, que el índice dice en su
> primera línea. Se asigna una vez y **no se reutiliza**: si esta incidencia se
> descarta, su número se queda con ella.
>
> `tipo:` es `defecto` (algo no hace lo que dice), `rfc` (una propuesta de
> arquitectura) o `mejora` (funciona y podría hacer más). Si es un `rfc`, el
> título no tiene por qué decir qué está mal.

## Qué pasa

Lo observado, con la cifra y de dónde sale. Si no hay cifra, se dice.

## Cómo se sabe que está mal

El comando, el test o la corrida que lo enseña. Una incidencia sin forma de
reproducirla es una opinión.

## Qué la cierra

La condición de aceptación, medible. Cuando se cumpla, `situacion: resuelta` y
`hito:` con la entrega donde se cerró.

## Relacionado

- [[00 — Incidencias de {titular}]]
"""


# --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("origen", nargs="?", type=Path, default=AQUI)
    ap.add_argument("--simulacro", action="store_true")
    ap.add_argument("--resembrar-plantilla", action="store_true",
                    help="rehace _PLANTILLA con lo que este generador "
                         "produce hoy; pisa lo que haya")
    args = ap.parse_args(argv)

    origen = args.origen.resolve()
    manifiesto = json.loads((origen / "wiki.json").read_text(encoding="utf-8"))
    vault = Path(manifiesto["vault"])
    proyecto = manifiesto["proyecto"]
    #: De quién es el tablero: dato del PROYECTO, no del código.
    #:
    #: Estuvo clavado a `proyecto` con una razón buena para ELEMENT —«mapas_de»
    #: acota los canvas a APOLO, y un tablero acotado igual dejaría fuera lo que
    #: no es del motor—. Esa razón deja de valer en cuanto un proyecto tiene
    #: varios titulares hermanos: SAPYRIA publica SMALLRNA, WES y WGS, y cada
    #: uno lleva su propia serie `INC-###` en su propio repo. Un solo tablero
    #: «de SAPYRIA» mezclaría tres numeraciones que nadie coordina.
    #:
    #: Por defecto sigue siendo el proyecto, así que ELEMENT no declara nada y
    #: no cambia. Es la misma lección que el `frontmatter`: lo que depende del
    #: proyecto, escrito dentro del código copiado, es lo que impide copiarlo.
    titular = manifiesto["estructura"].get("incidencias_de", proyecto)
    fm_vault = manifiesto["frontmatter"]
    if not vault.is_dir():
        print(f"✗ no existe el vault: {vault}")
        return 2

    carpeta_rel = f"wiki/{proyecto}/{manifiesto['estructura']['incidencias']}"
    carpeta = vault / carpeta_rel
    carpeta.mkdir(parents=True, exist_ok=True)

    plantilla = carpeta.parent / f"{PLANTILLA}.md"
    quiere = plantilla_de(titular, fm_vault)
    if not plantilla.exists() and not args.simulacro:
        plantilla.write_text(quiere, encoding="utf-8")
        print(f"  ✓ {plantilla.name} (sembrada; edítala y no la borres)")
    elif plantilla.exists():
        # La plantilla se siembra una vez y no se pisa, porque está para
        # editarla a mano. Pero «no se pisa nunca» dejó publicada una versión
        # vieja —con `tags: [incidencia, apolo]`, sin `inc:` y enlazando a un
        # índice que no existe— sin que nada lo dijera: la misma avería
        # silenciosa que el filtro atado a una raíz. Así que la deriva se
        # AVISA, y pisarla exige pedirlo.
        vieja = plantilla.read_text(encoding="utf-8")
        if vieja == quiere:
            pass
        elif args.resembrar_plantilla and not args.simulacro:
            plantilla.write_text(quiere, encoding="utf-8")
            print(f"  ✓ {plantilla.name} (rehecha a petición)")
        else:
            print(f"  ⚠ {plantilla.name} difiere de lo que este generador "
                  "produce hoy. Si no la editaste tú, "
                  "`--resembrar-plantilla` la rehace.")

    incidencias = leer(carpeta, titular)
    for p in ajenas(carpeta, titular):
        print(f"  ⚠ {p.name}: está en la carpeta y no lleva `{ETIQUETA}`, "
              "así que no es del tablero. Muévela o etiquétala.")
    problemas = problemas_de(incidencias)
    for p in problemas:
        print(f"  ✗ {p}")

    base = base_de(carpeta, titular)
    ok, lineas = informe(base, vault)
    for l in lineas:
        print("  " + l)

    nombre_base = None
    for b in manifiesto.get("bases", []):
        if b.get("titulo") == f"Incidencias de {titular}":
            nombre_base = f"{b['n']:02d} — {b['titulo']}.base"
    if nombre_base is None:
        print("  ✗ wiki.json no declara la base «Incidencias»: sin número no se publica")
        return 1

    # ⛔ Se publica sólo si la compuerta pasó. Antes se escribía siempre y se
    # devolvía 1 al final: eso es avisar DESPUÉS de publicar, que es justo lo
    # que INC-006 reprocha a la compuerta de historial del vault.
    if problemas or not ok:
        print("  ✗ no se publica nada: primero se arregla lo de arriba.")
        return 1

    if not args.simulacro:
        (origen / nombre_base).write_text(base.a_yaml(), encoding="utf-8")
        print(f"  ✓ {nombre_base}")
        #: Por NOMBRE y no por ruta: ver `generar_ecuaciones.py`.
        base_rel = nombre_base
        indice = carpeta / f"{INDICE.format(titular=titular)}.md"
        mapas_de = manifiesto["estructura"].get("mapas_de")
        indice.write_text(
            indice_de(base_rel, incidencias, titular, fm_vault,
                      f"00 — Mapas de {mapas_de}" if mapas_de else None),
            encoding="utf-8")
        print(f"  ✓ {indice.name}  ({len(incidencias)} incidencia(s))")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
