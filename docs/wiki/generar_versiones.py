# -*- coding: utf-8 -*-
"""El histórico de diseños del wiki repo: la Base, el índice y la compuerta.

`archivar.py` guarda el mapa vigente antes de que el nuevo lo pise y deja dos
ficheros por versión: el `.canvas` y una nota que dice **qué cambió**. Eso
impide perder un diseño. Este generador cierra los dos huecos que quedaban, y
los dos eran silenciosos:

1. **Lo archivado no estaba indexado.** La regla dura de la bóveda es que una
   nota nueva se indexa *en la misma operación*; las de `Versiones/` nacieron
   sin índice ni Base, así que no salían en ninguna consulta y sólo las
   encontraba quien ya sabía que estaban.
2. **Nada comprobaba que lo archivado siguiera siendo lo archivado.** La nota
   publica una `huella`; si el `.canvas` de al lado se edita, la huella deja de
   cuadrar y el histórico pasa a decir algo que no ocurrió — que es peor que no
   tener histórico, porque se sigue creyendo igual.

⛔ **Por qué esto NO siembra nada.** Al revés que las incidencias (que escribe
el usuario) y que las ecuaciones (que se siembran de un JSON), aquí **todo el
contenido lo produce `archivar.py`**: este script sólo lee lo que hay, lo
comprueba y regenera lo derivado. Si falta una versión, no se inventa: se
publica un mapa y el archivador la crea.

Uso:  python3 docs/wiki/generar_versiones.py [docs/wiki] [--simulacro]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from hashlib import sha256
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from base_lib import (Base, Vista, con_etiqueta, en_carpeta,  # noqa: E402
                      etiquetas_de, informe, raices_de_boveda, y)
from generar_incidencias import frontmatter  # noqa: E402

HOY = date.today().isoformat()

#: La etiqueta que hace de una nota una versión archivada. La MISMA que filtra
#: la Base: si el índice decidiera por su cuenta qué nota cuenta, tendría un
#: criterio distinto del de la tabla y uno de los dos mentiría.
ETIQUETA = "version"

INDICE = "00 — Versiones de mapas de {titular}"

#: Cuántos hex de sha256 publica `archivar.py`. Vive aquí porque es lo que esta
#: compuerta compara; si allí cambiara, este número tiene que cambiar con él.
DIGITOS_DE_HUELLA = 16


def leer(carpeta: Path) -> list[tuple[Path, dict]]:
    """Las notas de versión de la carpeta: las que llevan la etiqueta."""
    if not carpeta.is_dir():
        return []
    fuera = {INDICE.format(titular=t) for t in ("",)} | set()
    return [(p, frontmatter(p.read_text(encoding="utf-8", errors="ignore")))
            for p in sorted(carpeta.glob("*.md"), key=lambda p: p.name)
            if ETIQUETA in etiquetas_de(p) and p.stem not in fuera]


def huella_de(canvas: Path) -> str:
    """La misma cuenta que hace `archivar.py`, en un solo sitio."""
    return sha256(canvas.read_text(encoding="utf-8", errors="ignore")
                  .encode("utf-8")).hexdigest()[:DIGITOS_DE_HUELLA]


# --------------------------------------------------------------------------
# La compuerta
# --------------------------------------------------------------------------

def problemas_de(versiones: list[tuple[Path, dict]], carpeta: Path,
                 mapas: list[dict]) -> list[str]:
    """Las cuatro reglas que impiden que un archivo deje de serlo."""
    declarados = {int(m["n"]) for m in mapas}
    P: list[str] = []
    vistas: dict[tuple, str] = {}
    con_nota: set[str] = set()

    for ruta, fm in versiones:
        n = ruta.stem
        canvas = carpeta / f"{n}.canvas"
        con_nota.add(n)
        mapa_n, version = fm.get("mapa_n"), fm.get("version")
        if not isinstance(mapa_n, int) or mapa_n not in declarados:
            P.append(f"{n}: `mapa_n: {mapa_n!r}` no es ninguno de los mapas "
                     f"declarados {sorted(declarados)} — una versión de un mapa "
                     f"que nadie puede abrir no archiva nada")
        if not isinstance(version, int) or version < 1:
            P.append(f"{n}: `version: {version!r}` no es un entero ≥ 1")
        elif (mapa_n, version) in vistas:
            P.append(f"{n}: la v{version} del mapa {mapa_n} ya existe "
                     f"(«{vistas[(mapa_n, version)]}») — dos versiones con el "
                     f"mismo número significan que una pisó a la otra")
        else:
            vistas[(mapa_n, version)] = n
        if not canvas.is_file():
            P.append(f"{n}: no está el canvas `{canvas.name}` — la nota "
                     f"describe un diseño que ya no está, que es justo lo que "
                     f"este archivo existe para impedir")
            continue
        declarada = str(fm.get("huella") or "")
        real = huella_de(canvas)
        if declarada != real:
            P.append(f"{n}: la `huella` dice `{declarada}` y el canvas "
                     f"archivado vale `{real}` — alguien lo editó, y un "
                     f"histórico retocado se sigue creyendo igual")

    for c in sorted(carpeta.glob("*.canvas")) if carpeta.is_dir() else []:
        if c.stem not in con_nota:
            P.append(f"{c.stem}: canvas archivado sin nota — un `.canvas` "
                     f"suelto no dice de qué mapa es versión ni de cuándo")
    return P


# --------------------------------------------------------------------------
# Lo derivado: la Base y el índice
# --------------------------------------------------------------------------

def base_de(carpeta: Path, titular: str) -> Base:
    """Tres vistas: por mapa, la línea entera, y las fichas.

    Toma la carpeta **absoluta**: la relativa depende de qué se abrió como
    bóveda, y en este disco hay dos que contienen `wiki/ELEMENT/`.
    """
    return Base(
        nombre=f"Versiones de mapas de {titular}",
        filtros=y(en_carpeta(carpeta), con_etiqueta(ETIQUETA)),
        propiedades={
            "mapa_n": "Mapa",
            "version": "Versión",
            "sellado": "Archivada el",
            "issue": "Issue",
            "huella": "Huella",
            "file.name": "Diseño",
        },
        vistas=[
            Vista(tipo="table", nombre="Por mapa",
                  orden=["mapa_n", "version", "sellado", "file.name", "issue"],
                  agrupar_por=("mapa_n", "ASC")),
            Vista(tipo="table", nombre="Línea de tiempo",
                  orden=["sellado", "mapa_n", "version", "file.name", "huella"]),
            Vista(tipo="cards", nombre="Fichas",
                  orden=["file.name", "mapa_n", "version", "sellado"]),
        ],
    )


def _titulo_de(mapas: list[dict], mapa_n) -> str:
    for m in mapas:
        if int(m["n"]) == mapa_n:
            return m["titulo"]
    return "(mapa no declarado)"


def indice_de(base_rel: str, versiones, mapas, titular: str,
              fm_vault: dict, indice_de_incidencias: str | None = None) -> str:
    # El índice de incidencias es dato del proyecto, no de este generador: un
    # nombre de proyecto escrito dentro de una pieza vendorizable es lo que
    # obliga a copiarla y editarla, y así es como nace una divergencia.
    por_mapa = defaultdict(list)
    for p, fm in versiones:
        por_mapa[fm.get("mapa_n")].append((p, fm))
    bloques = []
    for mapa_n in sorted(por_mapa, key=lambda k: (k is None, k)):
        filas = "\n".join(
            f"- `v{fm.get('version')}` [[{p.stem}]] — archivada el "
            f"`{fm.get('sellado')}`"
            + (f" · issue `{fm['issue']}`"
               if str(fm.get("issue") or "—").strip() not in ("", "—") else "")
            for p, fm in sorted(por_mapa[mapa_n],
                                key=lambda par: par[1].get("version") or 0))
        bloques.append(f"### `{mapa_n:02d}` — {_titulo_de(mapas, mapa_n)}\n\n"
                       f"{filas}" if isinstance(mapa_n, int)
                       else f"### (sin `mapa_n`)\n\n{filas}")
    cuerpo = "\n\n".join(bloques) or "*(todavía no se ha archivado ningún diseño)*"
    area = "[" + ", ".join(fm_vault["area"]) + "]"
    tema = "[" + ", ".join(fm_vault["tema"]) + "]"
    vigentes = len(mapas)
    enlace_incidencias = (
        f"- [[{indice_de_incidencias}]] — la incidencia que motivó cada "
        f"rediseño\n" if indice_de_incidencias else "")
    return f"""---
