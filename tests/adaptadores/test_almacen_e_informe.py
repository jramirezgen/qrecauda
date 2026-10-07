import pytest

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.datos import ExperimentoE2, ExperimentoE3, InformeCorrida, leer_esquema
from qrecauda.dominio.errores import EntradaInvalida, EsquemaFuturo
from qrecauda.dominio.metricas import Metrica, Veredicto, medir
from qrecauda.dominio.muestra import Origen, Procedencia


def _informe() -> InformeCorrida:
    medidas = (medir(Metrica.MONOBIT, 0.4),)
    return InformeCorrida(
        corrida="C.E1a", eureka="E1", semilla=20261007, origen=Origen.PRNG_CLASICO, procedencia=Procedencia("prng", "", "numpy"),
        qubits=8, shots=1000, mitigada=False, epsilon=2.0**-64, profundidad_peres=2, validador="scipy", estimador="mcv",
        h_min_entrada=0.97, h_min_salida=0.999, bits_crudos=8000, bits_clave=5000, sha256_muestra_cruda="0" * 64,
        etapas={"cruda": medidas, "clave": medidas}, veredicto=Veredicto(medidas), preinscripcion_sha="a" * 7, commit="b" * 7,
        entorno={"python": "3.13"},
    )  # fmt: skip


def test_informe_ida_y_vuelta_exacta():
    i = _informe()
    assert InformeCorrida.desde_mapa(i.a_mapa()) == i


def test_lector_viejo_rechaza_esquema_futuro_y_malformado():
    d = _informe().a_mapa()
    with pytest.raises(EsquemaFuturo):
        InformeCorrida.desde_mapa({**d, "esquema": 99})
    with pytest.raises(EntradaInvalida):
        InformeCorrida.desde_mapa({"esquema": 2})


def test_almacen_es_append_only_canonico_y_rechaza_rutas(tmp_path):
    a = AlmacenJson(tmp_path)
    sha = a.guardar("E1a", _informe().a_mapa())
    assert len(sha) == 64 and a.leer("E1a") == _informe().a_mapa()
    with pytest.raises(EntradaInvalida):
        a.guardar("E1a", {"x": 1})
    with pytest.raises(EntradaInvalida):
        a.guardar("../fuera", {"x": 1})


def test_experimentos_e2_e3_ida_y_vuelta_y_esquema_futuro():
    e2 = ExperimentoE2("C.E2", 1, "medio", "twirling_propio", 400_000, 0.03, 0.002, (0.001, 0.003))
    e3 = ExperimentoE3("C.E3", 1, 30, 3, 12_000.0, 40.0, 55.0, {"cpu": "x"})
    assert ExperimentoE2.desde_mapa(e2.a_mapa()) == e2 and ExperimentoE3.desde_mapa(e3.a_mapa()) == e3
    with pytest.raises(EsquemaFuturo):
        ExperimentoE2.desde_mapa({**e2.a_mapa(), "esquema": 9})
    with pytest.raises(EsquemaFuturo):
        ExperimentoE3.desde_mapa({**e3.a_mapa(), "esquema": 9})


def test_leer_esquema_unica():
    assert leer_esquema({"esquema": 1}, 2) == 1
    for malo in ({}, {"esquema": "x"}, {"esquema": 0}):
        with pytest.raises(EntradaInvalida):
            leer_esquema(malo, 2)
