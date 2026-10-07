import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import min_entropia_mcv, sesgo
from qrecauda.dominio.errores import EntradaInvalida, EntropiaInsuficiente
from qrecauda.dominio.extractores import longitud_segura, peres, toeplitz, von_neumann

lista_bits = st.lists(st.integers(0, 1), min_size=0, max_size=400)


def test_bits_rechaza_lo_que_no_es_bit():
    with pytest.raises(EntradaInvalida):
        Bits.desde([0, 1, 2])
    with pytest.raises(EntradaInvalida):
        Bits(np.zeros((2, 2), dtype=np.uint8))


def test_bits_es_inmutable_y_no_congela_el_array_del_llamante():
    a = np.array([0, 1, 1], dtype=np.uint8)
    b = Bits(a)
    a[0] = 1  # el llamante sigue pudiendo escribir
    assert b.datos[0] == 0  # y Bits no cambió
    with pytest.raises(ValueError):
        b.datos[0] = 1


def test_bytes_ida_y_vuelta():
    assert Bits.desde_bytes(b"\xa5\x0f").a_bytes() == b"\xa5\x0f"
    with pytest.raises(EntradaInvalida):
        Bits.desde([1, 0, 1]).a_bytes()


def test_von_neumann_caso_conocido():
    assert von_neumann(Bits.desde([0, 1, 1, 0, 0, 0, 1, 1])) == Bits.desde([0, 1])


@given(lista_bits)
def test_von_neumann_no_alarga_y_peres_no_pierde(xs):
    b = Bits.desde(xs)
    assert len(von_neumann(b)) <= len(b) // 2
    assert len(peres(b)) >= len(von_neumann(b))


def test_von_neumann_quita_el_sesgo():
    rng = np.random.default_rng(1)
    sesgado = Bits((rng.random(200_000) < 0.8).astype(np.uint8))
    assert sesgo(sesgado) > 0.29
    assert sesgo(von_neumann(sesgado)) < 0.01


def test_longitud_segura_y_sus_bordes():
    assert longitud_segura(1000, 0.9, 2.0**-64) == 1000 * 0.9 // 1 - 128 + (0 if (1000 * 0.9) % 1 == 0 else 0)
    with pytest.raises(EntropiaInsuficiente):
        longitud_segura(100, 0.5, 2.0**-64)
    for epsilon in (0.0, 1.0, -1.0):
        with pytest.raises(EntradaInvalida):
            longitud_segura(1000, 0.9, epsilon)


def test_toeplitz_es_lineal_sobre_gf2():
    rng = np.random.default_rng(2)
    n, m = 64, 20
    s = Bits(rng.integers(0, 2, n + m - 1, dtype=np.uint8))
    x = Bits(rng.integers(0, 2, n, dtype=np.uint8))
    y = Bits(rng.integers(0, 2, n, dtype=np.uint8))
    suma = Bits(x.datos ^ y.datos)
    assert toeplitz(suma, s, m) == Bits(toeplitz(x, s, m).datos ^ toeplitz(y, s, m).datos)


def test_toeplitz_exige_semilla_del_tamano_exacto():
    with pytest.raises(EntradaInvalida):
        toeplitz(Bits.desde([1] * 8), Bits.desde([0] * 5), 4)


def test_min_entropia_balanceada_alta_y_sesgada_baja():
    rng = np.random.default_rng(3)
    assert min_entropia_mcv(Bits(rng.integers(0, 2, 100_000, dtype=np.uint8))) > 0.98
    assert min_entropia_mcv(Bits((rng.random(100_000) < 0.9).astype(np.uint8))) < 0.2


def _toeplitz_denso(x, s, m):
    """Referencia ingenua: T[i, j] = s[n-1+i-j], producto mod 2 con enteros exactos (sin FFT)."""
    import numpy as np

    n = len(x)
    T = np.array([[s[n - 1 + i - j] for j in range(n)] for i in range(m)], dtype=np.int64)
    return (T @ np.asarray(x, dtype=np.int64)) % 2


def test_toeplitz_coincide_con_la_matriz_densa_mod_2():
    import numpy as np

    rng = np.random.default_rng(5)
    for n, m in [(8, 3), (33, 20), (64, 64), (100, 1)]:
        x = rng.integers(0, 2, n, dtype=np.uint8)
        s = rng.integers(0, 2, n + m - 1, dtype=np.uint8)
        esperado = _toeplitz_denso(x, s, m)
        assert (toeplitz(Bits(x), Bits(s), m).datos == esperado).all(), (n, m)


def test_toeplitz_por_fft_es_exacto_a_n_grande():
    """matmul_toeplitz usa FFT en float: a n ≥ 2e5 el redondeo de np.rint no puede cambiar ni un bit."""
    import numpy as np

    n, m = 200_000, 50_000
    rng = np.random.default_rng(9)
    x = rng.integers(0, 2, n, dtype=np.uint8)
    s = rng.integers(0, 2, n + m - 1, dtype=np.uint8)
    y = toeplitz(Bits(x), Bits(s), m).datos
    # comprobación exacta de 200 filas elegidas al azar contra enteros
    for i in rng.integers(0, m, 200):
        fila = s[n - 1 + i - np.arange(n)]
        assert int((fila.astype(np.int64) @ x.astype(np.int64)) % 2) == int(y[i]), i
