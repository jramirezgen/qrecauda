"""EjecutorE2: lo preinscrito en docs/preinscripciones/E2.md, probado con un laboratorio FALSO (rápido, sin Aer).

Los parámetros salen de declaraciones/E2.toml; el laboratorio falso inyecta un sesgo conocido para ver que el ejecutor lo mide,
lo mitiga y lo juzga como manda la preinscripción. La cadena real con Aer está en tests/integracion/test_e2_e3_reales.py.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pytest

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.aplicacion.ejecutor_e2 import EjecutorE2
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.datos import Declaracion, RuidoDeLectura
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, FuenteNoDisponible
from qrecauda.dominio.muestra import Muestra, Origen

RAIZ = Path(__file__).resolve().parents[2]
SEMILLA = 20261007


class FuenteFalsa:
    def __init__(self, p1: float, semilla: int) -> None:
        self.p1, self.semilla = p1, semilla

    def generar(self, qubits: int, shots: int) -> Muestra:
        rng = np.random.default_rng(self.semilla)
        return Muestra(Bits((rng.random(qubits * shots) < self.p1).astype(np.uint8)), Origen.SIMULADOR_AER, qubits, shots)


class TwirlingFalso:
    def __init__(self, p1: float, semilla: int) -> None:
        self.p1, self.semilla = p1, semilla

    def mitigar(self, muestra: Muestra) -> Muestra:
        rng = np.random.default_rng(self.semilla + 99)
        return muestra.mitigada_con(Bits((rng.random(len(muestra.bits)) < self.p1).astype(np.uint8)), conserva_bits_por_disparo=True)


class EstimadorFalso:
    def __init__(self, factor: float) -> None:
        self.factor = factor

    def estimar(self, muestra: Muestra) -> float:
        return self.factor * (1.0 - 2.0 * muestra.bits.proporcion_de_unos())


@dataclass
class LabFalso:
    ve_el_sesgo: bool = True  # False: la fuente ignora el canal (el detector estaría ciego)
    twirling_sesga_sin_ruido: bool = False
    factor_tecnica: float = 1.0  # ZNE/PEC: ⟨Z⟩ después = factor · ⟨Z⟩ antes
    mthree_disponible: bool = True
    realista_p1: float = 0.504

    def __post_init__(self) -> None:
        self.llamadas: list[tuple[str, str, int]] = []

    def _p1(self, ruido: RuidoDeLectura) -> float:
        if ruido.realista:
            return self.realista_p1
        if ruido.canal is None or not self.ve_el_sesgo:
            return 0.5
        return 0.5 + (ruido.canal[0] - ruido.canal[1]) / 2  # H|0> leído por el canal: p(1) = ½ + (p(1|0) − p(0|1))/2

    def fuente(self, ruido, semilla):
        self.llamadas.append(("fuente", ruido.nombre, semilla))
        return FuenteFalsa(self._p1(ruido), semilla)

    def twirling(self, ruido, semilla, bloque):
        self.llamadas.append((f"twirling:{bloque}", ruido.nombre, semilla))
        sesga = self.twirling_sesga_sin_ruido and ruido.canal is None and not ruido.realista
        return TwirlingFalso(0.5 + (0.03 if sesga else 0.0), semilla)

    def zne(self, ruido, semilla):
        self.llamadas.append(("zne", ruido.nombre, semilla))
        return EstimadorFalso(self.factor_tecnica)

    def pec(self, ruido, semilla):
        self.llamadas.append(("pec", ruido.nombre, semilla))
        return EstimadorFalso(self.factor_tecnica)

    def sesgo_mthree(self, ruido, qubits, shots, semilla):
        self.llamadas.append(("mthree", ruido.nombre, semilla))
        if not self.mthree_disponible:
            raise FuenteNoDisponible("sin mthree")
        return 0.0299, 0.0011


class BitacoraEnMemoria:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    def registrar(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))


@pytest.fixture(scope="module")
def decl() -> Declaracion:
    return cargar_declaracion(Path("declaraciones/E2.toml"), RAIZ)


def _medir(decl, lab=None, semilla=SEMILLA, bitacora=None):
    lab = lab or LabFalso()
    return lab, EjecutorE2(lab, bitacora).ejecutar(decl, semilla)


def _celda(m, nivel, tecnica):
    (c,) = [c for c in m.e2 if c.nivel == nivel and c.tecnica == tecnica]
    return c


@pytest.fixture(scope="module")
def sano(decl):
    return _medir(decl)


# ---------------------------------------------------------------- lo que mide


def test_hay_una_celda_ninguna_y_una_twirling_por_nivel_y_semilla(sano, decl):
    _, m = sano
    for nivel in ("bajo", "medio", "alto", "realista"):
        assert _celda(m, nivel, "ninguna").shots == decl.shots == _celda(m, nivel, "twirling_propio").shots
        assert _celda(m, nivel, "ninguna").semilla == SEMILLA and _celda(m, nivel, "ninguna").corrida == "C.E2"


def test_el_sesgo_crudo_de_la_twirling_es_el_de_la_celda_ninguna_de_la_misma_semilla_y_nivel(sano):
    _, m = sano
    for nivel in ("bajo", "medio", "alto", "realista"):
        assert _celda(m, nivel, "twirling_propio").sesgo_crudo == _celda(m, nivel, "ninguna").sesgo_residual


def test_el_crudo_ve_el_sesgo_analitico_y_el_residuo_cae_al_piso(sano):
    _, m = sano
    assert _celda(m, "medio", "ninguna").sesgo_residual == pytest.approx(0.030, abs=0.002)
    assert _celda(m, "alto", "ninguna").sesgo_residual == pytest.approx(0.050, abs=0.002)
    assert _celda(m, "bajo", "ninguna").sesgo_residual == pytest.approx(0.010, abs=0.002)  # empate con M1: no es un caso cómodo
    assert _celda(m, "medio", "twirling_propio").sesgo_residual < 0.003


def test_el_estadistico_es_la_media_por_qubit_no_el_pooled(decl):
    """Dos qubits de signo opuesto: el pooled daría 0; la media de |p̂_q − ½| no."""

    class DosSignos(LabFalso):
        def fuente(self, ruido, semilla):
            class F:
                def generar(_, qubits, shots):
                    bits = np.concatenate([np.ones(shots // 2 + 5000), np.zeros(shots - shots // 2 - 5000)] * (qubits // 2))
                    bits2 = np.concatenate([np.zeros(shots // 2 + 5000), np.ones(shots - shots // 2 - 5000)] * (qubits // 2))
                    return Muestra(Bits(np.concatenate([bits, bits2]).astype(np.uint8)), Origen.SIMULADOR_AER, qubits, shots)

            return F()

    _, m = _medir(decl, DosSignos())
    assert _celda(m, "medio", "ninguna").sesgo_residual == pytest.approx(5000 / 400_000)


def test_el_intervalo_es_un_bootstrap_determinista_que_encierra_el_punto(decl):
    _, a = _medir(decl)
    _, b = _medir(decl)
    c = _celda(a, "medio", "ninguna")
    assert c.intervalo_residual == _celda(b, "medio", "ninguna").intervalo_residual
    lo, hi = c.intervalo_residual
    assert lo < c.sesgo_residual < hi and hi - lo < 0.002  # semiancho de ≈ 0,00055 a este tamaño


def test_el_intervalo_usa_la_semilla_de_la_celda_mas_uno_y_las_remuestras_declaradas(decl):
    """Otra semilla de bootstrap daría otro intervalo: se reproduce a mano con default_rng(semilla + 1)."""
    _, m = _medir(decl)
    c = _celda(m, "medio", "ninguna")
    from qrecauda.dominio.sesgo_por_qubit import frecuencias_de_unos

    muestra = FuenteFalsa(0.47, SEMILLA).generar(8, decl.shots)
    p = frecuencias_de_unos(muestra.bits, 8)
    rng = np.random.default_rng(SEMILLA + 1)
    B = int(decl.numero("intervalo", "remuestras"))
    sim = np.abs(rng.binomial(decl.shots, p, size=(B, 8)) / decl.shots - 0.5).mean(axis=1)
    lo, hi = np.percentile(sim, [2.5, 97.5])
    assert c.intervalo_residual == pytest.approx((lo, hi))


def test_el_ruido_sale_de_la_declaracion_no_de_constantes(decl):
    """P.E2: manda PARAMETROS.toml. Si el TOML cambia el bajo, el laboratorio recibe el canal del TOML."""
    tablas = {k: dict(v) for k, v in decl.tablas.items()}
    tablas["ruido_lectura"]["bajo"] = [0.04, 0.06]
    visto = {}

    class Espia(LabFalso):
        def fuente(self, ruido, semilla):
            visto[ruido.nombre] = ruido.canal
            return super().fuente(ruido, semilla)

    _medir(replace(decl, tablas=tablas), Espia())
    assert visto["bajo"] == (0.04, 0.06) and visto["medio"] == (0.02, 0.08) and visto["alto"] == (0.05, 0.15)
    assert visto["realista"] is None and visto["sin_ruido"] is None and visto["simetrico"] == (0.05, 0.05)


def test_el_twirling_usa_el_bloque_declarado_y_la_semilla_de_la_celda(sano):
    lab, _ = sano
    tw = [c for c in lab.llamadas if c[0].startswith("twirling")]
    assert tw and all(c[0] == "twirling:200" and c[2] == SEMILLA for c in tw)


def test_el_realista_lleva_el_maximo_por_qubit(sano):
    _, m = sano
    assert _celda(m, "realista", "twirling_propio").sesgo_maximo_por_qubit is not None
    assert _celda(m, "realista", "twirling_propio").sesgo_maximo_por_qubit >= _celda(m, "realista", "twirling_propio").sesgo_residual


# ---------------------------------------------------------------- controles


def test_c1_c2_c3_pasan_con_un_aparato_sano(sano):
    _, m = sano
    assert m.controles["C1"] and m.controles["C2"] and m.controles["C3"]
    assert _celda(m, "sin_ruido", "twirling_propio").sesgo_residual <= 0.003
    assert _celda(m, "simetrico", "twirling_propio").sesgo_residual <= 0.003


def test_c1_falla_si_el_detector_no_ve_el_sesgo_inyectado(decl):
    _, m = _medir(decl, LabFalso(ve_el_sesgo=False))
    assert m.controles["C1"] is False


def test_c2_falla_si_el_twirling_introduce_sesgo_sin_ruido(decl):
    _, m = _medir(decl, LabFalso(twirling_sesga_sin_ruido=True))
    assert m.controles["C2"] is False and m.controles["C3"] is True


def test_el_control_invalido_hace_que_el_juez_se_niegue_a_dar_veredicto(decl, tmp_path):
    class Hist:
        def ultimo_commit(self, rutas):
            return "a" * 40

        def commit_actual(self):
            return "b" * 40

        def modificado(self, rutas):
            return False

        def precede(self, a, d):
            return True

    class Libro:
        def anadir(self, linea):
            pass

    juez = CorrerYJuzgar(EjecutorE2(LabFalso(ve_el_sesgo=False)), AlmacenJson(tmp_path), Hist(), Libro(), {})
    juez.correr(decl)
    with pytest.raises(CorridaInvalida, match="C1"):
        juez.juzgar(decl)


def test_un_aparato_sano_se_juzga_cumple_de_punta_a_punta(decl, tmp_path):
    class Hist:
        def ultimo_commit(self, rutas):
            return "a" * 40

        def commit_actual(self):
            return "b" * 40

        def modificado(self, rutas):
            return False

        def precede(self, a, d):
            return True

    class Libro:
        def __init__(self):
            self.v = []

        def anadir(self, linea):
            self.v.append(linea)

    libro = Libro()
    juez = CorrerYJuzgar(EjecutorE2(LabFalso()), AlmacenJson(tmp_path), Hist(), libro, {})
    juez.correr(decl)
    v = juez.juzgar(decl)
    # las celdas extra (sin_ruido, simetrico, zne, pec, mthree) no cuentan para el veredicto
    assert v.desenlace == "CUMPLE", v.resumen


# ---------------------------------------------------------------- C4 (puerta ZNE/PEC) y C5 (contraste)


def test_c4_sin_efecto_se_registra_y_hay_celdas_zne_y_pec_en_medio(sano):
    lab, m = sano
    assert m.controles["C4"] is True
    assert {c.tecnica for c in m.e2 if c.nivel == "medio"} >= {"zne", "pec"}
    assert ("zne", "medio", SEMILLA) in lab.llamadas and ("pec", "medio", SEMILLA) in lab.llamadas
    assert not [c for c in lab.llamadas if c[0] in ("zne", "pec") and c[1] != "medio"]  # C4 es sólo en medio


def test_c4_un_efecto_es_hallazgo_no_error_y_no_invalida_el_veredicto(decl):
    _, m = _medir(decl, LabFalso(factor_tecnica=0.5))
    assert m.controles["C4"] is False  # «mueve ≥ 10 %»: hallazgo a reportar
    assert m.controles["C1"] and m.controles["C2"] and m.controles["C3"]
    zne = _celda(m, "medio", "zne")
    assert zne.sesgo_residual == pytest.approx(zne.sesgo_crudo * 0.5, rel=1e-6)  # lo medido, sin reinterpretar


def test_c4_el_umbral_es_relativo_al_z_antes(decl):
    _, justo_debajo = _medir(decl, LabFalso(factor_tecnica=0.91))  # |Δ| = 0,09·|Z| < 0,1·|Z|
    _, justo_encima = _medir(decl, LabFalso(factor_tecnica=0.89))
    assert justo_debajo.controles["C4"] is True and justo_encima.controles["C4"] is False


def test_c5_mthree_se_reporta_como_celda_de_contraste(sano):
    _, m = sano
    assert m.controles["C5"] is True
    for nivel in ("bajo", "medio", "alto"):
        c = _celda(m, nivel, "mthree")
        assert (c.sesgo_crudo, c.sesgo_residual) == (0.0299, 0.0011)


def test_c5_si_mthree_no_corre_se_declara_no_medido_y_el_resto_sigue(decl):
    bit = BitacoraEnMemoria()
    _, m = _medir(decl, LabFalso(mthree_disponible=False), bitacora=bit)
    assert "C5" not in m.controles and not [c for c in m.e2 if c.tecnica == "mthree"]
    assert any(e == "c5_no_medido" for e, _ in bit.eventos)
    assert m.controles["C1"]


def test_la_corrida_no_decide_con_mthree_ni_zne_ni_pec(decl):
    """El juez sólo mira las técnicas de `decide`: las celdas de contraste y puerta no entran en ningún criterio."""
    _, m = _medir(decl, LabFalso(factor_tecnica=0.2))
    decide = set(decl.lista("tecnicas", "decide"))
    assert {c.tecnica for c in m.e2} - decide == {"zne", "pec", "mthree"}
