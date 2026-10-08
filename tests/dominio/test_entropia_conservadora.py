"""F5.05: el dimensionado conservador, a nivel de dominio (puro, sin binarios)."""

import pytest

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import EstimadorMCV, EstimadorMinimo, h_contable


class _Fija:
    def __init__(self, h: float) -> None:
        self.h, self.vistos = h, []

    def estimar(self, bits: Bits) -> float:
        self.vistos.append(len(bits))
        return self.h


def test_el_minimo_toma_la_cota_mas_baja():
    assert EstimadorMinimo([(_Fija(0.9), None), (_Fija(0.4), None), (_Fija(0.7), None)]).estimar(Bits.desde([0, 1] * 50)) == 0.4


def test_cada_cota_mira_su_prefijo_y_ninguna_se_omite():
    a, b = _Fija(0.9), _Fija(0.8)
    est = EstimadorMinimo([(a, None), (b, 30)])
    assert est.por_cota(Bits.desde([0, 1] * 50)) == (0.9, 0.8)
    assert (a.vistos, b.vistos) == ([100], [30])


def test_una_cota_que_falla_propaga_su_error():
    class Rota:
        def estimar(self, bits: Bits) -> float:
            raise RuntimeError("no hay muestra")

    with pytest.raises(RuntimeError):
        EstimadorMinimo([(EstimadorMCV(), None), (Rota(), None)]).estimar(Bits.desde([0, 1] * 50))


def test_sin_cotas_no_hay_estimador():
    with pytest.raises(ValueError):
        EstimadorMinimo([])


def test_contabilidad_nunca_sube_la_cota_del_pool():
    assert h_contable(0.9, 1000, 1.0, 3000) == 0.9  # la fuente sobra: manda el pool
    assert h_contable(0.9, 1000, 0.1, 3000) == pytest.approx(0.3)  # la fuente es pobre: 0,1·3000/1000
    assert h_contable(0.2, 1000, 0.5, 3000) == 0.2


def test_contabilidad_rechaza_entradas_vacias():
    with pytest.raises(ValueError):
        h_contable(0.5, 0, 0.5, 10)
