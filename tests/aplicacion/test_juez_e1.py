"""El juez de E1: lee las cuatro corridas por semilla (cruda/mitigada/clave) y aplica B1, M-1, M-2 y la tabla de desenlaces
EXACTAMENTE como están preinscritos (con la enmienda del 2026-10-07: M4 y M5 de la mitigada informativas).

Todo sintético: medidas a mano (e1_medidas), declaración REAL declaraciones/E1.toml (sólo se lee), almacén en tmp.
"""

from dataclasses import replace
from pathlib import Path

import pytest
from e1_medidas import BUENA, SESGADA, fuente, fuentes_ok, informe
from test_juez import EjecutorFalso, HistorialFalso, LibroEnMemoria

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.datos import Medicion
from qrecauda.dominio.errores import CorridaInvalida

RAIZ = Path(__file__).resolve().parents[2]
SEMILLAS = (20261007, 20261008, 20261009)
CONTROLES = {"N1": True, "D1": True, "P1": True}
CAMBIO_M4_M5 = {**BUENA, "m4": 0.0, "m5": 0.0}


@pytest.fixture
def e1():
    return cargar_declaracion(Path("declaraciones/E1.toml"), RAIZ)


def _medicion(
    semilla,
    *,
    a=None,
    b=None,
    c=None,
    fuentes=None,
    controles=CONTROLES,
    cruda_b=SESGADA,
    cruda_c=SESGADA,
    mitigada=BUENA,
    clave_c=BUENA,
    m2=0.99,
    reporte_c=None,
):
    return Medicion(
        informes=(
            a or informe("C.E1a", semilla, cruda=BUENA, aer=False),
            b or informe("C.E1b", semilla, cruda=cruda_b, clave=BUENA),
            c or informe("C.E1c", semilla, cruda=cruda_c, mitigada=mitigada, clave=clave_c, m2=m2, reporte=reporte_c),
        ),
        fuentes=fuentes if fuentes is not None else fuentes_ok(semilla),
        controles=dict(controles),
    )


def _juzgar(tmp_path, e1, hacer):
    libro = LibroEnMemoria()
    s = CorrerYJuzgar(EjecutorFalso(hacer), AlmacenJson(tmp_path / "corridas"), HistorialFalso(), libro, {"python": "3.13"})
    s.correr(e1)
    return s.juzgar(e1), libro


# ---------------------------------------------------------------- correr: el manifiesto único y las cuatro rutas del plan


def test_correr_e1_escribe_el_manifiesto_unico_y_las_cuatro_rutas_E1a_a_E1d(tmp_path, e1):
    s = CorrerYJuzgar(
        EjecutorFalso(lambda d, sem: _medicion(sem)), AlmacenJson(tmp_path / "corridas"), HistorialFalso(), LibroEnMemoria(), {}
    )
    m = s.correr(e1)
    escritos = {p.name for p in (tmp_path / "corridas").glob("*.json")}
    assert {"C.E1.json", "E1a.json", "E1b.json", "E1c.json", "E1d.json"} <= escritos
    assert m.corrida == "C.E1" and len(m.artefactos) == 3 * (3 + 4)  # 3 informes y 4 fuentes por semilla
    for letra in "abcd":  # cada ruta del plan es un manifiesto propio, con los artefactos de SU corrida
        h = AlmacenJson(tmp_path / "corridas").leer(f"E1{letra}")
        assert h["corrida"] == f"C.E1{letra}" and h["eureka"] == "E1" and h["controles"] == CONTROLES
        assert len(h["artefactos"]) == 3 * (4 if letra == "d" else 1)  # type: ignore[arg-type]
        assert h["preinscripcion_sha"] == m.preinscripcion_sha


def test_correr_e1_se_niega_si_una_corrida_declarada_no_produjo_nada(tmp_path, e1):
    sin_d = EjecutorFalso(lambda d, sem: replace(_medicion(sem), fuentes=()))
    s = CorrerYJuzgar(sin_d, AlmacenJson(tmp_path / "corridas"), HistorialFalso(), LibroEnMemoria(), {})
    with pytest.raises(CorridaInvalida, match="C.E1d"):
        s.correr(e1)


