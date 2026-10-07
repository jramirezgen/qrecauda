"""Vectores publicados en NIST SP 800-22 rev1a (§2.1.8, §2.3.8): fijan el validador propio contra la fuente, no contra otra
implementación de las mismas fórmulas (hallazgo R.00-3)."""

import pytest

from qrecauda.adaptadores.estadistica import p_monobit, p_runs
from qrecauda.dominio.bits import Bits

# el ε de 100 bits de los ejemplos de NIST
CIEN = "1100100100001111110110101010001000100001011010001100001000110100110001001100011001100010100010111000"


def _b(s: str) -> Bits:
    return Bits.desde([int(c) for c in s])


@pytest.mark.parametrize(
    ("secuencia", "esperado"),
    [("1011010101", 0.527089), (CIEN, 0.109599)],
)
def test_monobit_reproduce_los_ejemplos_de_nist(secuencia, esperado):
    assert p_monobit(_b(secuencia)) == pytest.approx(esperado, abs=1e-6)


@pytest.mark.parametrize(
    ("secuencia", "esperado"),
    [("1001101011", 0.147232), (CIEN, 0.500798)],
)
def test_runs_reproduce_los_ejemplos_de_nist(secuencia, esperado):
    assert p_runs(_b(secuencia)) == pytest.approx(esperado, abs=1e-6)
