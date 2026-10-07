"""Reproducibilidad: BLAS a un hilo FORZADO (no sólo comprobado) y captura del entorno para el manifiesto."""

from __future__ import annotations

import platform
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import metadata

from threadpoolctl import threadpool_limits


@contextmanager
def un_hilo() -> Iterator[None]:
    with threadpool_limits(limits=1):
        yield


def entorno(
    paquetes: tuple[str, ...] = ("numpy", "scipy", "qiskit", "qiskit-aer", "qiskit-ibm-runtime", "mthree", "nistrng"),
) -> dict[str, str]:
    """Versiones exactas de lo que está instalado (el notebook y el manifiesto las citan)."""
    versiones = {}
    for p in paquetes:
        try:
            versiones[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            versiones[p] = "no instalado"
    return {"python": sys.version.split()[0], "plataforma": platform.platform(), **versiones}
