"""C.E2 y C.E3 con las piezas REALES (Aer, twirling, ZNE/PEC, mthree, NIST, 90B, AES-GCM) y parámetros DIMINUTOS.

No son las corridas: C.E2 y C.E3 las lanza quien dirige el plan. Esto prueba que el cableado funciona de punta a punta y que la
raíz de composición elige el ejecutor; las cifras de aquí no valen como resultado (pocos disparos, pocas repeticiones).
"""

from dataclasses import replace
from pathlib import Path

import pytest

from qrecauda import composicion
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.dominio.errores import CorridaInvalida

RAIZ = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.lento


def _diminuta_e2():
    d = cargar_declaracion(Path("declaraciones/E2.toml"), RAIZ)
    tablas = {k: dict(v) for k, v in d.tablas.items()}
    tablas["intervalo"]["remuestras"] = 200
    return replace(d, shots=2000, tablas=tablas)


def test_e2_real_con_parametros_diminutos_mide_todas_las_celdas(tmp_path):
    d = _diminuta_e2()
    m = composicion.ejecutor_e2_de(tmp_path).ejecutar(d, d.semillas[0])
    pares = {(c.nivel, c.tecnica) for c in m.e2}
    for nivel in ("bajo", "medio", "alto", "realista"):
        assert (nivel, "ninguna") in pares and (nivel, "twirling_propio") in pares
    assert {("sin_ruido", "twirling_propio"), ("simetrico", "twirling_propio"), ("medio", "zne"), ("medio", "pec")} <= pares
    assert {"C1", "C2", "C3", "C4"} <= set(m.controles)
    assert all(c.shots == 2000 and c.corrida == "C.E2" for c in m.e2)


def test_e2_aborta_si_la_constante_del_adaptador_no_coincide_con_el_toml(tmp_path):
    d = _diminuta_e2()
    tablas = {k: dict(v) for k, v in d.tablas.items()}
    tablas["ruido_lectura"]["bajo"] = [0.005, 0.01]  # la constante vieja del adaptador
    with pytest.raises(CorridaInvalida, match="bajo"):
        composicion.ejecutor_e2_de(tmp_path).ejecutar(replace(d, tablas=tablas), d.semillas[0])


def test_ejecutor_de_elige_el_de_e2(tmp_path):
    d = cargar_declaracion(Path("declaraciones/E2.toml"), RAIZ)
    assert type(composicion.ejecutor_de(tmp_path, d)).__name__ == "_EnMaquina"


def _diminuta_e3():
    d = cargar_declaracion(Path("declaraciones/E3.toml"), RAIZ)
    t = {k: dict(v) for k, v in d.tablas.items()}
    t["configuracion"].update(repeticiones=2, calentamiento=1, carga_previa_maxima=1e9)  # la carga del CI no es la de C.E3
    t["perfil_b"].update(transacciones=20, peaje=10, metro=10)
    t["controles_uso"].update(u2_casos=5, u3_casos=5)
    return replace(d, shots=125_000, tablas=t)  # 8 × 125 000 = 1 M de bits: el mínimo del 90B


def test_e3_real_exige_omp_num_threads_1_antes_de_medir(tmp_path, monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "8")
    d = _diminuta_e3()
    with pytest.raises(CorridaInvalida, match="OMP_NUM_THREADS"):
        composicion.ejecutor_e3_de(tmp_path).ejecutar(d, d.semillas[0])


def test_e3_real_con_parametros_diminutos_recorre_la_cadena_completa(tmp_path, monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    d = _diminuta_e3()
    m = composicion.ejecutor_e3_de(tmp_path).ejecutar(d, d.semillas[0])
    (e,) = m.e3
    assert (e.repeticiones, e.calentamiento, e.corrida) == (2, 1, "C.E3")
    assert set(m.controles) == {"U1", "U2", "U3", "U4", "U5", "T4"}
    assert set(e.reporte["etapas_ms"]) == {"fuente", "mitigacion", "extraccion", "validacion", "cifrado"}
    assert e.maquina["nucleos_logicos"] and e.m6_bits_por_s > 0
    assert (tmp_path / "salidas" / "candado_maquina.lock").exists()  # pasó por el candado de máquina


def test_ejecutor_de_elige_el_de_e3(tmp_path):
    d = cargar_declaracion(Path("declaraciones/E3.toml"), RAIZ)
    assert type(composicion.ejecutor_de(tmp_path, d)).__name__ == "_EnMaquina"
