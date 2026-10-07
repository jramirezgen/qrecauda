import json

from qrecauda import presentacion
from qrecauda.datos import serializar
from qrecauda.dominio.metricas import Metrica, Veredicto, medir

V = Veredicto((medir(Metrica.SESGO, 0.001), medir(Metrica.MONOBIT, 0.005)))


def test_tabla_marca_el_fallo():
    t = presentacion.tabla(V)
    assert "RECHAZADO M3_nist_monobit" in t and "NO" in t


def test_json_canonico_reusa_la_serializacion_de_datos():
    d = json.loads(presentacion.json_canonico(V))
    assert d["aprobado"] is False and d["fallos"] == ["M3_nist_monobit"]
    assert [m["metrica"] for m in d["medidas"]] == ["M1_sesgo", "M3_nist_monobit"]
    assert presentacion.json_canonico(V) == serializar(d)
