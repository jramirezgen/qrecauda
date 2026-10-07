# -*- coding: utf-8 -*-
"""Antes de pisar un mapa de la bóveda, guarda el que había.

⛔ **El hueco, medido el 2026-09-08.** `publicar.py` copiaba el `.canvas` encima
del anterior; `wiki.lock.json` se reescribía entero y no llevaba versión. La
única historia de un diseño era el git del repo — que no se abre desde Obsidian,
y por tanto no existe para quien usa la bóveda. El usuario lo pidió por su
nombre: *«como es git, se tendrá que archivar … de manera de nunca perder los
diseños anteriores»*.

**Por qué el número de versión NO vive en `wiki.json`.** El plan lo proponía
ahí, y sería un campo a mano que hay que acordarse de subir en el mismo commit
que el canvas. Un número derivable que se declara a mano se desincroniza —es el
mismo error que este repo ya pagó con los conteos del vault—, así que la versión
se lleva en `wiki.lock.json`, que es **generado**: sube sola cuando la huella
cambia y no hay nada que olvidar. Lo que sí es dato del proyecto, y por eso sí
va en `wiki.json`, es **dónde** se archiva (`estructura.versiones`).

Nunca borra: sólo añade. Un archivo que puede perder algo no es un archivo.
"""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

HOY = date.today().isoformat()


def _nodos_de(texto: str) -> dict:
    """`{id: texto}` de los nodos de texto. Un canvas ilegible da `{}`."""
    try:
        canvas = json.loads(texto)
    except (json.JSONDecodeError, ValueError):
        return {}
    return {n["id"]: (n.get("text") or "")
            for n in canvas.get("nodes", []) if n.get("type") == "text"}


def _titulo_del_nodo(texto: str) -> str:
    """La primera línea con contenido, sin `#`. Es como se reconoce un nodo."""
    for linea in texto.splitlines():
        limpia = linea.strip().lstrip("#").strip()
        if limpia:
            return limpia[:70]
    return "(sin título)"


def que_cambio(viejo: str, nuevo: str) -> dict:
    """Qué nodos nacen, mueren y cambian de texto entre dos canvas.

    Es lo que hace útil una nota de versión: un `.canvas` archivado sin esto
    obliga a abrir los dos y compararlos a ojo, que es exactamente lo que nadie
    hace.
    """
    a, b = _nodos_de(viejo), _nodos_de(nuevo)
    return {
        "nacen": sorted(set(b) - set(a)),
        "mueren": sorted(set(a) - set(b)),
        "cambian": sorted(k for k in set(a) & set(b) if a[k] != b[k]),
        "titulos": {k: _titulo_del_nodo(v) for k, v in {**a, **b}.items()},
    }


def nombre_de_version(item: dict, version: int, cuando: str = HOY) -> str:
    return f"{item['n']:02d} — {item['titulo']} (v{version}, {cuando})"


def _nota_de_version(item: dict, version: int, huella: str, cambios: dict,
                     fichero: str, fm: dict) -> str:
    def _lista(vs):
        return "[" + ", ".join(f'"{v}"' for v in vs) + "]"

    def _renglones(ids, verbo):
        if not ids:
            return []
        return [f"### {verbo}"] + [
            f"- `{i}` — {cambios['titulos'].get(i, '(sin título)')}" for i in ids]

    cuerpo = (_renglones(cambios["nacen"], "Nodos que nacen en la versión siguiente")
              + _renglones(cambios["mueren"], "Nodos que ya no están")
              + _renglones(cambios["cambian"], "Nodos que cambiaron de texto"))
    if not cuerpo:
        cuerpo = ["El diseño cambió sin que ningún nodo naciera, muriera ni "
                  "cambiara de texto: se movió la geometría, los grupos o las "
                  "aristas."]
    return "\n".join([
        "---",
        f"mapa_n: {item['n']}",
        f"version: {version}",
        f"huella: {huella}",
        f"sellado: {HOY}",
        f"issue: {item.get('issue', '—')}",
        f"area: {_lista(fm.get('area', []))}",
        f"tema: {_lista(fm.get('tema', []))}",
        "tags: [mapa, version]",
        "---",
        "",
        f"# {item['titulo']} — versión {version}",
        "",
        f"Diseño vigente hasta el {HOY}, archivado al publicar el siguiente. "
        f"Esta nota dice **qué cambió**; debajo está el diseño tal cual estaba.",
        "",
        # El lienzo se transcluye y no se nombra en prosa: una nota que dice
        # «el canvas está en tal fichero» obliga a ir a buscarlo, y a esa
        # altura ya nadie compara nada. Obsidian abre un `.canvas` embebido.
        f"![[{fichero}]]",
        "",
        f"> Generado por `docs/wiki/archivar.py`. No se edita a mano: se "
        f"regenera solo la próxima vez que este mapa cambie.",
        "",
        *cuerpo,
        "",
    ])


def archivar(destino: Path, texto_nuevo: str, item: dict, dir_versiones: Path,
             version: int, fm: dict, *, simulacro: bool = False) -> dict | None:
    """Guarda el mapa vigente de la bóveda antes de que lo pisen.

    Devuelve qué se archivó, o `None` si no había nada que perder — el mapa aún
    no existe en la bóveda, o lo que hay es idéntico a lo que va a entrar.

    Lo que se archiva es **lo que la bóveda tiene**, no lo que el repo cree que
    tiene: si alguien lo editó a mano y se adoptó, ésa es la versión que se
    pierde y ésa es la que hay que guardar.
    """
    if not destino.is_file():
        return None
    vigente = destino.read_text(encoding="utf-8", errors="ignore")
    if vigente == texto_nuevo:
        return None

    nombre = nombre_de_version(item, version)
    cambios = que_cambio(vigente, texto_nuevo)
    from hashlib import sha256
    huella = sha256(vigente.encode("utf-8")).hexdigest()[:16]
    if not simulacro:
        dir_versiones.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destino, dir_versiones / f"{nombre}.canvas")
        (dir_versiones / f"{nombre}.md").write_text(
            _nota_de_version(item, version, huella, cambios,
                             f"{nombre}.canvas", fm), encoding="utf-8")
    return {"version": version, "huella": huella, "fichero": f"{nombre}.canvas",
            "nacen": len(cambios["nacen"]), "mueren": len(cambios["mueren"]),
            "cambian": len(cambios["cambian"])}
