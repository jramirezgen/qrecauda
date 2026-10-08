"""El registro de claves consumidas es de proceso (B-1): cada test parte con él vacío para que no se influyan."""

import pytest

from qrecauda.adaptadores.aes_gcm import olvidar_consumo


@pytest.fixture(autouse=True)
def _consumo_limpio():
    olvidar_consumo()
    yield
    olvidar_consumo()
