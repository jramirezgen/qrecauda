"""El juez de E3b: T1/T2/T3 por semilla, recalculados de los datos crudos; sin tocar la máquina. Declaración REAL declaraciones/E3b.toml."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from test_juez import EjecutorFalso, HistorialFalso, _servicio

from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.aplicacion.ejecutor_e3b import p_latencia, tasa_neta_bps
from qrecauda.datos import Declaracion, ExperimentoE3b, Medicion
from qrecauda.dominio.errores import CorridaInvalida

RAIZ = Path(__file__).resolve().parents[2]
CONTROLES = {f"U{i}": True for i in range(1, 6)} | {"T4": True}


@pytest.fixture
def e3b() -> Declaracion:
    return cargar_declaracion(Path("declaraciones/E3b.toml"), RAIZ)


def _clave(i: int, *, t_gen_s: float = 0.05, en_ventana: bool = True) -> dict[str, object]:
    return {"indice": i, "bits": 3520, "t_gen_ns": round(t_gen_s * 1e9), "en_ventana": en_ventana, "huella": f"{i:012x}", "entregada": True}


def _e3b(decl, semilla, *, lat_ms=2.0, n=None, claves=None, esperas=0, agotada=False, p95=None, tasa=None, controles=CONTROLES, **ajustes):
    n = int(decl.numero("demanda", "transacciones")) if n is None else n
    lat = [lat_ms] * n
    claves = claves if claves is not None else [_clave(i) for i in range(5)]
    reporte = {"latencias_ms": lat, "claves": claves, "esperas": esperas, "espera_ms": 0.0, "reserva_agotada": agotada}
    campos = {
        "demanda_tx_por_s": decl.numero("demanda", "tx_por_s"), "duracion_s": decl.numero("demanda", "duracion_s"),
        "consumo_bps": decl.numero("demanda", "consumo_bps"),
    } | ajustes  # fmt: skip
    e = ExperimentoE3b(
        decl.nodo_corrida, semilla, campos["demanda_tx_por_s"], campos["duracion_s"], len(lat), 3000.0,
        tasa_neta_bps(claves) if tasa is None else tasa, campos["consumo_bps"], p_latencia(lat, 95) if p95 is None else p95, esperas,
        0.9, 0.5, {"cpu": "x"}, reporte=reporte,
    )  # fmt: skip
    return Medicion(e3b=(e,), controles=dict(controles))


def _juzgar(tmp_path, decl, hacer):
    s, libro = _servicio(tmp_path, EjecutorFalso(hacer))
    s.correr(decl)
    return s.juzgar(decl), libro


def test_cumple_cuando_t1_t2_t3_pasan_en_las_tres_semillas(tmp_path, e3b):
    v, libro = _juzgar(tmp_path, e3b, _e3b)
    assert v.desenlace == "CUMPLE" and v.eureka == "E3b"
    ids = [c.id for c in v.criterios if c.decide]
    assert sorted(ids) == sorted(f"T{k}/{s}" for k in (1, 2, 3) for s in e3b.semillas)
    assert all(not c.decide for c in v.criterios if c.id.startswith("inf:"))
    assert len(libro.lineas) == 1


def test_t1_falla_si_la_tasa_no_supera_el_umbral_de_m6(tmp_path, e3b):
    lenta = [_clave(i, t_gen_s=0.5) for i in range(5)]  # 3520/0,5 = 7040 bit/s < 10 000
    v, _ = _juzgar(tmp_path, e3b, lambda d, s: _e3b(d, s, claves=lenta))
    assert v.desenlace == "NO_CUMPLE" and all(c.cumple for c in v.criterios if c.id.startswith("T2"))
    assert {c.id.split("/")[0] for c in v.criterios if c.decide and not c.cumple} == {"T1"}


def test_t1_exige_ademas_superar_el_consumo(tmp_path, e3b):
    # 12 000 bit/s pasa M6 (>10 000) pero NO el consumo de 35 200 bit/s: la reserva se vaciaría
    ok_m6 = [_clave(i, t_gen_s=3520 / 12_000) for i in range(5)]
    v, _ = _juzgar(tmp_path, e3b, lambda d, s: _e3b(d, s, claves=ok_m6))
    assert v.desenlace == "NO_CUMPLE" and any(c.id.startswith("T1") and not c.cumple for c in v.criterios)


def test_t2_es_estricto_en_500_ms(tmp_path, e3b):
    v, _ = _juzgar(tmp_path, e3b, lambda d, s: _e3b(d, s, lat_ms=500.0))
    assert v.desenlace == "NO_CUMPLE" and {c.id.split("/")[0] for c in v.criterios if c.decide and not c.cumple} == {"T2"}


def test_t3_falla_con_una_sola_espera_o_con_reserva_agotada(tmp_path, e3b):
    v, _ = _juzgar(tmp_path, e3b, lambda d, s: _e3b(d, s, esperas=1))
    assert v.desenlace == "NO_CUMPLE" and any(c.id.startswith("T3") and not c.cumple for c in v.criterios)
    v2, _ = _juzgar(tmp_path / "otra", e3b, lambda d, s: _e3b(d, s, n=100, agotada=True, esperas=1))
    assert v2.desenlace == "NO_CUMPLE"


def test_basta_una_semilla_mala_para_no_cumplir(tmp_path, e3b):
    mala = e3b.semillas[1]
    v, _ = _juzgar(tmp_path, e3b, lambda d, s: _e3b(d, s, lat_ms=900.0 if s == mala else 2.0))
    assert v.desenlace == "NO_CUMPLE" and [c.id for c in v.criterios if c.decide and not c.cumple] == [f"T2/{mala}"]


def test_el_t_gen_de_los_intentos_rechazados_cuenta_y_las_claves_fuera_de_ventana_no(e3b):
    assert tasa_neta_bps([_clave(0, t_gen_s=1.0), _clave(1, t_gen_s=1.0, en_ventana=False)]) == pytest.approx(3520.0)


def test_un_control_que_falla_invalida_la_corrida(tmp_path, e3b):
    s, libro = _servicio(tmp_path, EjecutorFalso(lambda d, sem: _e3b(d, sem, controles=CONTROLES | {"T4": False})))
    s.correr(e3b)
    with pytest.raises(CorridaInvalida, match="T4"):
        s.juzgar(e3b)
    assert libro.lineas == []


def test_falta_un_control_invalida(tmp_path, e3b):
    s, _ = _servicio(tmp_path, EjecutorFalso(lambda d, sem: _e3b(d, sem, controles={"U1": True})))
    s.correr(e3b)
    with pytest.raises(CorridaInvalida):
        s.juzgar(e3b)


def test_un_resumen_que_no_coincide_con_los_datos_invalida(tmp_path, e3b):
    s, _ = _servicio(tmp_path, EjecutorFalso(lambda d, sem: _e3b(d, sem, lat_ms=900.0, p95=2.0)))  # el resumen miente
    s.correr(e3b)
    with pytest.raises(CorridaInvalida, match="resumen"):
        s.juzgar(e3b)


def test_una_tasa_inflada_en_el_resumen_invalida(tmp_path, e3b):
    s, _ = _servicio(tmp_path, EjecutorFalso(lambda d, sem: _e3b(d, sem, tasa=1e9)))
    s.correr(e3b)
    with pytest.raises(CorridaInvalida, match="resumen"):
        s.juzgar(e3b)


def test_medir_con_otra_demanda_que_la_declarada_invalida(tmp_path, e3b):
    s, _ = _servicio(tmp_path, EjecutorFalso(lambda d, sem: _e3b(d, sem, demanda_tx_por_s=10.0)))
    s.correr(e3b)
    with pytest.raises(CorridaInvalida, match="λ"):
        s.juzgar(e3b)


def test_umbrales_movidos_en_el_toml_no_se_juzgan(tmp_path, e3b):
    t = {k: dict(v) for k, v in e3b.tablas.items()}
    t["criterios"]["t2_p95_menor_que_ms"] = 5000
    movida = replace(e3b, tablas=t)
    s, _ = _servicio(tmp_path, EjecutorFalso(_e3b))
    s.correr(e3b)
    with pytest.raises(CorridaInvalida, match="umbrales"):
        s.juzgar(movida)


def test_se_niega_si_la_preinscripcion_no_precede(tmp_path, e3b):
    s, libro = _servicio(tmp_path, EjecutorFalso(_e3b))
    s.correr(e3b)
    s2, _ = _servicio(tmp_path, EjecutorFalso(_e3b), HistorialFalso(precede=False), libro)
    with pytest.raises(CorridaInvalida):
        s2.juzgar(e3b)
