"""Tests de presentacion.figuras: las tablas salen del registro real y coinciden con los veredictos del juez."""

import math

import pytest
from matplotlib.figure import Figure

from qrecauda.presentacion import figuras as f

RAIZ = f.localizar_raiz()


def test_localiza_la_raiz_desde_una_subcarpeta():
    assert f.localizar_raiz(RAIZ / "notebooks") == RAIZ


def test_veredictos_e1_e2_cumplen_y_e3_no():
    d = {r["eureka"]: r["desenlace"] for r in f.tabla_veredictos(RAIZ)}
    assert d["E3"] == "NO_CUMPLE"
    assert d["E1"] != "NO_CUMPLE" and d["E2"] != "NO_CUMPLE"


def test_e3_m6_cumple_y_m7_no_con_los_rangos_del_registro():
    t = f.tabla_e3(RAIZ)
    assert len(t) == 3
    assert all(r["M6_cumple"] and not r["M7_cumple"] for r in t)
    assert all(180_000 <= r["M6_bps"] <= 196_000 for r in t)
    assert all(5.5 <= r["M7_p95_ms"] / 1000 <= 9.4 for r in t)
    assert all(math.isclose(r["M7_umbral_ms"], 500, rel_tol=1e-3) for r in t)
    assert all(math.isclose(r["M6_umbral_bps"], 10_000, rel_tol=1e-3) for r in t)


def test_perfil_b_no_decide_y_ronda_30_a_63_mil():
    t = f.tabla_perfil_b(RAIZ)
    assert all(not r["decide"] and not r["entropia_insuficiente"] for r in t)
    assert all(30_000 <= r["tx_por_s"] <= 64_000 for r in t)


def test_e2_agrupa_por_nivel_y_tecnica_y_twirling_reduce_el_sesgo():
    t = f.tabla_e2(RAIZ)
    assert all(r["semillas"] == 3 for r in t)
    tw = [r for r in t if r["tecnica"] == "twirling_propio" and r["nivel"] in ("bajo", "medio", "alto")]
    assert tw and all(r["factor"] > 10 for r in tw)


def test_e1_tablas_no_vacias_y_las_fuentes_defectuosas_caen():
    assert {r["corrida"] for r in f.tabla_e1(RAIZ)} >= {"C.E1a", "C.E1b", "C.E1c"}
    fuentes = {r["fuente"]: r for r in f.tabla_e1_fuentes(RAIZ)}
    assert fuentes["sesgada"]["h_90b_media"] < 0.5


def test_markdown_formatea_bool_y_float():
    md = f.a_markdown([{"a": True, "b": 0.123456789}])
    assert "| a | b |" in md and "| sí | 0.1235 |" in md
    assert f.a_markdown([]) == "_(vacía)_"


@pytest.mark.parametrize("nombre", ["fig_e3_cuello", "fig_e2_sesgo", "fig_e1_fuentes"])
def test_las_figuras_son_figure_con_ejes(nombre):
    fig = getattr(f, nombre)(RAIZ)
    assert isinstance(fig, Figure) and fig.axes


def test_detalle_sin_cociente_falla_en_voz_alta():
    with pytest.raises(ValueError):
        f._umbral("sin dato", 1.0)


def test_a_png_devuelve_un_png():
    assert f.a_png(f.fig_e1_fuentes(RAIZ))[:8] == b"\x89PNG\r\n\x1a\n"
