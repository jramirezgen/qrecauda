"""E5: los defectos inyectados son deterministas, hacen lo que dicen y no cambian lo que no deben."""

import numpy as np
import pytest

from qrecauda.adaptadores.defectos import FuenteConDefecto, MitigadorConDefecto, patron, persistencia
from qrecauda.adaptadores.prng import FuentePrng
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import h_min_con_defecto
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Muestra, Origen

BASE = Bits(np.random.default_rng(5).integers(0, 2, 200_000, dtype=np.uint8))


def test_persistencia_es_determinista_y_copia_con_la_probabilidad_pedida():
    a, b = persistencia(0.8, 3)(BASE), persistencia(0.8, 3)(BASE)
    assert a == b and a != persistencia(0.8, 4)(BASE)
    iguales = float(np.mean(a.datos[1:] == a.datos[:-1]))
    assert iguales == pytest.approx(0.8 + 0.2 * 0.5, abs=0.005)  # P(x | x) = copia + (1 − copia)·½
    assert persistencia(0.0, 3)(BASE) == BASE  # sin defecto, la identidad
    assert len(persistencia(0.5, 1)(Bits.desde([]))) == 0


def test_patron_impone_el_valor_con_su_peso():
    b = patron(0.9, "00001111", 3)(BASE)
    esperado = np.resize(np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.uint8), len(BASE))
    assert float(np.mean(b.datos == esperado)) == pytest.approx(0.9 + 0.1 * 0.5, abs=0.005)
    assert patron(0.0, "01", 3)(BASE) == BASE


def test_parametros_invalidos_abortan():
    for malo in (lambda: persistencia(1.5, 1), lambda: patron(0.5, "", 1), lambda: patron(0.5, "012", 1), lambda: patron(-0.1, "01", 1)):
        with pytest.raises(EntradaInvalida):
            malo()


def test_la_fuente_con_defecto_conserva_origen_y_forma():
    m = FuenteConDefecto(FuentePrng(2), persistencia(0.8, 9)).generar(4, 1000)
    assert (m.origen, m.qubits, m.shots, m.mitigada, len(m.bits)) == (Origen.PRNG_CLASICO, 4, 1000, False, 4000)


def test_el_mitigador_con_defecto_aplica_el_defecto_despues_y_la_deja_mitigada():
    class Identidad:
        def mitigar(self, m: Muestra) -> Muestra:
            return m.mitigada_con(m.bits, conserva_bits_por_disparo=True)

    cruda = FuentePrng(2).generar(4, 1000)
    mit = MitigadorConDefecto(Identidad(), persistencia(0.8, 9)).mitigar(cruda)
    assert mit.mitigada and mit.bits == persistencia(0.8, 9)(cruda.bits)


def test_h_analitica_de_los_defectos():
    assert h_min_con_defecto(0.0, 0.5) == pytest.approx(1.0)
    assert h_min_con_defecto(0.6, 0.5) == pytest.approx(0.3219, abs=1e-3)  # la Markov de permanencia 0,8 del spike S.04
    assert h_min_con_defecto(1.0, 0.5) == 0.0
    with pytest.raises(ValueError):
        h_min_con_defecto(0.5, 0.2)
