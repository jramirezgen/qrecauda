"""R.02: las claves de Aer sembrada son reproducibles. (1) semillas consecutivas no comparten clave; (2) C.E3b conserva su regla declarada;
(3) la guarda impide usar una clave simulada fuera del contexto de validación (D-011)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from e3b_dobles import ProductorFalso, RelojFalso, clave_entregada, declaracion_diminuta  # noqa: E402

from qrecauda import composicion  # noqa: E402
from qrecauda.adaptadores.aes_gcm import CifradorAesGcm, ReservaDeClave  # noqa: E402
from qrecauda.adaptadores.estadistica import ValidadorEstadistico  # noqa: E402
from qrecauda.adaptadores.prng import FuentePrng  # noqa: E402
from qrecauda.aplicacion.pipeline import ParametrosPipeline, ejecutar  # noqa: E402
from qrecauda.aplicacion.reserva_asincrona import (  # noqa: E402
    PASO_SEMILLA,
    PASO_SEMILLA_HEREDADO,
    GeneradorDeClaveAprobada,
    ReservaAsincrona,
    ServicioDeTransaccionesAsincrono,
)
from qrecauda.aplicacion.transaccion import CONTEXTO_PRODUCCION, ROTULO_CUANTICO, ServicioDeTransacciones, Transaccion  # noqa: E402
from qrecauda.datos import RuidoDeLectura  # noqa: E402
from qrecauda.dominio.bits import Bits  # noqa: E402
from qrecauda.dominio.errores import EntradaInvalida  # noqa: E402
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia  # noqa: E402
from qrecauda.transversal.observabilidad import RelojMonotonico  # noqa: E402


class _Laboratorio:
    """Fuente PRNG por semilla: apunta qué semillas pidió el generador. Sin mitigador (el pipeline lo admite)."""

    def __init__(self) -> None:
        self.semillas: list[int] = []

    def fuente(self, ruido: object, semilla: int) -> FuentePrng:
        self.semillas.append(semilla)
        return FuentePrng(semilla)

    def twirling(self, ruido: object, semilla: int, bloque: int) -> None:
        return None


class _Noventa:
    def estimar(self, bits: Bits) -> float:
        return 0.9


def _generador(semilla: int, **kw: object) -> tuple[GeneradorDeClaveAprobada, _Laboratorio]:
    lab = _Laboratorio()
    g = GeneradorDeClaveAprobada(
        lab, ValidadorEstadistico(), _Noventa(), RelojMonotonico(), RuidoDeLectura("medio", (0.01, 0.01)),  # type: ignore[arg-type]
        ParametrosPipeline(8, 20_000), 1000, 100, semilla, **kw,
    )  # fmt: skip
    return g, lab


# ------------------------------------------------------------------ el paso de la semilla


def test_con_el_paso_nuevo_semillas_consecutivas_no_comparten_ninguna_clave():
    a, _ = _generador(5)
    b, _ = _generador(6)
    assert PASO_SEMILLA >= 10**6
    # con el paso heredado, (semilla 5, i=100) == (semilla 6, i=0): la colisión del hallazgo
    heredado_a, _ = _generador(5, paso_semilla=PASO_SEMILLA_HEREDADO)
    heredado_b, _ = _generador(6, paso_semilla=PASO_SEMILLA_HEREDADO)
    assert heredado_a.generar(100).meta.semilla == heredado_b.generar(0).meta.semilla
    assert a.generar(100).meta.semilla != b.generar(0).meta.semilla


def test_el_paso_nuevo_es_el_de_omision_y_rechaza_un_indice_que_no_cabe():
    g, lab = _generador(7)
    k = g.generar(3)
    assert k.meta.semilla == 7 * PASO_SEMILLA + 3 and lab.semillas[0] == 7 * PASO_SEMILLA + 3
    with pytest.raises(EntradaInvalida, match="no cabe"):
        g.generar(PASO_SEMILLA)


def test_el_paso_heredado_reproduce_las_claves_de_c_e3b():
    """C.E3b se midió con «semilla * 100 + i»: con ese paso la semilla de cada clave es EXACTAMENTE la de antes."""
    g, lab = _generador(20261007, paso_semilla=PASO_SEMILLA_HEREDADO)
    assert g.generar(2).meta.semilla == 20261007 * 100 + 2 == lab.semillas[0]


def test_c_e3b_conserva_su_regla_declarada_al_componer_el_productor():
    decl = declaracion_diminuta()
    esp = composicion._especificacion_de(decl, 20261007, (0, 1))
    assert esp.paso_semilla == PASO_SEMILLA_HEREDADO  # la declaración dice «semilla * 100 + i»: no se toca lo medido


def test_una_regla_de_semilla_desconocida_aborta():
    decl = declaracion_diminuta(ajustes={"configuracion": {"semilla_clave": "semilla + i"}})
    with pytest.raises(EntradaInvalida, match="semilla_clave"):
        composicion._especificacion_de(decl, 1, (0,))


def test_los_estimadores_opcionales_llegan_al_pipeline():
    vistos: list[int] = []

    class _Salida:
        def estimar(self, bits: Bits) -> float:
            vistos.append(len(bits))
            return 0.99

    g, _ = _generador(9, estimadores={"estimador_de_salida": _Salida()})
    g.generar(0)
    assert vistos  # el estimador de salida opcional se usó; por omisión (sin estimadores) el pipeline es el de 0.1.0


# ------------------------------------------------------------------ la guarda de contexto


def _resultado(origen: Origen):
    r = ejecutar(FuentePrng(11), ValidadorEstadistico(), RelojMonotonico(), ParametrosPipeline(qubits=8, shots=20_000))
    if origen is Origen.SIMULADOR_AER:
        return r  # la fuente PRNG ya es no cuántica: sirve de «Aer sembrada» para la guarda
    muestra = Muestra(r.muestra.bits, Origen.HARDWARE_IBM, 8, 20_000, False, Procedencia("ibm_x", "job-1", "9"))
    from dataclasses import replace

    return replace(r, muestra=muestra)


def test_una_clave_reproducible_se_rechaza_fuera_del_contexto_de_validacion():
    r = _resultado(Origen.SIMULADOR_AER)
    with pytest.raises(EntradaInvalida, match="D-011"):
        ServicioDeTransacciones(r, CifradorAesGcm(), ReservaDeClave, contexto=CONTEXTO_PRODUCCION)


def test_el_contexto_de_validacion_por_omision_sigue_funcionando_demo_y_e3b():
    r = _resultado(Origen.SIMULADOR_AER)
    s = ServicioDeTransacciones(r, CifradorAesGcm(), ReservaDeClave)  # contexto por omisión: validación
    assert s.descifrar(s.cifrar(Transaccion("Peaje Villa", 1, "T-1"))).estacion == "Peaje Villa"


def test_una_clave_de_hardware_pasa_la_guarda_de_contexto():
    ServicioDeTransacciones(_resultado(Origen.HARDWARE_IBM), CifradorAesGcm(), ReservaDeClave, contexto=CONTEXTO_PRODUCCION)


def test_un_contexto_desconocido_aborta():
    with pytest.raises(EntradaInvalida, match="contexto"):
        ServicioDeTransacciones(_resultado(Origen.SIMULADOR_AER), CifradorAesGcm(), ReservaDeClave, contexto="staging")


def test_la_reserva_asincrona_con_claves_simuladas_se_rechaza_en_produccion_y_funciona_en_validacion():
    def servicio(contexto: str | None) -> ServicioDeTransaccionesAsincrono:
        r = ReservaAsincrona(ProductorFalso([clave_entregada(i) for i in range(2)]), ReservaDeClave, RelojFalso(), 1.0)
        r.cebar()
        kw = {} if contexto is None else {"contexto": contexto}
        return ServicioDeTransaccionesAsincrono(r, CifradorAesGcm(), **kw)

    with pytest.raises(EntradaInvalida, match="D-011"):
        servicio(CONTEXTO_PRODUCCION).ciclo(Transaccion("Peaje Villa", 1, "T-1"))
    s = servicio(None)
    assert s.ciclo(Transaccion("Peaje Villa", 1, "T-1")).rotulo == "validación del pipeline"


def test_una_mezcla_de_claves_simuladas_y_reales_no_reclama_origen_cuantico():
    claves = [clave_entregada(0, rotulo=ROTULO_CUANTICO, origen="hardware_ibm"), clave_entregada(1)]
    r = ReservaAsincrona(ProductorFalso(claves), ReservaDeClave, RelojFalso(), 1.0)
    r.cebar()
    s = ServicioDeTransaccionesAsincrono(r, CifradorAesGcm())
    for k in range(11):  # 10 trozos de la primera clave + 1 de la segunda
        t = s.ciclo(Transaccion("Peaje Villa", k, f"T-{k}"))
    assert t.rotulo == "validación del pipeline"