def test_correr_e1_rechaza_una_fuente_que_cita_otra_corrida(tmp_path, e1):
    mala = EjecutorFalso(lambda d, sem: replace(_medicion(sem), fuentes=fuentes_ok(sem, corrida="C.OTRA")))
    s = CorrerYJuzgar(mala, AlmacenJson(tmp_path / "corridas"), HistorialFalso(), LibroEnMemoria(), {})
    with pytest.raises(CorridaInvalida, match="C.OTRA"):
        s.correr(e1)


# ---------------------------------------------------------------- desenlaces


def test_cumple_deja_la_linea_en_el_libro_con_el_rotulo_de_que_no_certifica_origen(tmp_path, e1):
    v, libro = _juzgar(tmp_path, e1, lambda d, sem: _medicion(sem, mitigada=CAMBIO_M4_M5))  # M4/M5 de la mitigada FALLAN y no deciden
    assert v.desenlace == "CUMPLE" and v.aprobado and v.corrida == "C.E1"
    assert "no certifica origen cuántico" in v.resumen
    assert len(libro.lineas) == 1 and libro.lineas[0]["eureka"] == "E1"
    for s in SEMILLAS:
        ids = {c.id: c for c in v.criterios}
        assert ids[f"M-1/{s}"].cumple and ids[f"M-2/{s}"].cumple and ids[f"B1/{s}"].cumple
        inf = ids[f"inf:M4_M5_mitigada/{s}"]
        assert not inf.cumple and not inf.decide  # se reporta, no decide (enmienda 2026-10-07)


def test_nulo_si_la_cruda_no_falla_m1_ni_m3(tmp_path, e1):
    """⚠️ Con la declaración real NULO es inalcanzable: D1 exige M1 ≈ 0,030 ± 0,002 y B1 falla desde M1 ≥ 0,01. Aquí, una
    declaración sintética con otro sesgo inyectado (0,001) hace D1 compatible con una cruda que no falla: prueba la rama de la tabla."""
    e1 = replace(e1, tablas={**e1.tablas, "ruido": {**e1.tablas["ruido"], "sesgo_analitico": 0.001}})
    v, _ = _juzgar(
        tmp_path,
        e1,
        lambda d, sem: _medicion(sem, cruda_b=BUENA) if sem == SEMILLAS[1] else _medicion(sem, cruda_b={**SESGADA, "m1": 0.001, "m3": 0.0}),
    )
    assert v.desenlace == "NULO" and not v.aprobado
    assert "no dice nada sobre la mitigación" in v.resumen and str(SEMILLAS[1]) in v.resumen
    b1 = {c.id: c.cumple for c in v.criterios if c.id.startswith("B1/")}
    assert b1 == {f"B1/{SEMILLAS[0]}": True, f"B1/{SEMILLAS[1]}": False, f"B1/{SEMILLAS[2]}": True}


def test_no_cumple_si_la_clave_de_c_e1c_falla_en_una_semilla_y_nombra_semilla_y_metrica(tmp_path, e1):
    def hacer(d, sem):
        return _medicion(sem, clave_c={**BUENA, "m5": 0.004}) if sem == SEMILLAS[2] else _medicion(sem)

    v, libro = _juzgar(tmp_path, e1, hacer)
    assert v.desenlace == "NO_CUMPLE"
    assert str(SEMILLAS[2]) in v.resumen and "M5_chi_cuadrado=0.004" in v.resumen
    assert libro.lineas[0]["aprobado"] is False


def test_cumple_parcial_si_la_clave_pasa_y_la_mitigada_falla_m1_o_m3(tmp_path, e1):
    v, _ = _juzgar(tmp_path, e1, lambda d, sem: _medicion(sem, mitigada={**BUENA, "m3": 0.004}))
    assert v.desenlace == "CUMPLE_PARCIAL" and "M3_nist_monobit" in v.resumen and "la clave pasa" in v.resumen


def test_m2_manda_sobre_m1_aunque_ambas_fallen(tmp_path, e1):
    v, _ = _juzgar(tmp_path, e1, lambda d, sem: _medicion(sem, mitigada={**BUENA, "m1": 0.02}, clave_c={**BUENA, "m4": 0.0}))
    assert v.desenlace == "NO_CUMPLE"


def test_m2_de_la_clave_incluye_la_min_entropia_de_salida(tmp_path, e1):
    v, _ = _juzgar(tmp_path, e1, lambda d, sem: _medicion(sem, m2=0.85))
    assert v.desenlace == "NO_CUMPLE" and "M2_min_entropia=0.85" in v.resumen


