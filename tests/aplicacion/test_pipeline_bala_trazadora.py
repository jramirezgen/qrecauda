"""Bala trazadora: de la fuente a la clave con el PRNG como fuente. El PRNG puede pasar los tests estadísticos:
eso NO prueba origen cuántico, y la muestra lo dice (`reclama_origen_cuantico`)."""

from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.prng import FuentePrng
from qrecauda.aplicacion.pipeline import ParametrosPipeline, ejecutar
from qrecauda.dominio.entropia import sesgo
from qrecauda.transversal.observabilidad import RelojMonotonico


def test_de_punta_a_punta_con_fuente_sesgada():
    p = ParametrosPipeline(qubits=8, shots=40_000)
    r = ejecutar(FuentePrng(7, sesgo=0.1), ValidadorEstadistico(), RelojMonotonico(), p)
    assert len(r.clave) > 50_000
    assert r.veredicto.medidas, "un veredicto sin medidas no prueba nada"
    assert not r.muestra.reclama_origen_cuantico
    assert sesgo(r.muestra.bits) > 0.09  # la fuente de entrada SÍ estaba sesgada…
    assert r.h_min > 0.95  # …y Peres la dejó con casi 1 bit de min-entropía por bit


def test_las_medidas_se_toman_en_tres_puntos_y_la_cruda_sesgada_no_pasa():
    """Hallazgo R.00-1: con p(1)=0,9 la clave pasa M1–M5 por Toeplitz; la muestra cruda NO. Sin medir ambas, E1 no discrimina."""
    from qrecauda.dominio.bits import Bits
    from qrecauda.dominio.metricas import Metrica
    from qrecauda.dominio.muestra import Muestra, Origen

    class Pasa:  # mitigador de prueba: devuelve una muestra equilibrada marcada mitigada
        def mitigar(self, m: Muestra) -> Muestra:
            import numpy as np

            b = np.random.default_rng(3).integers(0, 2, len(m.bits), dtype=np.uint8)
            return Muestra(Bits.desde(b), Origen.PRNG_CLASICO, m.qubits, m.shots, mitigada=True)

    p = ParametrosPipeline(qubits=8, shots=40_000)
    r = ejecutar(FuentePrng(7, sesgo=0.4), ValidadorEstadistico(), RelojMonotonico(), p, mitigador=Pasa())
    assert [e for e, _ in r.etapas] == ["cruda", "mitigada", "clave"]
    cruda = {m.metrica: m for m in r.medidas_de("cruda")}
    assert not cruda[Metrica.SESGO].cumple and not cruda[Metrica.MONOBIT].cumple
    assert all(m.cumple for m in r.medidas_de("mitigada"))
    assert all(m.cumple for m in r.medidas_de("clave"))
