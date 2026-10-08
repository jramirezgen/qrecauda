"""Fuentes sintéticas de C.E1d (adaptadores/prng): deterministas y con el defecto que dicen tener (analítico, tolerancias holgadas)."""

import pytest

from qrecauda.adaptadores.prng import FuenteMarkov, FuentePeriodica, FuentePrng
from qrecauda.dominio.entropia import min_entropia_mcv
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Origen

N = 200_000


def test_sesgada_por_el_sesgo_de_la_fuente_prng_da_la_proporcion_pedida():
    m = FuentePrng(1, sesgo=0.2).generar(1, N)  # p(1) = 0,7, como el spike S.04
    assert abs(m.bits.proporcion_de_unos() - 0.7) < 0.01


def test_periodica_repite_el_patron_y_su_proporcion_es_un_medio():
    m = FuentePeriodica("00001111").generar(1, 20)
    assert "".join(map(str, m.bits.datos)) == "00001111000011110000" and m.origen is Origen.PRNG_CLASICO
    assert FuentePeriodica("00001111").generar(8, N // 8).bits.proporcion_de_unos() == 0.5


def test_markov_cambia_con_probabilidad_uno_menos_la_permanencia_y_es_determinista():
    m = FuenteMarkov(3, 0.8).generar(1, N)
    b = m.bits.datos
    assert abs(float((b[1:] != b[:-1]).mean()) - 0.2) < 0.01 and m.bits == FuenteMarkov(3, 0.8).generar(1, N).bits
    assert m.bits != FuenteMarkov(4, 0.8).generar(1, N).bits


def test_el_mcv_no_ve_la_markov_y_si_ve_la_sesgada():
    """La tesis de la discrepancia 8: el MCV deja pasar la Markov (h real 0,322) porque mira sólo la frecuencia."""
    assert min_entropia_mcv(FuenteMarkov(3, 0.8).generar(1, N).bits) > 0.9
    assert min_entropia_mcv(FuentePrng(3, sesgo=0.2).generar(1, N).bits) < 0.55


@pytest.mark.parametrize(
    "malo", [lambda: FuenteMarkov(1, -0.1), lambda: FuenteMarkov(1, 1.1), lambda: FuentePeriodica("012"), lambda: FuentePeriodica("")]
)
def test_entradas_invalidas(malo):
    with pytest.raises(EntradaInvalida):
        malo()
