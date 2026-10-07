"""Observabilidad: reloj real, bitácora JSON-lines y coste por etapa (tiempo y memoria pico) para el manifiesto."""

from __future__ import annotations

import json
import sys
import time
import tracemalloc
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TextIO


class RelojMonotonico:
    """Implementa `Reloj`."""

    def ahora_ns(self) -> int:
        return time.perf_counter_ns()


_SENSIBLES = ("token", "secret", "secreto", "password", "clave", "key", "credencial")


def _es_sensible(campo: str) -> bool:
    """Una ruta (`*_ruta`, `*_file`) nombra dónde está el secreto, no es el secreto."""
    c = campo.lower()
    return any(s in c for s in _SENSIBLES) and not c.endswith(("_ruta", "_file", "_path"))


class BitacoraJsonl:
    """Implementa `Bitacora`: una línea JSON por evento, nunca un secreto (seguridad.describir)."""

    def __init__(self, salida: TextIO | None = None) -> None:
        self._salida = salida or sys.stderr

    def registrar(self, evento: str, **campos: object) -> None:
        seguros = {k: "<oculto>" if _es_sensible(k) else v for k, v in campos.items()}
        self._salida.write(json.dumps({"evento": evento, **seguros}, sort_keys=True, default=str) + "\n")


@dataclass(slots=True)
class CosteEtapa:
    etapa: str
    segundos: float = 0.0
    pico_bytes: int = 0


@contextmanager
def medir_etapa(etapa: str, bitacora: BitacoraJsonl | None = None) -> Iterator[CosteEtapa]:
    coste = CosteEtapa(etapa)
    ya = tracemalloc.is_tracing()
    if not ya:
        tracemalloc.start()
    t0 = time.perf_counter()
    try:
        yield coste
    finally:
        coste.segundos = time.perf_counter() - t0
        coste.pico_bytes = tracemalloc.get_traced_memory()[1]
        if not ya:
            tracemalloc.stop()
        if bitacora is not None:
            bitacora.registrar("etapa", etapa=etapa, segundos=coste.segundos, pico_bytes=coste.pico_bytes)
