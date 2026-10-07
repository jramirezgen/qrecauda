"""Campos OPCIONALES de E2 y E3 que la preinscripción manda reportar y el esquema 1 no traía (compatibles hacia atrás)."""

import pytest

from qrecauda.datos import ExperimentoE2, ExperimentoE3, RuidoDeLectura
from qrecauda.dominio.errores import EntradaInvalida


def test_e2_sin_maximo_por_qubit_conserva_el_mapa_de_siempre():
    e = ExperimentoE2("C.E2", 1, "medio", "ninguna", 1000, 0.03, 0.03, (0.02, 0.04))
    assert "sesgo_maximo_por_qubit" not in e.a_mapa()
    assert ExperimentoE2.desde_mapa(e.a_mapa()) == e and e.sesgo_maximo_por_qubit is None


def test_e2_con_maximo_por_qubit_ida_y_vuelta():
    e = ExperimentoE2("C.E2", 1, "realista", "twirling_propio", 1000, 0.03, 0.002, (0.001, 0.003), sesgo_maximo_por_qubit=0.0071)
    assert e.a_mapa()["sesgo_maximo_por_qubit"] == 0.0071
    assert ExperimentoE2.desde_mapa(e.a_mapa()) == e


def test_e3_sin_reporte_conserva_el_mapa_de_siempre():
    e = ExperimentoE3("C.E3", 1, 30, 3, 12_000.0, 40.0, 55.0, {"cpu": "x"})
    assert "reporte" not in e.a_mapa() and ExperimentoE3.desde_mapa(e.a_mapa()) == e and dict(e.reporte) == {}


def test_e3_con_reporte_ida_y_vuelta():
    e = ExperimentoE3("C.E3", 1, 30, 3, 12_000.0, 40.0, 55.0, {"cpu": "x"}, reporte={"t_rep_ms": [1.5, 2.5], "perfil_b": {"n": 1000}})
    assert ExperimentoE3.desde_mapa(e.a_mapa()) == e


def test_ruido_de_lectura_valida_lo_que_construye():
    assert RuidoDeLectura("medio", (0.02, 0.08)).canal == (0.02, 0.08)
    assert RuidoDeLectura("sin_ruido").canal is None and RuidoDeLectura("realista", realista=True).realista
    with pytest.raises(EntradaInvalida):
        RuidoDeLectura("malo", (1.5, 0.1))
    with pytest.raises(EntradaInvalida):
        RuidoDeLectura("raro", (0.1, 0.1), realista=True)  # o canal sintético o realista, no ambos
