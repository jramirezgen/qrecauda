import numpy as np
import pytest

from qrecauda.adaptadores.aes_gcm import CifradorAesGcm, ReservaDeClave
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import AutenticacionFallida, EntradaInvalida, EntropiaInsuficiente, NonceRepetido
from qrecauda.entrada.codigos import codigo_de


def _aleatorios(n: int, semilla: int = 1) -> Bits:
    return Bits(np.random.default_rng(semilla).integers(0, 2, n, dtype=np.uint8))


def _par(semilla: int = 1) -> tuple[Bits, Bits]:
    return ReservaDeClave(_aleatorios(352, semilla)).siguiente()


def test_ida_y_vuelta():
    c, (k, n) = CifradorAesGcm(), _par()
    assert c.descifrar(k, n, c.cifrar(k, n, b"peaje 42", b"metro"), b"metro") == b"peaje 42"


def test_texto_alterado_se_rechaza_con_error_del_dominio():
    c, (k, n) = CifradorAesGcm(), _par()
    ct = bytearray(c.cifrar(k, n, b"peaje 42", b""))
    ct[0] ^= 1
    with pytest.raises(AutenticacionFallida) as e:
        c.descifrar(k, n, bytes(ct), b"")
    assert codigo_de(e.value) == 6


def test_datos_asociados_autentican():
    c, (k, n) = CifradorAesGcm(), _par()
    ct = c.cifrar(k, n, b"x", b"estacion A")
    with pytest.raises(AutenticacionFallida):
        c.descifrar(k, n, ct, b"estacion B")


def test_nonce_repetido_con_la_misma_clave_se_rechaza():
    c, (k, n) = CifradorAesGcm(), _par()
    c.cifrar(k, n, b"a", b"")
    with pytest.raises(NonceRepetido) as e:
        c.cifrar(k, n, b"b", b"")
    assert codigo_de(e.value) == 7


def test_mismo_nonce_con_otra_clave_se_permite():
    c = CifradorAesGcm()
    (k1, n), (k2, _) = _par(1), _par(2)
    c.cifrar(k1, n, b"a", b"")
    c.cifrar(k2, n, b"a", b"")


def test_longitudes_ilegales():
    c, (k, n) = CifradorAesGcm(), _par()
    with pytest.raises(EntradaInvalida):
        c.cifrar(k[:128], n, b"", b"")
    with pytest.raises(EntradaInvalida):
        c.cifrar(k, n[:64], b"", b"")


def test_vector_oficial_gcm_caso_16_de_256_bits():
    """McGrew-Viega, Test Case 16 (AES-256, IV 96 bits, con AAD); también en NIST CAVP."""
    k = bytes.fromhex("feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308")
    iv = bytes.fromhex("cafebabefacedbaddecaf888")
    p = bytes.fromhex(
        "d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a721c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39"
    )
    a = bytes.fromhex("feedfacedeadbeeffeedfacedeadbeefabaddad2")
    c = bytes.fromhex(
        "522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662"
    )
    t = bytes.fromhex("76fc6ece0f4e1768cddf8853bb2d551b")
    cif = CifradorAesGcm()
    assert cif.cifrar(Bits.desde_bytes(k), Bits.desde_bytes(iv), p, a) == c + t


def test_reserva_nunca_repite_un_trozo_y_se_agota():
    r = ReservaDeClave(_aleatorios(352 * 4 + 100, 7))
    trozos = [r.siguiente() for _ in range(4)]
    assert len({(k, n) for k, n in trozos}) == 4
    assert len({k for k, _ in trozos}) == 4
    assert r.restantes == 0
    with pytest.raises(EntropiaInsuficiente):
        r.siguiente()


def test_reserva_corta_trozos_consecutivos():
    b = _aleatorios(704, 3)
    r = ReservaDeClave(b)
    k, n = r.siguiente()
    k2, n2 = r.siguiente()
    assert k.concatenar(n).concatenar(k2).concatenar(n2) == b
