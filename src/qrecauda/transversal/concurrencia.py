"""Concurrencia: candado de máquina para corridas pesadas (sellos, tiempos, relojes). El resto corre en paralelo."""

from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def candado(ruta: Path) -> Iterator[None]:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
