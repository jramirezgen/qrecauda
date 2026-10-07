"""Libro de veredictos: JSON-lines canónico que sólo se añade (puerto `LibroDeVeredictos`)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from qrecauda.datos import serializar


class LibroJsonl:
    """Implementa `LibroDeVeredictos`. Abre en modo añadir y sincroniza: una línea escrita no se reescribe."""

    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta

    def anadir(self, linea: Mapping[str, object]) -> None:
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._ruta.open("a", encoding="utf-8") as f:
            f.write(serializar(linea) + "\n")
            f.flush()
            os.fsync(f.fileno())
