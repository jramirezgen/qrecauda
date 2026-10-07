"""EjecutorE3: lo preinscrito en docs/preinscripciones/E3.md, con relojes y fuentes FALSOS (deterministas, sin Aer ni 90B).

El pipeline, el cifrado y la validación son los REALES (adaptadores `estadistica` y `aes_gcm`); sólo el origen de los bits, el reloj,
la sonda de la máquina y el 90B son dobles, para poder fijar a mano cuánto tarda cada repetición y qué CPU consume.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pytest

from qrecauda.adaptadores.aes_gcm import CifradorAesGcm, ReservaDeClave
from qrecauda.adaptadores.almacen_json import AlmacenJson
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.aplicacion.ejecutor_e3 import EjecutorE3
from qrecauda.aplicacion.juez import CorrerYJuzgar
from qrecauda.datos import Declaracion, RuidoDeLectura
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida
from qrecauda.dominio.metricas import Metrica, medir
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia

RAIZ = Path(__file__).resolve().parents[2]
MS = 1_000_000  # ns


class RelojFalso:
    """Cada lectura avanza `paso` ns; `extra` añade retraso a las lecturas siguientes (para fijar t_rep a mano)."""

    def __init__(self, paso: int = MS) -> None:
        self.t, self.paso = 0, paso

    def ahora_ns(self) -> int:
        self.t += self.paso
        return self.t


class SondaFalsa:
    def __init__(self, reloj: RelojFalso, *, factor_cpu: float = 1.0, carga: float = 0.1, factor_hijos: float = 1.0) -> None:
        self.reloj, self.factor, self.carga, self.fh = reloj, factor_cpu, carga, factor_hijos

    def carga_previa(self) -> float:
        return self.carga

    def cpu_proceso_ns(self) -> int:
        return int(self.reloj.t * self.factor)

    def cpu_con_hijos_ns(self) -> int:
        return int(self.reloj.t * self.fh)

    def maquina(self) -> dict[str, str]:
        return {"cpu": "doble", "nucleos": "20", "ram": "16 GB", "kernel": "6.x"}


class FuenteFalsa:
    def __init__(self, semilla: int, origen: Origen = Origen.SIMULADOR_AER, registro: list | None = None) -> None:
        self.semilla, self.origen, self.registro = semilla, origen, registro

    def generar(self, qubits: int, shots: int) -> Muestra:
        rng = np.random.default_rng(self.semilla)
        m = Muestra(
            Bits((rng.random(qubits * shots) < 0.5).astype(np.uint8)), self.origen, qubits, shots,
            procedencia=Procedencia("AerSimulator", "job-1" if self.origen is Origen.HARDWARE_IBM else "", "x"),
        )  # fmt: skip
        if self.registro is not None:
            self.registro.append(m)
        return m


class MitigadorFalso:
    def __init__(self, semilla: int) -> None:
        self.semilla = semilla

    def mitigar(self, muestra: Muestra) -> Muestra:
        rng = np.random.default_rng(self.semilla + 7)
        return muestra.mitigada_con(Bits((rng.random(len(muestra.bits)) < 0.5).astype(np.uint8)), conserva_bits_por_disparo=True)


@dataclass
class LabFalso:
    origen: Origen = Origen.SIMULADOR_AER

    def __post_init__(self) -> None:
        self.semillas_fuente: list[int] = []
        self.semillas_twirling: list[tuple[int, str, int]] = []
        self.crudas: list[Muestra] = []

    def fuente(self, ruido, semilla):
        self.semillas_fuente.append(semilla)
        self.ruido = ruido
        return FuenteFalsa(semilla, self.origen, self.crudas)

    def twirling(self, ruido, semilla, bloque):
        self.semillas_twirling.append((semilla, ruido.nombre, bloque))
        return MitigadorFalso(semilla)


class Estimador90bFalso:
    def __init__(self) -> None:
        self.llamadas: list[Bits] = []

    def estimar(self, bits: Bits) -> float:
        self.llamadas.append(bits)
        return 0.9


def _decl() -> Declaracion:
    """E3 con parámetros diminutos: 4 repeticiones + 1 de calentamiento, perfil B de 20 transacciones, 5 casos por control."""
    d = cargar_declaracion(Path("declaraciones/E3.toml"), RAIZ)
    t = {k: dict(v) for k, v in d.tablas.items()}
    t["configuracion"].update(repeticiones=4, calentamiento=1)
    t["perfil_b"].update(transacciones=20, peaje=10, metro=10)
    t["controles_uso"].update(u2_casos=5, u3_casos=5)
    t["validacion"]["muestras_90b"] = 20_000
    return replace(d, shots=8000, tablas=t)


@pytest.fixture(scope="module")
def decl() -> Declaracion:
    return _decl()


def _ejecutor(decl, *, lab=None, paso=MS, factor_cpu=1.0, carga=0.1, factor_hijos=1.0, cifrador=CifradorAesGcm, reserva=ReservaDeClave,
              validador=None, est90=None):  # fmt: skip
    reloj = RelojFalso(paso)
    lab = lab or LabFalso()
    est90 = est90 or Estimador90bFalso()
    ej = EjecutorE3(
        lab,
        validador or ValidadorEstadistico(),
        est90,
        cifrador,
        reserva,
        reloj,
        SondaFalsa(reloj, factor_cpu=factor_cpu, carga=carga, factor_hijos=factor_hijos),
    )
    return ej, lab, est90, reloj


@pytest.fixture(scope="module")
def sano(decl):
    ej, lab, est90, _ = _ejecutor(decl)
    return lab, est90, ej.ejecutar(decl, decl.semillas[0])


# ---------------------------------------------------------------- lo que se repite


def test_cada_semilla_hace_calentamiento_mas_repeticiones_con_semilla_por_100_mas_i(sano, decl):
    lab, _, m = sano
    s = decl.semillas[0]
    assert lab.semillas_fuente == [s * 100 + i for i in range(5)]  # 1 de calentamiento + 4 medidas (i = 0…)
    assert [t[0] for t in lab.semillas_twirling] == lab.semillas_fuente
    assert all(t[1:] == ("medio", 200) for t in lab.semillas_twirling)  # nivel y bloque de la declaración
    (e,) = m.e3
    assert (e.corrida, e.semilla, e.repeticiones, e.calentamiento) == ("C.E3", s, 4, 1)
    assert lab.ruido == RuidoDeLectura("medio", (0.02, 0.08))  # sale de PARAMETROS.toml


def test_el_90b_se_mide_sobre_la_cruda_antes_de_mitigar_y_dentro_de_cada_repeticion(sano, decl):
    lab, est90, _ = sano
    assert len(est90.llamadas) == 5
    for cruda, llamada in zip(lab.crudas, est90.llamadas, strict=True):
        assert llamada == cruda.bits[:20_000]  # muestras_90b de la declaración


def test_el_calentamiento_se_guarda_pero_no_entra_en_las_estadisticas(decl):
    """Retraso de 50 ms sólo en la repetición de calentamiento (la primera): M7 no lo ve."""

    class RelojLento(RelojFalso):
        def __init__(self) -> None:
            super().__init__()
            self.lecturas = 0

        def ahora_ns(self) -> int:
            self.lecturas += 1
            if self.lecturas == 5:  # una lectura dentro de la primera repetición (la de calentamiento)
                self.t += 500 * MS
            return super().ahora_ns()

    reloj = RelojLento()
    ej = EjecutorE3(LabFalso(), ValidadorEstadistico(), Estimador90bFalso(), CifradorAesGcm, ReservaDeClave, reloj, SondaFalsa(reloj))
    (e,) = ej.ejecutar(decl, decl.semillas[0]).e3
    r = e.reporte
    assert len(r["t_rep_ms"]) == 4 and len(r["calentamiento_t_rep_ms"]) == 1
    assert r["calentamiento_t_rep_ms"][0] > 500 and e.m7_max_ms < 100


def test_m6_es_suma_de_bits_sobre_suma_de_tiempos_y_m7_el_p95_higher(sano, decl):
    _, _, m = sano
    (e,) = m.e3
    r = e.reporte
    t_s = np.array(r["t_rep_ms"]) / 1e3
    bits = np.array(r["bits_clave"])
    assert e.m6_bits_por_s == pytest.approx(bits.sum() / t_s.sum())
    assert e.m7_p95_ms == pytest.approx(float(np.percentile(np.array(r["t_rep_ms"]), 95, method="higher")))
    assert e.m7_max_ms == max(r["t_rep_ms"]) and r["min_ms"] == min(r["t_rep_ms"])
    assert r["mediana_ms"] == pytest.approx(float(np.median(r["t_rep_ms"])))
    assert r["p5_tasa_bps"] == pytest.approx(float(np.percentile(bits / t_s, 5)))


def test_el_reporte_trae_el_tiempo_por_etapa_y_el_m6_solo_generacion(sano):
    _, _, m = sano
    r = m.e3[0].reporte
    assert set(r["etapas_ms"]) == {"fuente", "mitigacion", "extraccion", "validacion", "cifrado"}
    assert all(len(v) == 4 for v in r["etapas_ms"].values())
    suma = sum(np.array(v) for v in r["etapas_ms"].values())
    assert suma == pytest.approx(np.array(r["t_rep_ms"]))  # las etapas reparten t_rep sin perder ni inventar tiempo
    assert r["m6_solo_generacion_bps"] > 0


def test_cv_alto_se_reporta_como_inestable_sin_invalidar(decl):
    class RelojAspero(RelojFalso):
        def __init__(self) -> None:
            super().__init__()
            self.rng = np.random.default_rng(3)

        def ahora_ns(self) -> int:
            self.paso = int(self.rng.choice([1, 1, 1, 1, 1, 40])) * MS  # de vez en cuando una lectura de 40 ms
            return super().ahora_ns()

    reloj = RelojAspero()
    ej = EjecutorE3(LabFalso(), ValidadorEstadistico(), Estimador90bFalso(), CifradorAesGcm, ReservaDeClave, reloj, SondaFalsa(reloj))
    m = ej.ejecutar(decl, decl.semillas[0])
    r = m.e3[0].reporte
    assert r["cv_t_rep"] > 0.2 and r["inestable"] is True
    assert all(m.controles.values())  # se reporta, no invalida


# ---------------------------------------------------------------- T4 y máquina


def test_t4_un_hilo_pasa_con_cpu_igual_a_pared_y_en_el_borde(decl):
    assert _ejecutor(decl)[0].ejecutar(decl, decl.semillas[0]).controles["T4"] is True
    assert _ejecutor(decl, factor_cpu=1.10)[0].ejecutar(decl, decl.semillas[0]).controles["T4"] is True  # ≤ 1,10


def test_t4_falla_si_alguna_repeticion_pasa_de_1_10(decl):
    m = _ejecutor(decl, factor_cpu=1.5)[0].ejecutar(decl, decl.semillas[0])
    assert m.controles["T4"] is False
    assert max(m.e3[0].reporte["cpu_sobre_pared"]) > 1.10


def test_t4_usa_la_cpu_del_proceso_y_reporta_aparte_la_de_los_hijos(decl):
    m = _ejecutor(decl, factor_hijos=2.0)[0].ejecutar(decl, decl.semillas[0])
    r = m.e3[0].reporte
    assert m.controles["T4"] is True  # P.E3 define T4 con time.process_time
    assert max(r["cpu_con_hijos_sobre_pared"]) > 1.5 and max(r["cpu_sobre_pared"]) <= 1.10


def test_carga_previa_alta_invalida_la_semilla_antes_de_medir(decl):
    ej, lab, _, _ = _ejecutor(decl, carga=1.0)  # debe ser < 1,0
    with pytest.raises(CorridaInvalida, match="carga"):
        ej.ejecutar(decl, decl.semillas[0])
    assert lab.semillas_fuente == []


def test_la_maquina_se_registra(sano):
    assert sano[2].e3[0].maquina["cpu"] == "doble"


# ---------------------------------------------------------------- controles U1…U5 y perfil B


def test_u1_a_u5_pasan_con_el_cifrado_real(sano):
    c = sano[2].controles
    assert {k: c[k] for k in ("U1", "U2", "U3", "U4", "U5", "T4")} == dict.fromkeys(("U1", "U2", "U3", "U4", "U5", "T4"), True)


def test_perfil_b_se_mide_y_no_decide(sano, decl):
    b = sano[2].e3[0].reporte["perfil_b"]
    assert b["transacciones"] == 20 and b["peaje"] == 10 and b["metro"] == 10 and b["entropia_insuficiente"] is False
    assert b["ciclo_us"]["mediana"] > 0 and b["ciclo_us"]["p95"] >= b["ciclo_us"]["mediana"] and b["tx_por_s"] > 0
    assert b["decide"] is False


def test_u2_falla_si_el_cifrado_no_autentica(decl):
    class SinAutenticar(CifradorAesGcm):
        def descifrar(self, clave, nonce, cifrado, asociado):
            return super().descifrar(clave, nonce, cifrado, asociado) if False else b'{"estacion":"x","tarifa_centimos":1,"tarjeta":"t"}'

    m = _ejecutor(decl, cifrador=SinAutenticar)[0].ejecutar(decl, decl.semillas[0])
    assert m.controles["U2"] is False


def test_u3_falla_si_descifrar_con_otra_clave_funciona(decl):
    class IgnoraClave(CifradorAesGcm):
        def descifrar(self, clave, nonce, cifrado, asociado):
            return super().descifrar(self._ultima.get(nonce.a_bytes(), clave), nonce, cifrado, asociado)

        _ultima: dict = {}

        def cifrar(self, clave, nonce, texto, asociado):
            self._ultima[nonce.a_bytes()] = clave
            return super().cifrar(clave, nonce, texto, asociado)

    m = _ejecutor(decl, cifrador=IgnoraClave)[0].ejecutar(decl, decl.semillas[0])
    assert m.controles["U3"] is False and m.controles["U2"] is True


def test_u4_falla_si_la_reserva_repite_un_par_clave_nonce(decl):
    class Repetidora(ReservaDeClave):
        def siguiente(self):
            par = super().siguiente()
            if self.restantes > 5:  # devuelve el primero otra vez a mitad de reserva
                self._cursor = 0
            return par

    # el cifrador real se niega a repetir (NonceRepetido): el control mira la reserva, así que se relaja el cifrador
    class Permisivo(CifradorAesGcm):
        def cifrar(self, clave, nonce, texto, asociado):
            self._usados.clear()
            return super().cifrar(clave, nonce, texto, asociado)

    m = _ejecutor(decl, reserva=Repetidora, cifrador=Permisivo)[0].ejecutar(decl, decl.semillas[0])
    assert m.controles["U4"] is False


def test_u5_falla_si_el_origen_reclamara_ser_cuantico(decl):
    m = _ejecutor(decl, lab=LabFalso(origen=Origen.HARDWARE_IBM))[0].ejecutar(decl, decl.semillas[0])
    assert m.controles["U5"] is False


def test_una_reserva_corta_es_el_resultado_no_se_baja_n_tx(decl):
    t = {k: dict(v) for k, v in decl.tablas.items()}
    t["perfil_b"].update(transacciones=2000, peaje=1000, metro=1000)  # 704 000 bits: la clave del test no alcanza
    d = replace(decl, tablas=t)
    m = _ejecutor(d)[0].ejecutar(d, d.semillas[0])
    b = m.e3[0].reporte["perfil_b"]
    assert b["entropia_insuficiente"] is True and b["transacciones"] < 2000  # lo que hizo antes de agotarse
    assert m.controles["U1"] is False  # no se confirmó ida y vuelta de las 2000


def test_la_clave_que_no_pasa_m1_a_m5_aborta_la_corrida_no_se_cifra(decl):
    class Rechaza:
        def evaluar(self, bits):
            return (medir(Metrica.MONOBIT, 0.0),)

    with pytest.raises(CorridaInvalida, match="M1–M5"):
        _ejecutor(decl, validador=Rechaza())[0].ejecutar(decl, decl.semillas[0])


def test_la_validacion_en_la_mitigada_se_registra_sin_decidir(sano):
    v = sano[2].e3[0].reporte["validacion"]
    assert len(v) == 4 and set(v[0]) == {"cruda", "mitigada", "clave"}  # M1–M5 en los tres puntos, por repetición medida


# ---------------------------------------------------------------- guardias de la declaración


def test_la_regla_de_semilla_por_repeticion_es_la_declarada(decl):
    t = {k: dict(v) for k, v in decl.tablas.items()}
    t["configuracion"]["semilla_repeticion"] = "semilla + i"
    d = replace(decl, tablas=t)
    with pytest.raises(EntradaInvalida, match="semilla_repeticion"):
        _ejecutor(d)[0].ejecutar(d, d.semillas[0])


def test_solo_ejecuta_e3(decl):
    e2 = cargar_declaracion(Path("declaraciones/E2.toml"), RAIZ)
    with pytest.raises(EntradaInvalida):
        _ejecutor(decl)[0].ejecutar(e2, e2.semillas[0])


# ---------------------------------------------------------------- con el juez


class _Hist:
    def ultimo_commit(self, rutas):
        return "a" * 40

    def commit_actual(self):
        return "b" * 40

    def modificado(self, rutas):
        return False

    def precede(self, a, d):
        return True


class _Libro:
    def anadir(self, linea):
        pass


def _juzgar(decl, tmp_path, **kw):
    ej = _ejecutor(decl, **kw)[0]
    juez = CorrerYJuzgar(ej, AlmacenJson(tmp_path), _Hist(), _Libro(), {})
    juez.correr(decl)
    return juez.juzgar(decl)


def test_con_un_reloj_rapido_el_juez_da_cumple(decl, tmp_path):
    v = _juzgar(decl, tmp_path, paso=1_000)  # ~15 µs por repetición: M7 ≪ 500 ms y M6 ≫ 10 000 bit/s
    assert v.desenlace == "CUMPLE", v.resumen


def test_con_pasos_de_100_ms_el_juez_dice_no_cumple_m7(decl, tmp_path):
    v = _juzgar(decl, tmp_path, paso=100 * MS)
    assert v.desenlace == "NO_CUMPLE" and any(c.id.startswith("T2") and not c.cumple for c in v.criterios)


def test_un_control_roto_deja_la_corrida_invalida_para_el_juez(decl, tmp_path):
    with pytest.raises(CorridaInvalida, match="T4"):
        _juzgar(decl, tmp_path, factor_cpu=1.5)
