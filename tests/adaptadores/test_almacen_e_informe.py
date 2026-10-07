import pytest

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.datos import InformeCorrida
from qrecauda.dominio.errores import EntradaInvalida, EsquemaFuturo
from qrecauda.dominio.metricas import Metrica, Veredicto, medir
from qrecauda.dominio.muestra import Origen


def _informe() -> InformeCorrida:
    return InformeCorrida(
        "E1a", Origen.PRNG_CLASICO, 8, 1000, False, 0.97, 8000, 5000, Veredicto((medir(Metrica.MONOBIT, 0.4),)), {"python": "3.13"}
    )


def test_informe_ida_y_vuelta_exacta():
    i = _informe()
    assert InformeCorrida.desde_mapa(i.a_mapa()) == i


def test_lector_viejo_rechaza_esquema_futuro_y_malformado():
    d = _informe().a_mapa()
    with pytest.raises(EsquemaFuturo):
        InformeCorrida.desde_mapa({**d, "esquema": 99})
    with pytest.raises(EntradaInvalida):
        InformeCorrida.desde_mapa({"esquema": 1})


def test_almacen_es_append_only_canonico_y_rechaza_rutas(tmp_path):
    a = AlmacenJson(tmp_path)
    sha = a.guardar("E1a", _informe().a_mapa())
    assert len(sha) == 64 and a.leer("E1a") == _informe().a_mapa()
    with pytest.raises(EntradaInvalida):
        a.guardar("E1a", {"x": 1})
    with pytest.raises(EntradaInvalida):
        a.guardar("../fuera", {"x": 1})
