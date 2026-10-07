"""F5.01: nistrng contra el validador propio (D-006). El contraste vive aquí porque los adaptadores no se importan (C2)."""

import numpy as np
import pytest
from scipy.stats import chisquare

from qrecauda.adaptadores import estadistica, nist
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida, EntropiaInsuficiente
from qrecauda.dominio.metricas import Metrica

N_SECUENCIAS = 100
LONGITUD = 2000


def _secuencias(p1: float = 0.5) -> list[Bits]:
    return [Bits((np.random.default_rng(1000 + s).random(LONGITUD) < p1).astype(np.uint8)) for s in range(N_SECUENCIAS)]


def test_monobit_coincide_con_estadistica_en_100_secuencias():
    for b in _secuencias():
        assert abs(nist.p_monobit(b) - estadistica.p_monobit(b)) < 1e-6


def test_runs_coincide_con_estadistica_en_100_secuencias_incluidas_las_sesgadas():
    for p1 in (0.5, 0.52):  # con 0,52 y n=2000 buena parte incumple el prerrequisito: ambos devuelven 0
        for b in _secuencias(p1):
            assert abs(nist.p_runs(b) - estadistica.p_runs(b)) < 1e-6


def test_runs_sin_prerrequisito_de_frecuencia_vale_cero():
    assert nist.p_runs(Bits.desde([1] * 900 + [0] * 100)) == 0.0


def _p_bloques_con_scipy(b: Bits) -> float:
    """Frecuencia por bloques (SP 800-22 §2.2) con scipy: casillas (unos, ceros) de cada bloque, ddof para dar N grados."""
    n = len(b)
    nb = n // 20
    m = 20
    if nb >= 100:
        nb = 99
        m = n // nb
    bloques = b.datos[: nb * m].reshape(nb, m)
    unos = bloques.sum(axis=1)
    obs = np.concatenate([unos, m - unos])
    return float(chisquare(obs, f_exp=np.full(2 * nb, m / 2), ddof=nb - 1).pvalue)


def test_m5_frecuencia_por_bloques_coincide_con_scipy_chisquare():
    for b in _secuencias(0.5) + _secuencias(0.55)[:20]:
        assert nist.p_frecuencia_por_bloques(b) == pytest.approx(_p_bloques_con_scipy(b), abs=1e-6)


def test_frecuencia_por_bloques_exige_100_bits():
    with pytest.raises(EntropiaInsuficiente):
        nist.p_frecuencia_por_bloques(Bits.desde([0, 1] * 20))


def test_validador_devuelve_m3_m4_m5_y_aprueba_una_secuencia_buena():
    medidas = nist.ValidadorNist().evaluar(_secuencias()[0])
    assert [m.metrica for m in medidas] == [Metrica.MONOBIT, Metrica.RUNS, Metrica.CHI2]
    assert all(m.cumple for m in medidas)


def test_validador_rechaza_una_secuencia_sesgada():
    veredicto = nist.ValidadorNist().evaluar(_secuencias(0.6)[0])
    assert not any(m.cumple for m in veredicto)


def test_proporcion_de_aprobados_intervalo_de_nist_para_100_secuencias():
    p = nist.proporcion_aprobados([0.5] * 98 + [0.001] * 2)
    assert (p.aprobados, p.total, p.proporcion) == (98, 100, 0.98)
    assert p.minimo == pytest.approx(0.99 - 3 * (0.01 * 0.99 / 100) ** 0.5)  # 0,9602
    assert p.maximo == pytest.approx(0.99 + 3 * (0.01 * 0.99 / 100) ** 0.5)
    assert p.cumple


def test_proporcion_baja_incumple_aunque_cada_p_individual_sea_plausible():
    assert not nist.proporcion_aprobados([0.5] * 95 + [0.005] * 5).cumple


def test_proporcion_de_100_secuencias_aleatorias_cumple_en_las_tres_pruebas():
    seqs = _secuencias()
    for prueba in (nist.p_monobit, nist.p_runs, nist.p_frecuencia_por_bloques):
        assert nist.proporcion_aprobados([prueba(b) for b in seqs]).cumple, prueba.__name__


def test_proporcion_entradas_ilegales():
    with pytest.raises(EntradaInvalida):
        nist.proporcion_aprobados([])
    with pytest.raises(EntradaInvalida):
        nist.proporcion_aprobados([0.5], alfa=1.5)
