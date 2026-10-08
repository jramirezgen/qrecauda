"""Reproducibilidad: BLAS a un hilo FORZADO (no sólo comprobado) y captura del entorno para el manifiesto."""

from __future__ import annotations

import os
import platform
import sys
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from importlib import metadata
from typing import Any

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


# ------------------------------------------------------------------ F6.03: un proceso, un núcleo, un hilo

_LIMITE_DEL_PROCESO: Any = None  # el limitador de threadpoolctl se queda vivo mientras viva el proceso


def un_hilo_en_este_proceso() -> None:
    """BLAS/OpenMP a un hilo para TODA la vida del proceso (el productor no tiene un `with` que lo envuelva)."""
    global _LIMITE_DEL_PROCESO
    _LIMITE_DEL_PROCESO = threadpool_limits(limits=1)


def afinidad() -> tuple[int, ...]:
    """Núcleos en que este proceso puede correr ahora."""
    return tuple(sorted(os.sched_getaffinity(0)))


def fijar_afinidad(nucleo: int, permitidos: Collection[int] | None = None) -> tuple[int, ...]:
    """Fija este proceso a UN núcleo. Falla si el núcleo no existe o no está permitido (nada se fija en silencio a otro).

    `permitidos`: los núcleos de la máquina que se declararon antes de fijar a nadie. Un proceso hijo hereda la fijación de su padre
    (un solo núcleo), así que no puede validarse contra la suya; el kernel (cpuset) sigue siendo el último juez."""
    permitidos = os.sched_getaffinity(0) if permitidos is None else set(permitidos)
    if nucleo not in permitidos:
        raise EntradaInvalida(f"el núcleo {nucleo} no está entre los permitidos de este proceso: {sorted(permitidos)}")
    os.sched_setaffinity(0, {nucleo})
    return afinidad()


@contextmanager
def nucleo_fijo(nucleo: int) -> Iterator[tuple[int, ...]]:
    """Fija este proceso a `nucleo` mientras dure el bloque y restaura la afinidad previa. Los procesos que cree heredan la fijación."""
    previa = os.sched_getaffinity(0)
    efectiva = fijar_afinidad(nucleo)
    try:
        yield efectiva
    finally:
        os.sched_setaffinity(0, previa)
