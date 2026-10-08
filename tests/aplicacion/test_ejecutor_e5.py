"""EjecutorE5 con dobles de Aer y del 90B y parámetros DIMINUTOS: se prueba la lógica (qué se corre, qué se guarda, los controles),
no la estadística de 3,2 M de bits. Real: el pipeline, el validador, los defectos y el estimador mínimo. Declaración REAL de E5."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.adaptadores.defectos import MitigadorConDefecto, patron, persistencia
from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.aplicacion.ejecutor_e5 import DIMENSIONADOS, EjecutorE5
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia

RAIZ = Path(__file__).resolve().parents[2]
SHOTS, PREFIJO = 20_000, 60_000  # 8 × 20 000 = 160 000 bits crudos; el 90B (doble) mira los primeros 60 000


class RelojFalso:
    t = 0

    def ahora_ns(self) -> int:
        RelojFalso.t += 1_000_000
        return RelojFalso.t


class SondaFalsa:
    def __init__(self, carga: float = 0.1) -> None:
        self.carga = carga
        self.esperas: list[tuple[float, float]] = []

    def carga_previa(self) -> float:
        return self.carga

    def esperar_reposo(self, maximo: float, tope_s: float) -> None:
        self.esperas.append((maximo, tope_s))


class Aer50:
    """Un 'Aer' ideal: P(1) = ½ exacta, determinista dada la semilla."""

    def __init__(self, semilla: int) -> None:
        self.semilla = semilla

    def generar(self, qubits: int, shots: int) -> Muestra:
        bits = np.random.default_rng(self.semilla).integers(0, 2, qubits * shots, dtype=np.uint8)
        return Muestra(Bits(bits), Origen.SIMULADOR_AER, qubits, shots, procedencia=Procedencia("AerSimulator", "", "x"))


class TwirlingFalso:
    def __init__(self, semilla: int) -> None:
        self.semilla = semilla

    def mitigar(self, muestra: Muestra) -> Muestra:
        nueva = Aer50(self.semilla + 1).generar(muestra.qubits, muestra.shots)
        return muestra.mitigada_con(nueva.bits, conserva_bits_por_disparo=True)


def fabrica(decl, nombre, semilla):
    """Lo que hace la composición real, con el Aer de juguete: el defecto declarado va DESPUÉS del twirling."""
    mit = TwirlingFalso(semilla)
    if nombre == "buena":
        return Aer50(semilla), mit
    d = decl.tablas["defectos"][nombre]
    s = semilla + int(decl.tablas["defectos"]["desplazamiento_semilla"])
    f = persistencia(d["peso"], s) if d["tipo"] == "persistencia" else patron(d["peso"], d["patron"], s)
    return Aer50(semilla), MitigadorConDefecto(mit, f)


class Estimador90bFalso:
    """90B de juguete: 0,97 si la frecuencia de unos está a 0,05 de ½ y el bit cambia ~½ de las veces; si no, 0,2."""

    def __init__(self) -> None:
        self.llamadas: list[int] = []

    def estimar(self, bits: Bits) -> float:
        self.llamadas.append(len(bits))
        d = bits.datos
        cambia = float((d[1:] != d[:-1]).mean())
        return 0.97 if abs(bits.proporcion_de_unos() - 0.5) < 0.05 and abs(cambia - 0.5) < 0.05 else 0.2


@pytest.fixture
def e5():
    d = cargar_declaracion(Path("declaraciones/E5.toml"), RAIZ)
    cadena = {**d.tablas["cadena"], "shots": SHOTS}
    dim = {**d.tablas["dimensionados"], "prefijo_90b": PREFIJO}
    return replace(d, shots=SHOTS, tablas={**d.tablas, "cadena": cadena, "dimensionados": dim})


def _ejecutor(sonda=None, est=None, bit=None) -> EjecutorE5:
    return EjecutorE5(fabrica, ValidadorEstadistico(), est or Estimador90bFalso(), RelojFalso(), sonda or SondaFalsa(), bit)


@pytest.fixture(scope="module")
def medicion():
    d = cargar_declaracion(Path("declaraciones/E5.toml"), RAIZ)
    cadena = {**d.tablas["cadena"], "shots": SHOTS}
    dim = {**d.tablas["dimensionados"], "prefijo_90b": PREFIJO}
    decl = replace(d, shots=SHOTS, tablas={**d.tablas, "cadena": cadena, "dimensionados": dim})
    return decl, _ejecutor().ejecutar(decl, 20261007)


def test_una_semilla_mide_cada_fuente_con_los_tres_dimensionados(medicion):
    decl, med = medicion
    assert [e.fuente for e in med.e5] == ["buena", "markov", "markov_fuerte", "periodica"]
    for e in med.e5:
        assert e.semilla == 20261007 and e.corrida == "C.E5" and e.bits_crudos == 8 * SHOTS
        assert tuple(r["dimensionado"] for r in e.resultados) == DIMENSIONADOS
        assert len({r["sha256_muestra"] for r in e.resultados}) == 1  # P5: misma muestra en los tres
    assert set(med.controles) == {"D5", "P5"} and all(med.controles.values())


def test_los_defectos_acortan_la_clave_del_dimensionado_conservador_y_la_buena_apenas(medicion):
    _, med = medicion
    claves = {e.fuente: {r["dimensionado"]: r["bits_clave"] for r in e.resultados} for e in med.e5}
    for f in ("markov", "markov_fuerte", "periodica"):
        assert claves[f]["conservador"] < 0.7 * claves[f]["mcv"]  # el 90B (doble) ve el defecto en la fuente y la contabilidad lo propaga
        assert claves[f]["conservador"] <= 0.2 * 8 * SHOTS  # nunca más entropía que la de la fuente cruda
    assert claves["buena"]["conservador"] >= 0.9 * claves["buena"]["mcv"] > 0


def test_mcv_es_el_pipeline_de_0_1_0_sin_cotas_nuevas(medicion):
    _, med = medicion
    for e in med.e5:
        r = next(r for r in e.resultados if r["dimensionado"] == "mcv")
        assert r["h_90b_pool"] is None and r["h_90b_fuente"] is None and r["estado"] == "entregada"
        assert r["h_mcv_pool"] == r["h_efectiva"]


def test_el_90b_de_control_mira_el_prefijo_de_la_mitigada(medicion):
    _, med = medicion
    assert med.e5[0].h_90b_fuente > 0.9 and all(e.h_90b_fuente < 0.5 for e in med.e5[1:])


def test_un_pool_menor_que_el_prefijo_es_un_rechazo_registrado_no_una_excepcion(e5):
    class Exigente(Estimador90bFalso):
        def estimar(self, bits):
            from qrecauda.dominio.errores import EntropiaInsuficiente

            if len(bits) < PREFIJO:
                raise EntropiaInsuficiente("el 90B exige más bits")
            return super().estimar(bits)

    med = _ejecutor(est=Exigente()).ejecutar(e5, 20261007)  # el pool de la markov_fuerte (57 311 bits) no llega a 60 000
    fuerte = next(e for e in med.e5 if e.fuente == "markov_fuerte")
    r = next(x for x in fuerte.resultados if x["dimensionado"] == "min_mcv_90b")
    assert r["estado"] == "rechazada" and r["bits_clave"] == 0 and "exige" in r["motivo"]


def test_un_90b_ciego_invalida_d5(e5):
    class Ciego:
        def estimar(self, bits):
            return 0.97

    assert _ejecutor(est=Ciego()).ejecutar(e5, 20261007).controles["D5"] is False


def test_espera_el_reposo_y_se_niega_a_medir_con_la_maquina_ocupada(e5):
    sonda = SondaFalsa(carga=3.0)
    with pytest.raises(CorridaInvalida, match="carga previa"):
        _ejecutor(sonda).ejecutar(e5, 20261007)
    assert sonda.esperas == [(2.0, 900.0)]


def test_solo_mide_e5(e5):
    with pytest.raises(EntradaInvalida):
        _ejecutor().ejecutar(replace(e5, eureka="E1"), 20261007)


def test_el_resultado_sobrevive_al_almacen(medicion, tmp_path):
    _, med = medicion
    alm = AlmacenJson(tmp_path)
    for i, e in enumerate(med.e5):
        alm.guardar(f"x{i}", e.a_mapa())
    from qrecauda.datos import ExperimentoE5

    assert [ExperimentoE5.desde_mapa(alm.leer(f"x{i}")) for i in range(4)] == list(med.e5)
