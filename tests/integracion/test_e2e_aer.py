"""F7.06: Aer ruidoso → mitigación → extracción → validación (NIST) → AES-GCM → descifrado, con el pipeline REAL y sin red.

Nada de dobles: la raíz de composición elige FuenteAer, TwirlingLectura, ValidadorNist y CifradorAesGcm. Lo que se prueba es
la cadena entera, no cada pieza. Rótulo honesto (D-002): el muestreo de Aer es un PRNG, así que es «validación del pipeline».
"""

import socket

import pytest

from qrecauda import composicion
from qrecauda.aplicacion.transaccion import ROTULO_VALIDACION, Transaccion
from qrecauda.dominio.metricas import Metrica
from qrecauda.dominio.muestra import Origen
from qrecauda.transversal.configuracion import Configuracion

pytestmark = pytest.mark.lento  # unos segundos; ci_local.sh corre todo pytest, así que esta SÍ corre en la CI local

TX = Transaccion(estacion="Peaje Chillón", tarifa_centimos=1250, tarjeta="T-pseudonimo-0042")


@pytest.fixture
def sin_red(monkeypatch):
    def prohibido(*a, **k):
        raise AssertionError("la cadena de F7.06 no abre sockets")

    monkeypatch.setattr(socket.socket, "connect", prohibido)
    monkeypatch.setattr(socket, "create_connection", prohibido)


@pytest.fixture(scope="module")
def cfg() -> Configuracion:
    return Configuracion(
        backend="aer_ruidoso", mitigacion="lectura", nivel_ruido="medio", validador="nist", qubits=8, shots=40_000, semilla=20261007
    )


@pytest.fixture(scope="module")
def resultado(cfg):
    return composicion.ejecutar(cfg)


def test_la_cadena_corre_con_las_piezas_reales(resultado):
    assert resultado.muestra.origen is Origen.SIMULADOR_AER and not resultado.muestra.reclama_origen_cuantico
    assert resultado.muestra.mitigada and resultado.muestra.procedencia.backend == "AerSimulator"
    assert [e for e, _ in resultado.etapas] == ["cruda", "mitigada", "clave"]
    assert len(resultado.clave) >= 2 * (256 + 96)  # alcanza para transacciones


def test_la_mitigacion_arregla_la_cruda_y_la_clave_pasa_la_validacion(resultado):
    """El ValidadorNist mide M3–M5 (no M1). Con ruido medio la cruda falla el monobit; la mitigada lo pasa; la clave pasa M3–M5 y M2.

    ⚠️ Determinista dada la semilla y el lock; M3 de la clave queda a ~0,001 del umbral (0,0111 > 0,01): si cambia el SDK, aquí primero.
    """
    monobit = {e: next(m for m in resultado.medidas_de(e) if m.metrica is Metrica.MONOBIT) for e in ("cruda", "mitigada", "clave")}
    assert not monobit["cruda"].cumple, "el ruido inyectado (medio) debe verse en la muestra cruda"
    assert monobit["mitigada"].cumple and monobit["clave"].cumple
    assert resultado.veredicto.calidad_de_clave_aprobada
    assert all(m.cumple for m in resultado.medidas_de("clave"))


def test_se_cifra_y_el_descifrado_es_igual_al_original(cfg, resultado, sin_red):
    servicio = composicion.servicio_de(cfg, resultado)
    t = servicio.cifrar(TX)
    assert TX.a_bytes() not in t.cifrado
    assert t.rotulo == ROTULO_VALIDACION
    descifrado = servicio.descifrar(t)
    assert descifrado == TX and descifrado.a_bytes() == TX.a_bytes()


def test_toda_la_cadena_corre_sin_red(cfg, sin_red):
    r = composicion.ejecutar(cfg)
    s = composicion.servicio_de(cfg, r)
    assert s.descifrar(s.cifrar(TX)) == TX
