import io
import json

from qrecauda.transversal.observabilidad import BitacoraJsonl, RelojMonotonico, medir_etapa


def test_reloj_es_monotono():
    r = RelojMonotonico()
    a, b = r.ahora_ns(), r.ahora_ns()
    assert b >= a


def test_bitacora_escribe_una_linea_json_por_evento_con_claves_ordenadas():
    s = io.StringIO()
    b = BitacoraJsonl(s)
    b.registrar("a", z=1, y="x")
    b.registrar("b")
    lineas = s.getvalue().splitlines()
    assert [json.loads(x)["evento"] for x in lineas] == ["a", "b"]
    assert lineas[0] == '{"evento": "a", "y": "x", "z": 1}'


def test_bitacora_no_vuelca_un_secreto():
    s = io.StringIO()
    BitacoraJsonl(s).registrar("auth", token="s3creto-largo", ibm_token_ruta="/r/t.txt")
    linea = json.loads(s.getvalue())
    assert "s3creto-largo" not in s.getvalue()
    assert linea["token"] == "<oculto>"
    assert linea["ibm_token_ruta"] == "/r/t.txt"  # una ruta no es un secreto


def test_coste_por_etapa_mide_tiempo_y_pico():
    with medir_etapa("e") as c:
        _ = bytearray(2_000_000)
    assert c.etapa == "e" and c.segundos > 0 and c.pico_bytes >= 2_000_000


def test_medir_etapa_anidada_no_apaga_el_trazado_externo():
    import tracemalloc

    with medir_etapa("ext"), medir_etapa("int"):
        pass
    assert not tracemalloc.is_tracing()


def test_medir_etapa_registra_en_la_bitacora_si_se_da():
    s = io.StringIO()
    with medir_etapa("x", bitacora=BitacoraJsonl(s)):
        pass
    ev = json.loads(s.getvalue())
    assert ev["evento"] == "etapa" and ev["etapa"] == "x" and ev["segundos"] >= 0
