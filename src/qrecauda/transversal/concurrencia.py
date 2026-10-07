"""Concurrencia: candado de máquina para corridas pesadas (sellos, tiempos, relojes). El resto corre en paralelo."""

from __future__ import annotations

import fcntl
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from qrecauda.dominio.errores import CandadoOcupado

_SONDEO_S = 0.05


@contextmanager
def candado(ruta: Path, espera_s: float | None = None) -> Iterator[None]:
    """flock exclusivo sobre `ruta`. `espera_s=None` bloquea; un número acota la espera y lanza `CandadoOcupado`.

    El SO suelta el flock si el proceso muere, así que un candado huérfano no puede quedar colgado."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w") as f:
        if espera_s is None:
            fcntl.flock(f, fcntl.LOCK_EX)
        else:
            limite = time.monotonic() + espera_s
            while True:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= limite:
                        raise CandadoOcupado(f"{ruta} ocupado tras {espera_s} s") from None
                    time.sleep(_SONDEO_S)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
