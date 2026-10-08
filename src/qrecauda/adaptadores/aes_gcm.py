"""Cifrador — AES-256-GCM con la clave QRNG y un nonce de 96 bits que no se repite (DAG F6.01)."""

from __future__ import annotations

import hashlib
import threading

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import AutenticacionFallida, EntradaInvalida, EntropiaInsuficiente, NonceRepetido

BITS_CLAVE = 256
BITS_NONCE = 96

# Trozos ya repartidos por clave certificada (sha256 de la clave → bits consumidos), a nivel de PROCESO: dos reservas, dos servicios o
# dos cifradores sobre la misma clave comparten el cursor, así que ningún (clave, nonce) AES-GCM sale dos veces (B-1).
_CONSUMIDO: dict[bytes, int] = {}
_CANDADO_CONSUMO = threading.Lock()


def olvidar_consumo() -> None:
    """Sólo para tests: vacía el registro de trozos consumidos. En producción un trozo repartido no se devuelve."""
    with _CANDADO_CONSUMO:
        _CONSUMIDO.clear()


def _huella(clave: Bits) -> bytes:
    return hashlib.sha256(clave.a_bytes() if len(clave) % 8 == 0 else clave.datos.tobytes()).digest()


class CifradorAesGcm:
    """Implementa el puerto `Cifrador`. Recuerda en memoria los (clave, nonce) usados para cifrar y rechaza repetirlos."""

    def __init__(self) -> None:
        self._usados: set[bytes] = set()  # sha256(clave‖nonce): no guarda la clave en claro
        self._candado = threading.Lock()

    @staticmethod
    def _bytes(clave: Bits, nonce: Bits) -> tuple[bytes, bytes]:
        if len(clave) != BITS_CLAVE:
            raise EntradaInvalida(f"la clave AES-256 mide {BITS_CLAVE} bits, llegaron {len(clave)}")
        if len(nonce) != BITS_NONCE:
            raise EntradaInvalida(f"el nonce GCM mide {BITS_NONCE} bits, llegaron {len(nonce)}")
        return clave.a_bytes(), nonce.a_bytes()

    def cifrar(self, clave: Bits, nonce: Bits, texto: bytes, asociado: bytes) -> bytes:
        k, n = self._bytes(clave, nonce)
        marca = hashlib.sha256(k + n).digest()
        with self._candado:  # comprobar y anotar es una sola operación: dos hilos no ganan el mismo par
            if marca in self._usados:
                raise NonceRepetido("este nonce ya cifró un mensaje con esta clave")
            self._usados.add(marca)
        return bytes(AESGCM(k).encrypt(n, texto, asociado))

    def descifrar(self, clave: Bits, nonce: Bits, cifrado: bytes, asociado: bytes) -> bytes:
        k, n = self._bytes(clave, nonce)
        try:
            return bytes(AESGCM(k).decrypt(n, cifrado, asociado))
        except InvalidTag as exc:
            raise AutenticacionFallida("el cifrado o los datos asociados no autentican") from exc


class ReservaDeClave:
    """Reparte la clave certificada en trozos consecutivos (256 bits de clave + 96 de nonce); cada trozo sale una vez.

    El cursor no es de la instancia sino de la clave (registro de proceso por sha256): una reserva nueva sobre la misma clave
    continúa donde dejó la anterior en vez de volver al trozo 0.
    """

    def __init__(self, certificada: Bits) -> None:
        self._bits = certificada
        self._huella = _huella(certificada)

    @property
    def restantes(self) -> int:
        with _CANDADO_CONSUMO:
            return (len(self._bits) - _CONSUMIDO.get(self._huella, 0)) // (BITS_CLAVE + BITS_NONCE)

    def siguiente(self) -> tuple[Bits, Bits]:
        with _CANDADO_CONSUMO:
            cursor = _CONSUMIDO.get(self._huella, 0)
            fin = cursor + BITS_CLAVE + BITS_NONCE
            if fin > len(self._bits):
                raise EntropiaInsuficiente(f"quedan {len(self._bits) - cursor} bits y un mensaje necesita {BITS_CLAVE + BITS_NONCE}")
            medio = cursor + BITS_CLAVE
            clave, nonce = self._bits[cursor:medio], self._bits[medio:fin]
            _CONSUMIDO[self._huella] = fin
        return clave, nonce
