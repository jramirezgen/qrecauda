"""Los tests que corren el 90B real se saltan con un mensaje claro si falta el binario, SALVO en CI (allí faltar es un fallo)."""

import os

import pytest

from qrecauda.adaptadores.min_entropia import BINARIO_POR_DEFECTO, INSTRUCCION_BUILD

NECESITAN_90B = ("recorre_la_cadena",)  # e3 y e3b con las piezas reales


def pytest_runtest_setup(item: pytest.Item) -> None:
    if os.environ.get("CI") or not any(m in item.name for m in NECESITAN_90B):
        return
    if not BINARIO_POR_DEFECTO.is_file():
        pytest.skip(f"falta el binario del 90B ({BINARIO_POR_DEFECTO}); compílalo con: {INSTRUCCION_BUILD}")
