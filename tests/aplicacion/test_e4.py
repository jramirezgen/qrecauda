"""E4 (docs/preinscripciones/E4.md): el ejecutor y el juez, de punta a punta con un contraste de juguete.

REAL: el pipeline, el validador estadístico, los criterios, el juez y la declaración declaraciones/E4.toml (sólo se lee).
DOBLE: el hardware y su gemelo (`ContrasteFalso`: bits con el sesgo por qubit que el test ordena) y el historial git."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from test_juez import HistorialFalso, LibroEnMemoria

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.prng import FuentePeriodica, FuentePrng
from qrecauda.aplicacion.ejecutor_e4 import EjecutorE4, mascaras_de
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.datos import Declaracion, InformeCorrida
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia

RAIZ = Path(__file__).resolve().parents[2]
SHOTS = 64_000  # 8 PUBs de 8 000: la cruda da 64 000 bits y la clave > 10 240 (mínimo del χ² de bytes)
SEMILLAS = (20261007, 20261008, 20261009)


class RelojFalso:
    t = 0

    def ahora_ns(self) -> int:
        RelojFalso.t += 1_000_000
        return RelojFalso.t


def _bits(rng: np.random.Generator, sesgos: Sequence[float], shots: int) -> Bits:
    """Qubit-mayor: el qubit q vale 1 con probabilidad ½ + sesgos[q]."""
    d = np.vstack([(rng.random(shots) < 0.5 + s).astype(np.uint8) for s in sesgos])
    return Bits(np.ascontiguousarray(d).reshape(-1))


class _Cara:
    def __init__(self, m: Muestra) -> None:
        self.m = m

    def generar(self, qubits: int, shots: int) -> Muestra:
        assert (self.m.qubits, self.m.shots) == (qubits, shots)
        return self.m


class ContrasteFalso:
    """Un trabajo ficticio: hardware y gemelo con el sesgo por qubit pedido; el twirling del hardware lo cancela (sesgo ≈ 0)."""

    def __init__(
        self,
        decl: Declaracion,
        semilla: int,
        *,
        hw: Sequence[float],
        gemelo: Sequence[float],
        twirl_hw: Sequence[float] | None = None,
        twirl_bits: Bits | None = None,
        job_id: str | None = None,
        backend: str = "ibm_doble",
        origen: Origen = Origen.HARDWARE_IBM,
    ) -> None:
        rng = np.random.default_rng(semilla)
        q, por = decl.qubits, decl.shots // (mascaras_de(decl) + 1)
        k = mascaras_de(decl)
        nulo = [0.0] * q
        proc = Procedencia(backend, job_id or f"job-{semilla}", "9.9")
        self._hw = (
            Muestra(_bits(rng, hw, por), origen, q, por, False, proc),
            Muestra(twirl_bits or _bits(rng, twirl_hw or nulo, por * k), origen, q, por * k, True, proc),
        )
        pg = Procedencia("AerSimulator(gemelo)", "", "x")
        self._gem = (
            Muestra(_bits(rng, gemelo, por), Origen.SIMULADOR_AER, q, por, False, pg),
            Muestra(_bits(rng, nulo, por * k), Origen.SIMULADOR_AER, q, por * k, True, pg),
        )
        self._job = proc.job_id

    def cruda(self) -> _Cara:
        return _Cara(self._hw[0])

    def con_twirling(self) -> _Cara:
        return _Cara(self._hw[1])

    def gemelo_cruda(self) -> _Cara:
        return _Cara(self._gem[0])

    def gemelo_con_twirling(self) -> _Cara:
        return _Cara(self._gem[1])

    def registro(self) -> dict[str, object]:
        return {"job_id": self._job, "backend": "ibm_doble", "cola_s": 12.5, "ejecucion_s": 3.0, "uso_qpu_s": 2.0}


def _suave(q: int = 8) -> list[float]:
    return [0.004 * (-1) ** i for i in range(q)]


@pytest.fixture
def e4() -> Declaracion:
    d = cargar_declaracion(Path("declaraciones/E4.toml"), RAIZ)
    return replace(d, shots=SHOTS)


def _ejecutor(contraste) -> EjecutorE4:
    return EjecutorE4(FuentePrng, contraste, ValidadorEstadistico(), RelojFalso(), HistorialFalso(), lambda: {"python": "x"})


def _correr_y_juzgar(e4: Declaracion, tmp_path: Path, contraste):
    juez = CorrerYJuzgar(_ejecutor(contraste), AlmacenJson(tmp_path), HistorialFalso(), LibroEnMemoria(), {"python": "x"})
    return juez, juez.correr(e4)


def _bueno(decl, semilla):
    return ContrasteFalso(decl, semilla, hw=_suave(), gemelo=_suave())


# ------------------------------------------------------------------ la declaración


def test_la_declaracion_de_e4_es_la_preinscrita(e4: Declaracion) -> None:
    assert e4.eureka == "E4" and e4.nodo_corrida == "C.E4" and len(e4.semillas) == 3
    assert e4.lista("corridas", "ids") == ("C.E4a", "C.E4b", "C.E4c", "C.E4d", "C.E4e")
    assert e4.lista("controles", "requeridos") == ("N1", "S1", "V1")
    assert "docs/preinscripciones/E4.md" in e4.rutas


def test_los_cien_mil_disparos_reales_se_reparten_en_ocho_pubs_iguales() -> None:
    d = cargar_declaracion(Path("declaraciones/E4.toml"), RAIZ)
    assert (d.shots, mascaras_de(d), d.shots // 8) == (100_000, 7, 12_500)


def test_mascaras_que_no_reparten_igual_se_rechazan(e4: Declaracion) -> None:
    mal = replace(e4, shots=100, tablas={**e4.tablas, "hardware": {**e4.tablas["hardware"], "mascaras": 6}})
    with pytest.raises(EntradaInvalida, match="PUBs iguales"):
        mascaras_de(mal)


# ------------------------------------------------------------------ el ejecutor


def test_cinco_informes_por_semilla_con_el_pipeline_real(e4: Declaracion) -> None:
    med = _ejecutor(_bueno).ejecutar(e4, SEMILLAS[0])
    assert [i.corrida for i in med.informes] == ["C.E4a", "C.E4b", "C.E4c", "C.E4d", "C.E4e"]
    assert all(isinstance(i, InformeCorrida) and i.eureka == "E4" for i in med.informes)
    assert med.controles == {"N1": True, "S1": True, "V1": True}


def test_los_informes_del_hardware_llevan_el_registro_del_trabajo_y_los_otros_no(e4: Declaracion) -> None:
    por = {i.corrida: i for i in _ejecutor(_bueno).ejecutar(e4, SEMILLAS[0]).informes}
    for k in ("C.E4d", "C.E4e"):
        assert por[k].origen is Origen.HARDWARE_IBM and por[k].reporte["trabajo"]["cola_s"] == 12.5  # type: ignore[index]
        assert por[k].procedencia.job_id == f"job-{SEMILLAS[0]}"
    for k in ("C.E4a", "C.E4b", "C.E4c"):
        assert "trabajo" not in por[k].reporte and por[k].origen is not Origen.HARDWARE_IBM


def test_cada_informe_trae_los_sesgos_por_qubit_con_signo(e4: Declaracion) -> None:
    por = {i.corrida: i for i in _ejecutor(lambda d, s: ContrasteFalso(d, s, hw=[0.1] * 8, gemelo=[0.0] * 8)).ejecutar(e4, 1).informes}
    sesgos = por["C.E4d"].reporte["sesgos_por_qubit"]
    assert len(sesgos) == 8 and all(0.08 < x < 0.12 for x in sesgos)  # type: ignore[union-attr]
    assert por["C.E4d"].reporte["sesgo_medio_por_qubit"] == pytest.approx(sum(abs(x) for x in sesgos) / 8)  # type: ignore[arg-type,union-attr]


def test_los_disparos_del_gemelo_son_los_del_hardware(e4: Declaracion) -> None:
    por = {i.corrida: i for i in _ejecutor(_bueno).ejecutar(e4, 1).informes}
    assert (por["C.E4b"].shots, por["C.E4c"].shots) == (por["C.E4d"].shots, por["C.E4e"].shots) == (8_000, 56_000)


def test_un_backend_falso_hace_fallar_v1_y_un_prng_roto_n1(e4: Declaracion) -> None:
    med = _ejecutor(lambda d, s: ContrasteFalso(d, s, hw=_suave(), gemelo=_suave(), backend="fake_sherbrooke")).ejecutar(e4, 1)
    assert med.controles["V1"] is False and med.controles["S1"] is True


def test_el_ejecutor_se_niega_a_medir_otra_eureka(e4: Declaracion) -> None:
    with pytest.raises(EntradaInvalida, match="mide E4"):
        _ejecutor(_bueno).ejecutar(replace(e4, eureka="E1"), 1)


def test_el_envio_va_antes_de_cualquier_reloj_de_cadena(e4: Declaracion) -> None:
    """El ejecutor pide las dos caras (que envían) ANTES de arrancar el primer pipeline: la cola no entra en M6/M7."""
    orden: list[str] = []

    class Espia(ContrasteFalso):
        def cruda(self):
            orden.append("envio")
            return super().cruda()

    class RelojEspia(RelojFalso):
        def ahora_ns(self) -> int:
            orden.append("reloj")
            return super().ahora_ns()

    EjecutorE4(
        FuentePrng, lambda d, s: Espia(d, s, hw=_suave(), gemelo=_suave()), ValidadorEstadistico(), RelojEspia(), HistorialFalso(), dict
    ).ejecutar(e4, 1)
    assert orden[0] == "envio" and "reloj" in orden


# ------------------------------------------------------------------ el juez


def test_cumple_cuando_hardware_y_gemelo_coinciden_y_la_clave_pasa(e4: Declaracion, tmp_path: Path) -> None:
    juez, m = _correr_y_juzgar(e4, tmp_path, _bueno)
    assert len(m.artefactos) == 15 and set(m.controles) == {"N1", "S1", "V1"}
    v = juez.juzgar(e4)
    assert v.desenlace == "CUMPLE", v.resumen
    ids = {c.id.split("/")[0] for c in v.criterios}
    assert {"H1", "H2", "cola_y_ejecucion", "M6_M7_hw", "M6_M7_aer", "twirling_hw"} <= ids
    assert all(not c.decide for c in v.criterios if c.id.split("/")[0] not in ("H1", "H2"))
    assert "no certifica aleatoriedad cuántica" in v.resumen.lower()


def test_el_veredicto_reporta_cola_y_ejecucion_aparte(e4: Declaracion, tmp_path: Path) -> None:
    juez, _ = _correr_y_juzgar(e4, tmp_path, _bueno)
    cola = [c for c in juez.juzgar(e4).criterios if c.id.startswith("cola_y_ejecucion")]
    assert len(cola) == 3 and all("cola 12.5 s" in c.detalle and "ejecución 3 s" in c.detalle and not c.decide for c in cola)


def test_cumple_parcial_si_un_qubit_se_aparta_mas_de_la_tolerancia(e4: Declaracion, tmp_path: Path) -> None:
    def contraste(d, s):
        hw = _suave()
        hw[3] = 0.12  # un qubit con mucho sesgo que el gemelo no predice
        return ContrasteFalso(d, s, hw=hw, gemelo=_suave())

    juez, _ = _correr_y_juzgar(e4, tmp_path, contraste)
    v = juez.juzgar(e4)
    assert v.desenlace == "CUMPLE_PARCIAL"
    assert not any(c.cumple for c in v.criterios if c.id.startswith("H1")) and all(c.cumple for c in v.criterios if c.id.startswith("H2"))


def test_no_cumple_si_la_clave_del_hardware_con_twirling_falla(e4: Declaracion, tmp_path: Path) -> None:
    """Una fuente periódica que el twirling no arregla (patrón 001011) deja una clave que falla M1–M5."""

    def contraste(d, s):
        por, k = d.shots // 8, 7
        markov = FuentePeriodica("001011").generar(1, d.qubits * por * k).bits
        return ContrasteFalso(d, s, hw=_suave(), gemelo=_suave(), twirl_bits=markov)

    juez, _ = _correr_y_juzgar(e4, tmp_path, contraste)
    v = juez.juzgar(e4)
    assert v.desenlace == "NO_CUMPLE" and "H2" in v.resumen


def test_un_sesgo_grande_que_sobrevive_al_twirling_no_rompe_la_clave_hallazgo_r00_1(e4: Declaracion, tmp_path: Path) -> None:
    """H2 es débil por construcción: Toeplitz limpia el sesgo (R.00-1). Por eso H1 y los sesgos por qubit se reportan aparte."""
    juez, _ = _correr_y_juzgar(e4, tmp_path, lambda d, s: ContrasteFalso(d, s, hw=_suave(), gemelo=_suave(), twirl_hw=[0.2] * 8))
    assert juez.juzgar(e4).desenlace == "CUMPLE"


def test_un_trabajo_repetido_invalida_v1_aunque_el_manifiesto_diga_ok(e4: Declaracion, tmp_path: Path) -> None:
    juez, _ = _correr_y_juzgar(e4, tmp_path, lambda d, s: ContrasteFalso(d, s, hw=_suave(), gemelo=_suave(), job_id="el-mismo"))
    with pytest.raises(CorridaInvalida, match="V1"):
        juez.juzgar(e4)


def test_un_ensayo_no_se_juzga(e4: Declaracion, tmp_path: Path) -> None:
    ens = lambda d, s: ContrasteFalso(d, s, hw=_suave(), gemelo=_suave(), origen=Origen.SIMULADOR_AER)  # noqa: E731
    juez, m = _correr_y_juzgar(e4, tmp_path, ens)
    assert m.controles["V1"] is False
    with pytest.raises(CorridaInvalida, match="V1"):
        juez.juzgar(e4)


def test_el_juez_exige_n1_s1_y_v1_del_manifiesto(e4: Declaracion, tmp_path: Path) -> None:
    class SinS1(EjecutorE4):
        def ejecutar(self, decl, semilla):  # type: ignore[no-untyped-def]
            m = super().ejecutar(decl, semilla)
            return replace(m, controles={k: v for k, v in m.controles.items() if k != "S1"})

    juez = CorrerYJuzgar(
        SinS1(FuentePrng, _bueno, ValidadorEstadistico(), RelojFalso(), HistorialFalso(), dict),
        AlmacenJson(tmp_path), HistorialFalso(), LibroEnMemoria(), {},
    )  # fmt: skip
    juez.correr(e4)
    with pytest.raises(CorridaInvalida, match="S1"):
        juez.juzgar(e4)


def test_los_artefactos_se_pueden_releer_y_son_json_puro(e4: Declaracion, tmp_path: Path) -> None:
    _, m = _correr_y_juzgar(e4, tmp_path, _bueno)
    almacen = AlmacenJson(tmp_path)
    nombre = next(n for n, _, _ in m.artefactos if "informe_003" in n)
    assert InformeCorrida.desde_mapa(almacen.leer(nombre)).corrida == "C.E4d"
