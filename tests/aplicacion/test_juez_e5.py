"""El juez de E5: D (rechazada o acortada), G1–G3 y la tabla de desenlaces tal como están preinscritos; los controles D5 y P5 se
RECALCULAN. Todo sintético (resultados a mano); la declaración es la REAL declaraciones/E5.toml (sólo se lee)."""

import math
from pathlib import Path

import pytest
from test_juez import EjecutorFalso, HistorialFalso, LibroEnMemoria

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.aplicacion import criterios_e5 as c
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.datos import ExperimentoE5, Medicion
from qrecauda.dominio.errores import CorridaInvalida

RAIZ = Path(__file__).resolve().parents[2]
CRUDOS = 3_200_000
METRICAS = ("M1_sesgo", "M2_min_entropia", "M3_nist_monobit", "M4_nist_runs", "M5_chi_cuadrado")
SEMILLAS = (20261007, 20261008, 20261009)


@pytest.fixture
def e5():
    return cargar_declaracion(Path("declaraciones/E5.toml"), RAIZ)


def _res(dim, bits, *, ok=True, segundos=1.0, entrega=True, sha="s"):
    if not entrega:
        return {"dimensionado": dim, "estado": "rechazada", "motivo": "x", "sha256_muestra": sha, "bits_clave": 0, "medidas": []}
    return {
        "dimensionado": dim, "estado": "entregada", "motivo": "", "sha256_muestra": sha, "bits_pool": 2 * bits,
        "h_mcv_pool": 0.99, "h_90b_pool": None, "h_90b_fuente": None, "h_efectiva": 0.99, "bits_clave": bits,
        "medidas": [[m, 0.0, 1.0, ok] for m in METRICAS], "segundos": segundos, "tasa_bps": bits / segundos,
    }  # fmt: skip


def _exp(decl, semilla, fuente, mcv, mp, cons, h90=None):
    t = decl.tablas["defectos"]
    par = {"prefijo_90b": 1_000_000, "p_fresca_max": t["p_fresca_max"]}
    par |= {"tipo": "ninguno"} if fuente == "buena" else {k: v for k, v in t[fuente].items()}
    if h90 is None:
        h90 = 0.9 if fuente == "buena" else 0.1
    return ExperimentoE5(
        "C.E5", semilla, fuente, CRUDOS, h90, par, (_res("mcv", **mcv), _res("min_mcv_90b", **mp), _res("conservador", **cons))
    )


BUENA = (dict(bits=2_000_000), dict(bits=1_900_000), dict(bits=1_800_000, segundos=100.0))


def _semilla(decl, semilla, defectuosas=None, buena=BUENA, h90=None):
    # por omisión, cada defectuosa SIN clave con el conservador; hoy (mcv) entrega una clave larga que pasa M1–M5
    d = {f: (dict(bits=1_500_000), dict(bits=900_000), dict(bits=0, entrega=False)) for f in ("markov", "markov_fuerte", "periodica")}
    d |= defectuosas or {}
    exps = [_exp(decl, semilla, "buena", *(dict(x) for x in buena), h90=h90)]
    exps += [_exp(decl, semilla, f, *(dict(x) for x in t)) for f, t in d.items()]
    return Medicion(e5=tuple(exps), controles={"D5": True, "P5": True})


def _juzgar(tmp_path, e5, hacer):
    libro = LibroEnMemoria()
    s = CorrerYJuzgar(EjecutorFalso(hacer), AlmacenJson(tmp_path / "corridas"), HistorialFalso(), libro, {"python": "3.13"})
    s.correr(e5)
    return s.juzgar(e5), libro


def test_cumple_cuando_las_tres_defectuosas_se_rechazan_y_la_buena_se_conserva(tmp_path, e5):
    v, libro = _juzgar(tmp_path, e5, lambda d, s: _semilla(d, s))
    assert v.desenlace == "CUMPLE" and libro.lineas[0]["desenlace"] == "CUMPLE"
    ids = {x.id for x in v.criterios if x.decide}
    assert {f"{k}/{s}" for k in ("G1", "G2", "G3") for s in SEMILLAS} <= ids and "D/markov_fuerte/20261009" in ids
    hoy = [
        x for x in v.criterios if x.id.startswith("HOY/mcv")
    ]  # R.00-1: con 0.1.0 entrega claves defectuosas largas, por encima del techo
    assert len(hoy) == 3 and all(not x.decide and not x.cumple for x in hoy)


def test_una_defectuosa_acortada_bajo_el_techo_y_la_cuarta_parte_cumple(tmp_path, e5):
    corta = (dict(bits=1_500_000), dict(bits=900_000), dict(bits=40_000))  # techo K1 de markov 0,8 ≈ 0,3 · 3,2 M; 0,25 · 1,8 M = 450 000
    v, _ = _juzgar(tmp_path, e5, lambda d, s: _semilla(d, s, {"markov": corta}))
    assert v.desenlace == "CUMPLE"