tags: [indice, versiones, {titular.lower()}]
area: {area}
tema: {tema}
creado: {HOY}
actualizado: {HOY}
fuente: "docs/wiki/generar_versiones.py sobre lo que archivó docs/wiki/archivar.py"
resumen: "El histórico de diseños de los mapas de {titular}: {len(versiones)} versiones archivadas de {vigentes} mapas."
submapa: true
---

# Versiones de mapas de {titular}

**{len(versiones)} diseños archivados** de {vigentes} mapas. Cada uno es el
`.canvas` que estaba publicado **antes** de que el siguiente lo pisara, con una
nota que dice qué nodos nacieron, murieron o cambiaron de texto.

![[{base_rel}]]

## Los {len(versiones)} diseños

Una Base es una **consulta**: Obsidian la resuelve al dibujarla y no deja ningún
enlace en el fichero, así que sin esta lista el grafo del vault no tendría por
dónde llegar a estas notas. La tabla de arriba es para **filtrar**; esta lista
es la **arista**.

{cuerpo}

## Cómo nace una versión

Nadie la escribe. `publicar.py` compara el mapa del repo con el de la bóveda y,
si van a diferir, llama a `archivar.py` **antes** de copiar: guarda el vigente
aquí y sube el número en `wiki.lock.json`. Si el archivado no deja fichero, la
bóveda **no se toca** — perder el anterior para publicar el nuevo es exactamente
lo que esto impide.

