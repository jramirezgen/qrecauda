"""F6.02: transacción de peaje/Metro cifrada con la clave certificada de un pipeline."""

import pytest

from qrecauda.adaptadores.aes_gcm import BITS_CLAVE, BITS_NONCE, CifradorAesGcm, ReservaDeClave
from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.prng import FuentePrng
from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado, ejecutar
from qrecauda.aplicacion.transaccion import ROTULO_CUANTICO, ROTULO_VALIDACION, ServicioDeTransacciones, Transaccion
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import AutenticacionFallida, EntropiaInsuficiente, ErrorQRecauda, NonceRepetido
from qrecauda.dominio.metricas import Veredicto
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia
from qrecauda.transversal.observabilidad import RelojMonotonico

TX = Transaccion(estacion="Estacion Central", tarifa_centimos=250, tarjeta="T-0001")


@pytest.fixture(scope="module")
def resultado() -> Resultado:
    return ejecutar(FuentePrng(11), ValidadorEstadistico(), RelojMonotonico(), ParametrosPipeline(qubits=8, shots=20_000))


def _servicio(r: Resultado, cifrador=None) -> ServicioDeTransacciones:
    return ServicioDeTransacciones(r, cifrador or CifradorAesGcm(), ReservaDeClave)


def test_se_cifra_se_descifra_y_se_verifica(resultado):
    s = _servicio(resultado)
    t = s.cifrar(TX)
    assert TX.a_bytes() not in t.cifrado
    assert s.descifrar(t) == TX


def test_la_clave_sale_de_resultado_clave(resultado):
    s = _servicio(resultado)
    t = s.cifrar(TX)
    esperada, nonce = ReservaDeClave(resultado.clave).siguiente()
    assert t.nonce == nonce
    assert CifradorAesGcm().descifrar(esperada, nonce, t.cifrado, t.asociado) == TX.a_bytes()


def test_cada_transaccion_usa_un_nonce_distinto(resultado):
    s = _servicio(resultado)
    assert s.cifrar(TX).nonce != s.cifrar(TX).nonce


def test_nonce_repetido_se_rechaza_aunque_la_reserva_lo_entregue(resultado):
    class ReservaTramposa:
        def __init__(self, bits: Bits) -> None:
            self._par = ReservaDeClave(bits).siguiente()

        restantes = 99

        def siguiente(self) -> tuple[Bits, Bits]:
            return self._par

    s = ServicioDeTransacciones(resultado, CifradorAesGcm(), ReservaTramposa)
    s.cifrar(TX)
    with pytest.raises(NonceRepetido):
        s.cifrar(TX)


def test_agotamiento_de_entropia(resultado):
    corta = Resultado(**{**_campos(resultado), "clave": resultado.clave[: 2 * (BITS_CLAVE + BITS_NONCE) + 5]})
    s = _servicio(corta)
    s.cifrar(TX)
    s.cifrar(TX)
    assert s.restantes == 0
    with pytest.raises(EntropiaInsuficiente):
        s.cifrar(TX)


def test_fallo_de_autenticacion_por_cifrado_alterado_o_asociado_cambiado(resultado):
    s = _servicio(resultado)
    t = s.cifrar(TX)
    alterado = bytearray(t.cifrado)
    alterado[0] ^= 1
    with pytest.raises(AutenticacionFallida):
        s.descifrar(type(t)(**{**vars_de(t), "cifrado": bytes(alterado)}))
    with pytest.raises(AutenticacionFallida):
        s.descifrar(type(t)(**{**vars_de(t), "asociado": b"otra estacion"}))


def test_clave_no_certificada_no_se_usa(resultado):
    sin_veredicto = Resultado(**{**_campos(resultado), "veredicto": Veredicto(())})
    with pytest.raises(ErrorQRecauda):
        _servicio(sin_veredicto)


def test_el_rotulo_de_aer_es_validacion_del_pipeline(resultado):
    aer = Muestra(resultado.muestra.bits, Origen.SIMULADOR_AER, 8, 20_000)
    r = Resultado(**{**_campos(resultado), "muestra": aer})
    t = _servicio(r).cifrar(TX)
    assert t.rotulo == ROTULO_VALIDACION == "validación del pipeline"
    assert "cuántica" not in t.rotulo


def test_solo_hardware_con_job_reclama_origen_cuantico(resultado):
    hw = Muestra(resultado.muestra.bits, Origen.HARDWARE_IBM, 8, 20_000, procedencia=Procedencia(job_id="j1"))
    r = Resultado(**{**_campos(resultado), "muestra": hw})
    assert _servicio(r).cifrar(TX).rotulo == ROTULO_CUANTICO
    assert _servicio(resultado).cifrar(TX).rotulo == ROTULO_VALIDACION


def _campos(r: Resultado) -> dict[str, object]:
    return {c: getattr(r, c) for c in Resultado.__slots__}


def vars_de(t: object) -> dict[str, object]:
    return {c: getattr(t, c) for c in type(t).__slots__}
