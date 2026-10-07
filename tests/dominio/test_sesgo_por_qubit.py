import numpy as np
import pytest

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.sesgo_por_qubit import frecuencias_de_unos, sesgo_maximo, sesgo_medio


def test_frecuencias_por_qubit_en_orden_qubit_mayor():
    # qubit 0: 1,1,1,0 -> 0.75 ; qubit 1: 0,0,0,0 -> 0.0
    p = frecuencias_de_unos(Bits(np.array([1, 1, 1, 0, 0, 0, 0, 0], dtype=np.uint8)), 2)
    assert p.tolist() == [0.75, 0.0]
    assert sesgo_medio(p) == pytest.approx((0.25 + 0.5) / 2) and sesgo_maximo(p) == 0.5


def test_el_pooled_cancela_pero_el_maximo_no():
    p = np.array([0.55, 0.45])
    assert abs(p.mean() - 0.5) == 0.0 and sesgo_maximo(p) == pytest.approx(0.05)


def test_no_se_reparte_lo_que_no_cuadra():
    with pytest.raises(EntradaInvalida):
        frecuencias_de_unos(Bits(np.zeros(7, dtype=np.uint8)), 2)
