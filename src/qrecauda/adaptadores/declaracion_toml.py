"""Declaración desde TOML: lee `declaraciones/<X>.toml`, la funde con lo que `hereda` y comprueba que existe su preinscripción."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path

from qrecauda.datos import Declaracion
from qrecauda.dominio.errores import EntradaInvalida


def _leer(ruta: Path, raiz: Path, rutas: list[str]) -> dict[str, object]:
    rel = ruta.as_posix()
    if rel in rutas:
        raise EntradaInvalida(f"herencia circular en {rel}")
    rutas.append(rel)
    try:
        propio = tomllib.loads((raiz / ruta).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise EntradaInvalida(f"no se puede leer la declaración {rel}: {exc}") from exc
    padre = propio.pop("hereda", None)
    base = _leer(Path(str(padre)), raiz, rutas) if padre else {}
    fusion: dict[str, object] = dict(base)
    for k, v in propio.items():
        previo = fusion.get(k)
        fusion[k] = {**previo, **v} if isinstance(previo, Mapping) and isinstance(v, Mapping) else v
    return fusion


def cargar_declaracion(ruta: Path, raiz: Path) -> Declaracion:
    """`ruta` es relativa a `raiz` (la raíz del repo). Sin preinscripción en `docs/preinscripciones/<id>.md` no hay declaración."""
    rutas: list[str] = []
    mapa = _leer(ruta, raiz, rutas)
    exp = mapa.get("experimento")
    eureka = str(exp.get("id", "")) if isinstance(exp, Mapping) else ""
    pre = f"docs/preinscripciones/{eureka}.md"
    if not eureka or not (raiz / pre).is_file():
        raise EntradaInvalida(f"la declaración {ruta} no tiene preinscripción ({pre}): se fija ANTES de correr")
    return Declaracion.desde_mapa(mapa, (*rutas, pre))