def test_el_hallazgo_de_que_la_clave_de_e1b_pasa_se_escribe_pero_no_decide(tmp_path, e1):
    v, _ = _juzgar(tmp_path, e1, lambda d, sem: _medicion(sem))
    h = [c for c in v.criterios if c.id.startswith("inf:clave_c_e1b/")]
    assert len(h) == 3 and all(c.cumple and not c.decide for c in h) and "R.00-1" in v.resumen
    v2, _ = _juzgar(
        tmp_path / "otro", e1, lambda d, sem: _medicion(sem, b=informe("C.E1b", sem, cruda=SESGADA, clave={**BUENA, "m1": 0.02}))
    )
    assert v2.desenlace == "CUMPLE"  # que la clave de E1b falle no condiciona CUMPLE/NO CUMPLE


def test_informativos_90b_y_proporcion_nist_se_leen_del_reporte_sin_decidir(tmp_path, e1):
    rep = {
        "h_90b_cruda": 0.91, "h_90b_mitigada": 0.4, "sha256_muestra_cruda": "s" * 64, "sha256_muestra_mitigada": "m" * 64,
        "proporcion_nist": {"M3": {"aprobados": 90, "total": 93, "proporcion": 90 / 93, "cumple": True}},
    }  # fmt: skip
    v, _ = _juzgar(tmp_path, e1, lambda d, sem: _medicion(sem, reporte_c=rep))
    ids = {c.id: c for c in v.criterios}
    assert v.desenlace == "CUMPLE"  # un 90B de 0,4 en la mitigada NO decide (E1.md, C.E1c)
    assert not ids[f"inf:90B/{SEMILLAS[0]}"].decide and not ids[f"inf:nist_proporcion/{SEMILLAS[0]}"].decide
    assert "0.4" in ids[f"inf:90B/{SEMILLAS[0]}"].detalle and "90/93" in ids[f"inf:nist_proporcion/{SEMILLAS[0]}"].detalle


# ---------------------------------------------------------------- controles: inválida, no veredicto


@pytest.mark.parametrize("control", ["N1", "D1", "P1"])
def test_un_control_en_falso_invalida_la_corrida(tmp_path, e1, control):
    s = CorrerYJuzgar(EjecutorFalso(lambda d, sem: _medicion(sem, controles={**CONTROLES, control: False})),
                      AlmacenJson(tmp_path / "corridas"), HistorialFalso(), libro := LibroEnMemoria(), {})  # fmt: skip
    s.correr(e1)
    with pytest.raises(CorridaInvalida, match=control):
        s.juzgar(e1)
    assert libro.lineas == []


@pytest.mark.parametrize(
    ("estropicio", "control"),
    [
        (lambda sem: {"a": informe("C.E1a", sem, cruda={**BUENA, "m3": 0.0}, aer=False)}, "N1"),
        (lambda sem: {"b": informe("C.E1b", sem, cruda={**SESGADA, "m1": 0.0})}, "D1"),
        (lambda sem: {"fuentes": (*fuentes_ok(sem)[:3], fuente("C.E1d", sem, "ideal", cruda=BUENA, mcv=0.9, h90=0.5))}, "P1"),
    ],
    ids=["N1", "D1", "P1"],
)
def test_si_el_manifiesto_dice_ok_pero_los_datos_lo_desmienten_tambien_es_invalida(tmp_path, e1, estropicio, control):
    """Defensa en profundidad: el juez recalcula N1, D1 y P1 de los artefactos; no se fía del booleano del ejecutor."""
    v_hacer = lambda d, sem: _medicion(sem, **estropicio(sem))  # noqa: E731
    s = CorrerYJuzgar(EjecutorFalso(v_hacer), AlmacenJson(tmp_path / "corridas"), HistorialFalso(), LibroEnMemoria(), {})
    s.correr(e1)
    with pytest.raises(CorridaInvalida, match=control):
        s.juzgar(e1)


def test_juzgar_se_niega_si_falta_una_semilla_o_una_corrida(tmp_path, e1):
    def sin_c(d, sem):
        m = _medicion(sem)
        return replace(m, informes=m.informes[:2]) if sem == SEMILLAS[1] else m

    s = CorrerYJuzgar(EjecutorFalso(sin_c), AlmacenJson(tmp_path / "corridas"), HistorialFalso(), LibroEnMemoria(), {})
    s.correr(e1)
    with pytest.raises(CorridaInvalida, match="C.E1c"):
        s.juzgar(e1)
