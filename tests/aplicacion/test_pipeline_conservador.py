"""F5.05: el dimensionado conservador en el pipeline. Contrato (sin binario) y regresión (con el 90B real, si está compilado).

Regresión: sin los estimadores nuevos el pipeline es el de 0.1.0, bit a bit (las eurekas E1–E3b se midieron así y no se repiten).
"""

import pytest

from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.min_entropia import BINARIO_POR_DEFECTO, MUESTRAS_MIN, EstimadorNist90B
from qrecauda.adaptadores.prng import FuenteMarkov, FuentePrng
from qrecauda.aplicacion.pipeline import ParametrosPipeline, ejecutar
from qrecauda.dominio.entropia import EstimadorMCV, EstimadorMinimo
from qrecauda.dominio.errores import EntropiaInsuficiente
from qrecauda.transversal.observabilidad import RelojMonotonico

necesita_binario = pytest.mark.skipif(not BINARIO_POR_DEFECTO.is_file(), reason="falta ea_non_iid: bash spikes/S04_90b/build_nist.sh")
P = ParametrosPipeline(qubits=8, shots=40_000)


class _Fija:
    def __init__(self, h: float) -> None:
        self.h = h

    def estimar(self, bits) -> float:
        return self.h


def _corre(fuente, **kw):
    return ejecutar(fuente, ValidadorEstadistico(), RelojMonotonico(), P, **kw)


def test_regresion_sin_estimadores_nuevos_es_el_pipeline_de_0_1_0():
    a = _corre(FuentePrng(7))
    b = _corre(FuentePrng(7), estimador=EstimadorMCV())
    assert a.clave.datos.tobytes() == b.clave.datos.tobytes()
    assert (a.h_min, a.h_fuente) == (b.h_min, None)


def test_un_minimo_mas_bajo_acorta_la_clave_y_nunca_la_alarga():
    base = _corre(FuentePrng(7))
    mas_bajo = _corre(FuentePrng(7), estimador=EstimadorMinimo([(EstimadorMCV(), None), (_Fija(0.5), None)]))
    assert mas_bajo.h_min == 0.5 and len(mas_bajo.clave) < len(base.clave)
    mas_alto = _corre(FuentePrng(7), estimador=EstimadorMinimo([(EstimadorMCV(), None), (_Fija(0.99999), None)]))
    assert len(mas_alto.clave) <= len(base.clave)  # el mínimo nunca supera a la cota MCV sola


def test_la_contabilidad_de_fuente_acota_la_entropia_total():
    r = _corre(FuentePrng(7), estimador_de_fuente=_Fija(0.1))
    assert r.h_fuente == 0.1
    assert r.h_min == pytest.approx(0.1 * r.bits_crudos / r.bits_extraidos)
    assert len(r.clave) < 0.1 * r.bits_crudos  # y la clave cabe en la entropía total de la muestra


def test_la_salida_se_mide_con_su_propio_estimador():
    class Falla:
        def estimar(self, bits) -> float:
            raise EntropiaInsuficiente("el 90B no cabe en la clave")

    with pytest.raises(EntropiaInsuficiente):
        _corre(FuentePrng(7), estimador=Falla())
    r = _corre(FuentePrng(7), estimador=_Fija(0.8), estimador_de_salida=EstimadorMCV())
    assert r.h_min == 0.8 and r.h_min_salida > 0.9


@necesita_binario
def test_con_el_90b_real_una_fuente_con_persistencia_da_clave_mas_corta_que_con_mcv():
    """El hallazgo R.00-1 en pequeño: con MCV la clave de una cadena de Markov se dimensiona como si fuera ideal."""
    p = ParametrosPipeline(qubits=8, shots=400_000)  # 3,2 M de bits: el pool de Peres supera el millón del 90B
    est90 = EstimadorNist90B()
    cons = EstimadorMinimo([(EstimadorMCV(), None), (est90, MUESTRAS_MIN)])
    val = ValidadorEstadistico()
    mcv = ejecutar(FuenteMarkov(11, 0.8), val, RelojMonotonico(), p)
    nuevo = ejecutar(
        FuenteMarkov(11, 0.8), val, RelojMonotonico(), p,
        estimador=cons, estimador_de_fuente=EstimadorMinimo([(est90, MUESTRAS_MIN)]), estimador_de_salida=EstimadorMCV(),
    )  # fmt: skip
    assert len(nuevo.clave) < 0.5 * len(mcv.clave)
    assert nuevo.h_min < 0.5 < mcv.h_min
    assert len(nuevo.clave) <= 0.322 * nuevo.bits_crudos  # y cabe en la entropía analítica de la cadena (−log2 0,8 por bit)


@necesita_binario
def test_con_el_90b_real_la_fuente_ideal_conserva_la_mayor_parte_de_su_clave():
    """Del otro lado: el control no puede rechazar ni mutilar lo bueno."""
    p = ParametrosPipeline(qubits=8, shots=400_000)
    est90 = EstimadorNist90B()
    cons = EstimadorMinimo([(EstimadorMCV(), None), (est90, MUESTRAS_MIN)])
    val = ValidadorEstadistico()
    mcv = ejecutar(FuentePrng(11), val, RelojMonotonico(), p)
    nuevo = ejecutar(
        FuentePrng(11), val, RelojMonotonico(), p,
        estimador=cons, estimador_de_fuente=EstimadorMinimo([(est90, MUESTRAS_MIN)]), estimador_de_salida=EstimadorMCV(),
    )  # fmt: skip
    assert nuevo.veredicto.calidad_de_clave_aprobada
    assert 0.75 * len(mcv.clave) <= len(nuevo.clave) <= len(mcv.clave)


@necesita_binario
def test_sin_muestra_suficiente_para_el_90b_el_pipeline_aborta():
    est90 = EstimadorNist90B()
    with pytest.raises(EntropiaInsuficiente, match="800-90B"):
        _corre(FuentePrng(7), estimador=EstimadorMinimo([(EstimadorMCV(), None), (est90, MUESTRAS_MIN)]))
