"""F5.02: min-entropía SP 800-90B (ea_non_iid oficial, S.04). Los tests con binario se saltan si no está compilado."""

import math
from pathlib import Path

import numpy as np
import pytest

from qrecauda.adaptadores.min_entropia import BINARIO_POR_DEFECTO, MUESTRAS_MIN, EstimadorNist90B
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import min_entropia_mcv
from qrecauda.dominio.errores import EntropiaInsuficiente, FuenteNoDisponible

N = MUESTRAS_MIN
SEMILLA = 20261007
necesita_binario = pytest.mark.skipif(not BINARIO_POR_DEFECTO.is_file(), reason="falta ea_non_iid: bash spikes/S04_90b/build_nist.sh")


def test_menos_de_un_millon_de_muestras_es_entropia_insuficiente():
    with pytest.raises(EntropiaInsuficiente):
        EstimadorNist90B().estimar(Bits.desde([0, 1] * 1000))


def test_sin_binario_falla_con_la_instruccion_de_build():
    est = EstimadorNist90B(binario=Path("/no/existe/ea_non_iid"))
    with pytest.raises(FuenteNoDisponible, match="build_nist.sh"):
        est.estimar(Bits(np.zeros(N, dtype=np.uint8)))


@necesita_binario
def test_iid_sesgada_da_la_cota_conservadora_de_s04():
    rng = np.random.default_rng(SEMILLA)
    b = Bits((rng.random(N) < 0.7).astype(np.uint8))
    h = EstimadorNist90B().estimar(b)
    assert h == pytest.approx(0.322, abs=0.01)
    assert h <= -math.log2(0.7) + 0.01  # nunca por encima de la teórica (0,515): es cota inferior
    assert min_entropia_mcv(b) > h  # MCV no ve la estructura que sí ve la batería


@necesita_binario
def test_markov_con_permanencia_08_da_h_menor_o_igual_04_y_mcv_no_la_ve():
    rng = np.random.default_rng(SEMILLA)
    b = Bits((np.cumsum(rng.random(N) < 0.2) % 2).astype(np.uint8))
    assert EstimadorNist90B().estimar(b) <= 0.4
    assert min_entropia_mcv(b) > 0.9  # el hallazgo R.00-2: MCV es ciega a la dependencia


@necesita_binario
def test_periodica_da_cero():
    b = Bits((np.arange(N) % 8 < 4).astype(np.uint8))
    assert EstimadorNist90B().estimar(b) == pytest.approx(0.0, abs=1e-6)
