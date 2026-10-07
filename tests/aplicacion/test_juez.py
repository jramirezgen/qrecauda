"""F2.07: de la declaración al veredicto, sin que nadie teclee una cifra. Semillas y umbrales salen de declaraciones/*.toml."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.datos import Declaracion, ExperimentoE2, ExperimentoE3, Medicion
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida

RAIZ = Path(__file__).resolve().parents[2]
PRE, HEAD = "a" * 40, "b" * 40


class HistorialFalso:
    def __init__(self, *, precede: bool = True, pre: str = PRE, modificado: bool = False) -> None:
        self.pre, self.head, self._precede, self._modificado = pre, HEAD, precede, modificado

    def ultimo_commit(self, rutas: tuple[str, ...]) -> str:
        return self.pre

    def commit_actual(self) -> str:
        return self.head

    def modificado(self, rutas: tuple[str, ...]) -> bool:
        return self._modificado

    def precede(self, antes: str, despues: str) -> bool:
        return self._precede


class LibroEnMemoria:
    def __init__(self) -> None:
        self.lineas: list[dict[str, object]] = []

    def anadir(self, linea: dict[str, object]) -> None:
        self.lineas.append(linea)


class EjecutorFalso:
    """Devuelve lo que el test le ordene; apunta qué semillas le pidieron."""

    def __init__(self, hacer) -> None:
        self.hacer, self.semillas = hacer, []

    def ejecutar(self, decl: Declaracion, semilla: int) -> Medicion:
        self.semillas.append(semilla)
        return self.hacer(decl, semilla)


NIVELES = ("bajo", "medio", "alto")
CONTROLES_E2 = {"C1": True, "C2": True, "C3": True}
CONTROLES_E3 = {f"U{i}": True for i in range(1, 6)} | {"T4": True}


def _e2_ok(decl, semilla, *, residual=0.001, crudo=0.03, ic=(0.0005, 0.0015), controles=CONTROLES_E2, falla: dict | None = None):
    celdas = []
    for nivel in NIVELES:
        r, c, i = (falla or {}).get((nivel, semilla), (residual, crudo, ic))
        celdas.append(ExperimentoE2(decl.nodo_corrida, semilla, nivel, "ninguna", decl.shots, c, c, (c, c)))
        celdas.append(ExperimentoE2(decl.nodo_corrida, semilla, nivel, "twirling_propio", decl.shots, c, r, i))
    return Medicion(e2=tuple(celdas), controles=dict(controles))


def _e3(decl, semilla, *, m6=20_000.0, m7=100.0, controles=CONTROLES_E3):
    cfg = decl.tabla("configuracion")
    e = ExperimentoE3(decl.nodo_corrida, semilla, int(cfg["repeticiones"]), int(cfg["calentamiento"]), m6, m7, m7 * 1.2, {"cpu": "x"})  # type: ignore[call-overload,arg-type]
    return Medicion(e3=(e,), controles=dict(controles))


@pytest.fixture
def e2() -> Declaracion:
    return cargar_declaracion(Path("declaraciones/E2.toml"), RAIZ)


@pytest.fixture
def e3() -> Declaracion:
    return cargar_declaracion(Path("declaraciones/E3.toml"), RAIZ)


def _servicio(tmp_path, ejecutor, historial=None, libro=None):
    libro = libro if libro is not None else LibroEnMemoria()
    return CorrerYJuzgar(ejecutor, AlmacenJson(tmp_path / "corridas"), historial or HistorialFalso(), libro, {"python": "3.13"}), libro


# ---------------------------------------------------------------- la declaración manda


def test_la_declaracion_trae_semillas_y_umbrales_de_los_toml(e2, e3):
    assert e2.eureka == "E2" and e2.nodo_corrida == "C.E2" and e3.nodo_corrida == "C.E3"
    assert e2.semillas == e3.semillas == (20261007, 20261008, 20261009)  # heredadas de PARAMETROS.toml
    assert (e2.qubits, e2.shots) == (8, 400_000)
    assert e2.tabla("criterios_twirling")["k3_residuo_maximo"] == 0.003
    assert e2.rutas[-1] == "docs/preinscripciones/E2.md" and "declaraciones/PARAMETROS.toml" in e2.rutas


def test_una_declaracion_sin_preinscripcion_no_se_carga(tmp_path):
    (tmp_path / "declaraciones").mkdir()
    (tmp_path / "declaraciones" / "X.toml").write_text(
        '[experimento]\nid="X"\nnodo_corrida="C.X"\n[cadena]\nqubits=1\nshots=1\nsemillas=[1]\n'
    )
    with pytest.raises(EntradaInvalida):
        cargar_declaracion(Path("declaraciones/X.toml"), tmp_path)


# ---------------------------------------------------------------- correr


def test_correr_corre_las_semillas_declaradas_y_escribe_manifiesto_y_artefactos(tmp_path, e3):
    ej = EjecutorFalso(_e3)
    s, _ = _servicio(tmp_path, ej)
    m = s.correr(e3)
    assert ej.semillas == list(e3.semillas)
    assert (m.preinscripcion_sha, m.commit, m.corrida) == (PRE, HEAD, "C.E3")
    assert len(m.artefactos) == 3 and all(len(sha) == 64 for _, _, sha in m.artefactos)
    assert (tmp_path / "corridas" / "C.E3.json").exists()
    assert len(list((tmp_path / "corridas").glob("*.json"))) == 4


def test_correr_es_append_only(tmp_path, e3):
    s, _ = _servicio(tmp_path, EjecutorFalso(_e3))
    s.correr(e3)
    with pytest.raises(EntradaInvalida):
        s.correr(e3)


def test_correr_se_niega_si_la_preinscripcion_tiene_cambios_sin_commit(tmp_path, e3):
    ej = EjecutorFalso(_e3)
    s, _ = _servicio(tmp_path, ej, HistorialFalso(modificado=True))
    with pytest.raises(CorridaInvalida):
        s.correr(e3)
    assert ej.semillas == []  # no se midió nada


def test_correr_rechaza_una_medicion_que_no_cita_el_nodo_declarado(tmp_path, e3):
    mala = EjecutorFalso(lambda d, s: _e3(replace(d, nodo_corrida="C.OTRO"), s))
    s, _ = _servicio(tmp_path, mala)
    with pytest.raises(CorridaInvalida):
        s.correr(e3)


# ---------------------------------------------------------------- juzgar E3


def test_juzgar_e3_cumple_y_deja_una_linea_en_el_libro(tmp_path, e3):
    s, libro = _servicio(tmp_path, EjecutorFalso(_e3))
    s.correr(e3)
    v = s.juzgar(e3)
    assert v.aprobado and v.desenlace == "CUMPLE" and v.corrida == "C.E3"
    assert len(libro.lineas) == 1 and libro.lineas[0]["eureka"] == "E3" and libro.lineas[0]["aprobado"] is True
    assert libro.lineas[0]["preinscripcion_sha"] == PRE


def test_juzgar_e3_usa_desigualdad_estricta_y_dice_cual_falla_y_por_cuanto(tmp_path, e3):
    s, _ = _servicio(tmp_path, EjecutorFalso(lambda d, sem: _e3(d, sem, m6=10_000.0, m7=250.0)))  # M6 en el umbral exacto
    s.correr(e3)
    v = s.juzgar(e3)
    assert not v.aprobado and v.desenlace == "NO_CUMPLE"
    t1 = next(c for c in v.criterios if c.id.startswith("T1/"))
    assert not t1.cumple and "1.00" in t1.detalle  # cociente M6/10000, del umbral de dominio.metricas
    assert all(c.cumple for c in v.criterios if c.id.startswith("T2/"))


# ---------------------------------------------------------------- juzgar se niega


def test_juzgar_se_niega_si_la_preinscripcion_no_precede_a_la_corrida(tmp_path, e3):
    s, libro = _servicio(tmp_path, EjecutorFalso(_e3))
    s.correr(e3)
    s2, _ = _servicio(tmp_path, EjecutorFalso(_e3), HistorialFalso(precede=False), libro)
    with pytest.raises(CorridaInvalida, match="precede"):
        s2.juzgar(e3)
    assert libro.lineas == []


def test_juzgar_se_niega_si_la_preinscripcion_cambio_despues_de_correr(tmp_path, e3):
    s, libro = _servicio(tmp_path, EjecutorFalso(_e3))
    s.correr(e3)
    s2, _ = _servicio(tmp_path, EjecutorFalso(_e3), HistorialFalso(pre="c" * 40), libro)
    with pytest.raises(CorridaInvalida, match="cambió"):
        s2.juzgar(e3)


def test_juzgar_se_niega_si_falta_un_control(tmp_path, e3):
    s, libro = _servicio(tmp_path, EjecutorFalso(lambda d, sem: _e3(d, sem, controles={"U1": True})))
    s.correr(e3)
    with pytest.raises(CorridaInvalida, match="falta"):
        s.juzgar(e3)
    assert libro.lineas == []


def test_un_control_que_falla_invalida_la_corrida_no_la_veredicta(tmp_path, e3):
    s, libro = _servicio(tmp_path, EjecutorFalso(lambda d, sem: _e3(d, sem, controles=CONTROLES_E3 | {"T4": False})))
    s.correr(e3)
    with pytest.raises(CorridaInvalida, match="T4"):
        s.juzgar(e3)
    assert libro.lineas == []


def test_juzgar_detecta_un_artefacto_alterado(tmp_path, e3):
    s, _ = _servicio(tmp_path, EjecutorFalso(_e3))
    m = s.correr(e3)
    ruta = tmp_path / "corridas" / f"{m.artefactos[0][0]}.json"
    d = json.loads(ruta.read_text())
    d["m7_p95_ms"] = 1.0
    ruta.write_text(json.dumps(d))
    with pytest.raises(CorridaInvalida, match="sha"):
        s.juzgar(e3)


def test_juzgar_sin_haber_corrido_no_inventa_nada(tmp_path, e3):
    s, _ = _servicio(tmp_path, EjecutorFalso(_e3))
    with pytest.raises(CorridaInvalida):
        s.juzgar(e3)


# ---------------------------------------------------------------- juzgar E2


def _juzga(tmp_path, e2, hacer):
    s, libro = _servicio(tmp_path, EjecutorFalso(hacer))
    s.correr(e2)
    return s.juzgar(e2), libro


def test_e2_cumple_con_k1_a_k4_en_las_nueve_celdas(tmp_path, e2):
    v, libro = _juzga(tmp_path, e2, _e2_ok)
    assert v.aprobado and v.desenlace == "CUMPLE" and len(v.criterios) == 9
    assert libro.lineas[0]["desenlace"] == "CUMPLE"


def test_e2_parcial_nombra_el_nivel_mas_bajo_donde_falla_una_semilla(tmp_path, e2):
    s0 = e2.semillas[1]
    v, _ = _juzga(
        tmp_path,
        e2,
        lambda d, s: _e2_ok(d, s, falla={("alto", s0): (0.004, 0.05, (0.003, 0.005)), ("medio", s0): (0.0035, 0.03, (0.003, 0.004))}),
    )
    assert not v.aprobado and v.desenlace == "CUMPLE_PARCIAL"
    assert "nivel medio" in v.resumen  # el más bajo donde falla alguna semilla, no el último


def test_e2_nulo_si_el_factor_es_menor_que_1_5_con_algo_que_reducir(tmp_path, e2):
    v, _ = _juzga(tmp_path, e2, lambda d, s: _e2_ok(d, s, falla={("medio", s): (0.025, 0.03, (0.024, 0.026))}))
    assert v.desenlace == "NULO" and not v.aprobado


def test_e2_inconcluso_si_el_ic_contiene_el_umbral(tmp_path, e2):
    v, _ = _juzga(tmp_path, e2, lambda d, s: _e2_ok(d, s, falla={("alto", s): (0.0025, 0.05, (0.002, 0.0101))}))
    assert v.desenlace == "INCONCLUSO"


def test_e2_el_residuo_en_el_umbral_exacto_no_cumple_m1(tmp_path, e2):
    v, _ = _juzga(tmp_path, e2, lambda d, s: _e2_ok(d, s, falla={("bajo", s): (0.01, 0.02, (0.009, 0.0095))}))
    assert not v.aprobado


def test_e2_k4_no_aplica_si_el_crudo_ya_esta_bajo_m1(tmp_path, e2):
    v, _ = _juzga(tmp_path, e2, lambda d, s: _e2_ok(d, s, falla={("bajo", s): (0.002, 0.0099, (0.001, 0.003))}))
    assert v.aprobado  # factor 4,95 < 5 pero crudo < 0,01: «no aplicable»


def test_e2_el_realista_tiene_veredicto_propio_y_no_entra_en_la_conjuncion(tmp_path, e2):
    def con_realista(d, s):
        m = _e2_ok(d, s)
        malo = ExperimentoE2(d.nodo_corrida, s, "realista", "twirling_propio", d.shots, 0.03, 0.02, (0.019, 0.021))
        return replace(m, e2=(*m.e2, malo))

    v, _ = _juzga(tmp_path, e2, con_realista)
    assert v.aprobado and any(c.id.startswith("realista/") and not c.cumple and not c.decide for c in v.criterios)


def test_e2_exige_las_nueve_celdas(tmp_path, e2):
    def sin_una(d, s):
        m = _e2_ok(d, s)
        return replace(m, e2=tuple(c for c in m.e2 if not (c.nivel == "alto" and c.tecnica == "twirling_propio")))

    s, _ = _servicio(tmp_path, EjecutorFalso(sin_una))
    s.correr(e2)
    with pytest.raises(CorridaInvalida, match="alto"):
        s.juzgar(e2)


def test_e2_sin_el_control_c2_no_hay_veredicto(tmp_path, e2):
    s, _ = _servicio(tmp_path, EjecutorFalso(lambda d, sem: _e2_ok(d, sem, controles={"C1": True, "C3": True})))
    s.correr(e2)
    with pytest.raises(CorridaInvalida, match="C2"):
        s.juzgar(e2)
