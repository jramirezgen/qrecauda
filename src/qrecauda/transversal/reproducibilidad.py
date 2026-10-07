"""Reproducibilidad: BLAS a un hilo FORZADO (no sólo comprobado) y captura del entorno para el manifiesto."""

from __future__ import annotations

import platform
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import metadata

from threadpoolctl import threadpool_info, threadpool_limits

from qrecauda.dominio.errores import EntradaInvalida


@contextmanager
def un_hilo() -> Iterator[None]:
    with threadpool_limits(limits=1):
        yield


def hilos_blas() -> dict[str, int]:
    """Hilos que usa ahora cada biblioteca BLAS/OpenMP cargada (clave `api:prefijo`)."""
    return {f"{i['internal_api']}:{i['prefix']}": int(i["num_threads"]) for i in threadpool_info()}


def verificar_un_hilo() -> None:
    """Comprobación, no sólo fuerza: un sello con BLAS multihilo cambia en la 15.ª cifra."""
    mal = {k: n for k, n in hilos_blas().items() if n != 1}
    if mal:
        raise EntradaInvalida(f"BLAS no está a un hilo: {mal}")


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