def test_una_defectuosa_con_clave_por_encima_del_techo_k1_es_no_cumple(tmp_path, e5):
    alta = (dict(bits=1_500_000), dict(bits=900_000), dict(bits=440_000))  # ≤ 0,25 · buena, pero sobre el techo analítico de 0,9/periódica
    v, _ = _juzgar(tmp_path, e5, lambda d, s: _semilla(d, s, {"markov_fuerte": alta}))
    assert v.desenlace == "NO_CUMPLE" and "D/markov_fuerte/20261007" in v.resumen


def test_una_defectuosa_bajo_k1_pero_sobre_un_cuarto_de_la_buena_es_no_cumple(tmp_path, e5):
    larga = (dict(bits=1_500_000), dict(bits=900_000), dict(bits=460_000))  # techo de markov 0,8 > 460 000; pero 460 000 > 0,25 · 1,8 M
    v, _ = _juzgar(tmp_path, e5, lambda d, s: _semilla(d, s, {"markov": larga}))
    assert v.desenlace == "NO_CUMPLE" and "D/markov/" in v.resumen


def test_una_clave_defectuosa_que_no_pasa_m1_m5_cuenta_como_rechazada(tmp_path, e5):
    mala = (dict(bits=1_500_000), dict(bits=900_000), dict(bits=1_000_000, ok=False))
    v, _ = _juzgar(tmp_path, e5, lambda d, s: _semilla(d, s, {"periodica": mala}))
    assert v.desenlace == "CUMPLE"


@pytest.mark.parametrize(
    ("buena", "falla"),
    [
        ((dict(bits=2_000_000), dict(bits=1_900_000), dict(bits=0, entrega=False)), "G1"),  # la buena es rechazada
        ((dict(bits=2_000_000), dict(bits=1_900_000), dict(bits=1_400_000, segundos=100.0)), "G2"),  # 0,70 < 0,75 de la de 0.1.0
        ((dict(bits=2_000_000), dict(bits=1_900_000), dict(bits=1_800_000, segundos=180.0)), "G3"),  # 10 000 bit/s: no es ESTRICTO
    ],
)
def test_cada_criterio_de_la_buena_puede_romper_la_conjuncion(tmp_path, e5, buena, falla):
    v, _ = _juzgar(tmp_path, e5, lambda d, s: _semilla(d, s, buena=buena))
    assert v.desenlace == "NO_CUMPLE" and f"{falla}/20261007" in v.resumen


def test_d5_que_no_se_cumple_al_releer_es_una_corrida_invalida_no_un_veredicto(tmp_path, e5):
    with pytest.raises(CorridaInvalida, match="D5"):
        _juzgar(tmp_path, e5, lambda d, s: _semilla(d, s, h90=0.2))  # el 90B no ve la buena: falla el piso


def test_p5_que_no_se_cumple_al_releer_es_una_corrida_invalida(tmp_path, e5):
    def hacer(d, s):
        med = _semilla(d, s)
        e = med.e5[1]
        rs = (e.resultados[0], {**e.resultados[1], "sha256_muestra": "otra"}, e.resultados[2])
        return Medicion(
            e5=(med.e5[0], ExperimentoE5(e.corrida, e.semilla, e.fuente, e.bits_crudos, e.h_90b_fuente, e.parametros, rs), *med.e5[2:]),
            controles=med.controles,
        )

    with pytest.raises(CorridaInvalida, match="P5"):
        _juzgar(tmp_path, e5, hacer)


def test_parametros_movidos_respecto_de_la_declaracion_invalidan(tmp_path, e5):
    def hacer(d, s):
        med = _semilla(d, s)
        e = med.e5[1]
        return Medicion(
            e5=(
                med.e5[0],
                ExperimentoE5(e.corrida, e.semilla, e.fuente, e.bits_crudos, e.h_90b_fuente, {**e.parametros, "peso": 0.5}, e.resultados),
                *med.e5[2:],
            ),
            controles=med.controles,
        )

    with pytest.raises(CorridaInvalida, match="parámetros"):
        _juzgar(tmp_path, e5, hacer)


def test_falta_una_semilla_o_una_fuente_no_es_juzgable(tmp_path, e5):
    with pytest.raises(CorridaInvalida):
        _juzgar(tmp_path, e5, lambda d, s: Medicion(e5=_semilla(d, s).e5[:3], controles={"D5": True, "P5": True}))


def test_el_techo_k1_es_la_min_entropia_analitica_por_los_bits_crudos():
    assert c.techo_k1(1000, 0.0, 0.5) == 1000  # sin defecto y con bits frescos justos: todo es entropía
    assert c.techo_k1(1000, 0.9, 0.51) == math.floor(-math.log2(0.9 + 0.1 * 0.51) * 1000)