```bash
python3 docs/wiki/publicar.py            # archiva y publica
python3 docs/wiki/generar_versiones.py   # comprueba el archivo y regenera esto
```

## Las cuatro reglas que impiden que esto deje de ser un archivo

1. **Cada `.canvas` archivado lleva su nota**, y cada nota su `.canvas`. Un
   lienzo suelto no dice de qué mapa es versión; una nota sin lienzo describe un
   hueco.
2. **`mapa_n` nombra un mapa declarado** en `docs/wiki/wiki.json`. Una versión de
   un mapa que nadie puede abrir no archiva nada.
3. **`version` es única por mapa.** Dos v1 del mismo mapa significan que una pisó
   a la otra — justo el defecto que este archivo existe para impedir.
4. **La `huella` es la del canvas archivado.** Es la regla que convierte esto en
   un archivo y no en una carpeta: si el lienzo se puede retocar sin que nada lo
   diga, el histórico deja de ser histórico y se sigue creyendo igual.

## Relacionado

- [[00 — Mapas de {titular}]] — los mapas **vigentes**, que es de lo que esto es historia
{enlace_incidencias}"""


# --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("origen", nargs="?", type=Path, default=AQUI)
    ap.add_argument("--simulacro", action="store_true")
    args = ap.parse_args(argv)

    origen = args.origen.resolve()
    manifiesto = json.loads((origen / "wiki.json").read_text(encoding="utf-8"))
    vault = Path(manifiesto["vault"])
    proyecto = manifiesto["proyecto"]
    titular = manifiesto["estructura"].get("mapas_de", proyecto)
    fm_vault = manifiesto["frontmatter"]
    mapas = manifiesto.get("mapas", [])
    if not vault.is_dir():
        print(f"✗ no existe el vault: {vault}")
        return 2

    carpeta = (vault / "wiki" / proyecto
               / manifiesto["estructura"].get(
                   "versiones", manifiesto["estructura"]["mapas"] + "/Versiones"))
    if not carpeta.is_dir():
        print(f"  · {carpeta.name}/ todavía no existe: no se ha archivado "
              f"ningún diseño. Nada que indexar.")
        return 0
    # El filtro de una Base es relativo a la raíz de bóveda, así que sin `.obsidian/`
    # por encima no hay filtro que escribir. Se dice aquí, que es donde se conoce
    # la ruta, y no cuatro llamadas más abajo en forma de excepción.
    if not raices_de_boveda(carpeta):
        print(f"  ✗ {carpeta} no está dentro de ninguna bóveda: no hay un "
              f"`.obsidian/` ni ahí ni por encima. Un filtro escrito sin raíz "
              f"conocida sale vacío y no lo dice.")
        return 2

    versiones = leer(carpeta)
    problemas = problemas_de(versiones, carpeta, mapas)
    for p in problemas:
        print(f"  ✗ {p}")

    base = base_de(carpeta, titular)
    ok, lineas = informe(base, vault)
    for l in lineas:
        print("  " + l)

    nombre_base = None
    for b in manifiesto.get("bases", []):
        if b.get("titulo") == f"Versiones de mapas de {titular}":
            nombre_base = f"{b['n']:02d} — {b['titulo']}.base"
    if nombre_base is None:
        # Dictar el remedio, no sólo el diagnóstico: es la misma cortesía que
        # `publicar.py` tiene con la nota puerta, y la diferencia entre un
        # callejón sin salida y un arreglo de treinta segundos.
        siguiente = max((b["n"] for b in manifiesto.get("bases", [])),
                        default=0) + 1
        print(f"  ✗ wiki.json no declara la base «Versiones de mapas de "
              f"{titular}»: sin número no se publica.")
        print("    Añade esto a `bases` (regla dura: lo archivado se indexa en "
              "la misma operación):")
        for l in json.dumps({
                "n": siguiente,
                "titulo": f"Versiones de mapas de {titular}",
                "fuente": f"{siguiente:02d} — Versiones de mapas de {titular}.base",
                "generador": "docs/wiki/generar_versiones.py",
                "tabula": ("el histórico de diseños: cada canvas que se archivó "
                           "antes de que el siguiente lo pisara"),
                "indice": f"00 — Versiones de mapas de {titular}",
                "gancho": "🗄️ el histórico de diseños",
        }, ensure_ascii=False, indent=2).splitlines():
            print("      " + l)
        return 1

    # Se publica sólo si la compuerta pasó. Avisar DESPUÉS de publicar es lo
    # que INC-006 reprocha a la compuerta de historial del vault.
    if problemas or not ok:
        print("  ✗ no se publica nada: primero se arregla lo de arriba.")
        return 1

    if not args.simulacro:
        (origen / nombre_base).write_text(base.a_yaml(), encoding="utf-8")
        print(f"  ✓ {nombre_base}")
        indice = carpeta / f"{INDICE.format(titular=titular)}.md"
        indice.write_text(
            # De quién es el tablero lo decide el manifiesto, no este fichero:
            # un proyecto con varios titulares hermanos tiene un tablero por
            # titular. Escribirlo como `{proyecto}` dejaba aquí un enlace a una
            # nota que nadie iba a crear. Ver `generar_incidencias.py`.
            indice_de(nombre_base, versiones, mapas, titular, fm_vault,
                      f"00 — Incidencias de "
                      f"{manifiesto['estructura'].get('incidencias_de', proyecto)}"),
            encoding="utf-8")
        print(f"  ✓ {indice.name}  ({len(versiones)} versión(es) archivada(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
