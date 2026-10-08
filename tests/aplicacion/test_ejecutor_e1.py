"""EjecutorE1: las cuatro corridas por semilla de docs/preinscripciones/E1.md, con parámetros DIMINUTOS y dobles de Aer y del 90B.

Real: el pipeline, el validador estadístico, los criterios y el juez. Doble: la fuente "Aer" (un PRNG con el sesgo analítico del ruido
medio), el twirling (otra muestra del mismo canal, simetrizada), el 90B y el entorno. La declaración es la REAL de E1 (sólo se lee)
con shots y bits de C.E1d reducidos por `replace`: se prueba la lógica, no la estadística de 3,2 M de bits.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from test_juez import HistorialFalso, LibroEnMemoria

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.prng import FuenteMarkov, FuentePeriodica, FuentePrng
from qrecauda.aplicacion.ejecutor_e1 import EjecutorE1
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.datos import Declaracion, RuidoDeLectura
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia

RAIZ = Path(__file__).resolve().parents[2]
SHOTS, BITS_D = 5_000, 40_000  # 8 × 5 000 = 40 000 bits crudos; C.E1d con 40 000 bits por fuente


class RelojFalso:
    t = 0

    def ahora_ns(self) -> int:
        RelojFalso.t += 1000
        return RelojFalso.t


class FuenteAerFalsa:
    """El canal de lectura medio: P(1) = 0,47 exacta (sesgo analítico 0,03). Determinista dada la semilla."""

    def __init__(self, semilla: int, p1: float = 0.47) -> None:
        self.semilla, self.p1 = semilla, p1

    def generar(self, qubits: int, shots: int) -> Muestra:
        rng = np.random.default_rng(self.semilla)
        n = qubits * shots
        bits = np.zeros(n, dtype=np.uint8)
        bits[: round(self.p1 * n)] = 1  # proporción EXACTA (el sesgo medido = el inyectado), mezclada
        rng.shuffle(bits)
        return Muestra(Bits(bits), Origen.SIMULADOR_AER, qubits, shots, procedencia=Procedencia("AerSimulator", "", "x"))


class TwirlingFalso:
    """Re-ejecuta (como el real): una muestra NUEVA del canal, pero simetrizada (P(1) = 0,5)."""

    def __init__(self, semilla: int) -> None:
        self.semilla = semilla

    def mitigar(self, muestra: Muestra) -> Muestra:
        nueva = FuenteAerFalsa(self.semilla + 1, 0.5).generar(muestra.qubits, muestra.shots)
        return muestra.mitigada_con(nueva.bits, conserva_bits_por_disparo=True)


class LabFalso:
    def __init__(self, p1: float = 0.47) -> None:
        self.p1, self.pedidos = p1, []

    def fuente(self, ruido: RuidoDeLectura, semilla: int):
        self.pedidos.append(("fuente", ruido.nombre, ruido.canal, semilla))
        return FuenteAerFalsa(semilla, self.p1)

    def twirling(self, ruido: RuidoDeLectura, semilla: int, bloque: int):
        self.pedidos.append(("twirling", ruido.nombre, semilla, bloque))
        return TwirlingFalso(semilla)


class Estimador90bFalso:
    """90B de juguete: 0,97 si la frecuencia de unos está a 0,05 de ½ y el bit cambia ~½ de las veces; si no, 0,2. Registra sus llamadas."""

    def __init__(self) -> None:
        self.llamadas: list[Bits] = []

    def estimar(self, bits: Bits) -> float:
        self.llamadas.append(bits)
        d = bits.datos
        cambia = float((d[1:] != d[:-1]).mean())
        return 0.97 if abs(bits.proporcion_de_unos() - 0.5) < 0.05 and abs(cambia - 0.5) < 0.05 else 0.2


def _fuentes_de_control(decl: Declaracion, semilla: int):
    c = decl.tabla("criterios")["c_e1d"]
    return {
        "sesgada": FuentePrng(semilla, sesgo=float(c["sesgada_p1"]) - 0.5),  # type: ignore[arg-type,index]
        "periodica": FuentePeriodica(str(c["periodica"])),  # type: ignore[index]
        "markov": FuenteMarkov(semilla, float(c["markov_permanencia"])),  # type: ignore[arg-type,index]
        "ideal": FuentePrng(semilla),
    }


def _proporciones(bits: Bits, secuencias: int, longitud: int, alfa: float):
    return {"M3": {"aprobados": secuencias, "total": secuencias, "proporcion": 1.0, "minimo": 0.959, "cumple": True}}


@pytest.fixture
def e1() -> Declaracion:
    d = cargar_declaracion(Path("declaraciones/E1.toml"), RAIZ)
    cadena = {**d.tablas["cadena"], "shots": SHOTS}
    c_e1d = {**d.tablas["criterios"]["c_e1d"], "bits": BITS_D}  # type: ignore[dict-item]
    return replace(d, shots=SHOTS, tablas={**d.tablas, "cadena": cadena, "criterios": {**d.tablas["criterios"], "c_e1d": c_e1d}})  # type: ignore[arg-type]


def _ejecutor(lab=None, est=None, **kw) -> EjecutorE1:
    return EjecutorE1(
        lab or LabFalso(), lambda s: FuentePrng(s), _fuentes_de_control, ValidadorEstadistico(), est or Estimador90bFalso(),
        RelojFalso(), HistorialFalso(), lambda: {"python": "3.13"}, _proporciones, **kw,
    )  # fmt: skip


def test_una_semilla_produce_las_tres_corridas_de_pipeline_y_las_cuatro_fuentes(e1):
    med = _ejecutor().ejecutar(e1, 20261007)
    assert [i.corrida for i in med.informes] == ["C.E1a", "C.E1b", "C.E1c"]
    assert [f.fuente for f in med.fuentes] == ["sesgada", "periodica", "markov", "ideal"] and {f.corrida for f in med.fuentes} == {"C.E1d"}
    assert {i.semilla for i in med.informes} == {20261007} and {f.bits for f in med.fuentes} == {BITS_D}
    assert set(med.controles) == {"N1", "D1", "P1"} and all(med.controles.values())
    a, b, c = med.informes
    assert (a.origen, b.origen) == (Origen.PRNG_CLASICO, Origen.SIMULADOR_AER) and (a.mitigada, b.mitigada, c.mitigada) == (
        False,
        False,
        True,
    )
    assert "mitigada" not in a.etapas and "mitigada" not in b.etapas and set(c.etapas) == {"cruda", "mitigada", "clave"}
    for i in med.informes:  # M1 en los tres puntos aunque el validador sea el que sea
        assert all(any(m.metrica.value == "M1_sesgo" for m in ms) for ms in i.etapas.values())
        assert i.preinscripcion_sha == "a" * 40 and i.commit == "b" * 40 and i.entorno == {"python": "3.13"} and i.eureka == "E1"


def test_pide_al_laboratorio_el_nivel_medio_con_la_semilla_de_la_corrida_y_el_bloque_declarado(e1):
    lab = LabFalso()
    _ejecutor(lab).ejecutar(e1, 20261008)
    assert lab.pedidos == [
        ("fuente", "medio", (0.02, 0.08), 20261008),
        ("fuente", "medio", (0.02, 0.08), 20261008),
        ("twirling", "medio", 20261008, 200),
    ]


def test_los_criterios_salen_de_los_datos_el_sesgo_inyectado_se_ve_y_la_mitigada_lo_baja(e1):
    a, b, c = _ejecutor().ejecutar(e1, 20261007).informes
    m1 = lambda i, e: next(m for m in i.etapas[e] if m.metrica.value == "M1_sesgo")  # noqa: E731
    assert abs(m1(b, "cruda").valor - 0.03) < 1e-9 and not m1(b, "cruda").cumple  # D1 y B1
    assert m1(c, "mitigada").cumple and m1(a, "cruda").cumple


def test_las_crudas_de_c_e1b_y_c_e1c_se_comparan_por_huella_y_el_reporte_lleva_lo_informativo(e1):
    est = Estimador90bFalso()
    _, b, c = _ejecutor(est=est).ejecutar(e1, 20261007).informes
    assert b.sha256_muestra_cruda == c.sha256_muestra_cruda  # ⚠️ abierto 3: el twirling no toca la cruda; se verifica, no se supone
    assert c.reporte["sha256_muestra_mitigada"] != c.sha256_muestra_cruda
    assert set(b.reporte) >= {"h_90b_cruda"} and set(c.reporte) >= {"h_90b_cruda", "h_90b_mitigada", "proporcion_nist"}
    assert c.reporte["h_90b_cruda"] == b.reporte["h_90b_cruda"]
    # misma huella ⇒ mismo 90B, calculado UNA vez (cuesta minutos): cruda (compartida), mitigada y las cuatro fuentes
    assert len(est.llamadas) == 1 + 1 + 4


def test_el_90b_se_calcula_sobre_los_primeros_muestras_90b_bits(e1):
    est = Estimador90bFalso()
    d = replace(e1, tablas={**e1.tablas, "validacion": {**e1.tablas["validacion"], "muestras_90b": 12_345}})
    _ejecutor(est=est).ejecutar(d, 20261007)
    assert [len(x) for x in est.llamadas[:2]] == [12_345, 12_345]


def test_c_e1d_mide_cada_fuente_defectuosa_con_la_misma_vara(e1):
    f = {x.fuente: x for x in _ejecutor().ejecutar(e1, 20261007).fuentes}
    assert f["markov"].mcv > 0.9 and f["markov"].h_90b < 0.9  # el MCV la deja pasar, el 90B (de juguete) la rechaza
    assert f["ideal"].h_90b > 0.9 and all(m.cumple for m in f["ideal"].medidas)
    assert not f["sesgada"].medidas[0].cumple and f["periodica"].mcv > 0.9
    assert [m.metrica.value for m in f["ideal"].medidas] == ["M1_sesgo", "M3_nist_monobit", "M4_nist_runs", "M5_chi_cuadrado"]


def test_un_control_que_falla_se_informa_en_falso_no_como_excepcion(e1):
    med = _ejecutor(LabFalso(p1=0.5)).ejecutar(e1, 20261007)  # el ruido NO sesga: el detector no ve lo inyectado
    assert med.controles["D1"] is False and med.controles["N1"] is True


def test_p1_falla_si_el_90b_deja_pasar_a_la_markov(e1):
    class Ciego:
        def estimar(self, bits):
            return 0.97

    assert _ejecutor(est=Ciego()).ejecutar(e1, 20261007).controles["P1"] is False


def test_se_niega_a_medir_otra_eureka_o_una_declaracion_sin_el_nivel(e1):
    with pytest.raises(EntradaInvalida, match="E1"):
        _ejecutor().ejecutar(replace(e1, eureka="E2"), 1)
    with pytest.raises(EntradaInvalida, match="nivel"):
        _ejecutor().ejecutar(replace(e1, tablas={**e1.tablas, "ruido": {**e1.tablas["ruido"], "nivel": "inexistente"}}), 1)


def test_de_punta_a_punta_con_el_juez_las_tres_semillas_cumple_y_deja_las_cuatro_rutas(tmp_path, e1):
    """C.E1 entero con dobles: correr (3 semillas) → E1a…E1d.json + C.E1.json → juzgar. Las semillas cuentan las tres."""
    libro = LibroEnMemoria()
    s = CorrerYJuzgar(_ejecutor(), AlmacenJson(tmp_path / "corridas"), HistorialFalso(), libro, {"python": "3.13"})
    m = s.correr(e1)
    assert {p.name for p in (tmp_path / "corridas").glob("E1?.json")} == {"E1a.json", "E1b.json", "E1c.json", "E1d.json"}
    assert m.controles == {"N1": True, "D1": True, "P1": True}
    v = s.juzgar(e1)
    # el doble de Aer no reproduce el twirling real (M4/M5 de la mitigada pasan aquí): lo que se prueba es la cadena, no el desenlace
    assert v.desenlace in {"CUMPLE", "CUMPLE_PARCIAL", "NO_CUMPLE"} and len(libro.lineas) == 1
