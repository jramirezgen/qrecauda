"""Cifrador — AES-256-GCM con la clave QRNG y un nonce de 96 bits que no se repite (DAG F6.01)."""

from __future__ import annotations

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import AutenticacionFallida, EntradaInvalida, EntropiaInsuficiente, NonceRepetido

BITS_CLAVE = 256
BITS_NONCE = 96


class CifradorAesGcm:
    """Implementa el puerto `Cifrador`. Recuerda en memoria los (clave, nonce) usados para cifrar y rechaza repetirlos."""

    def __init__(self) -> None:
        self._usados: set[tuple[bytes, bytes]] = set()

    @staticmethod
    def _bytes(clave: Bits, nonce: Bits) -> tuple[bytes, bytes]:
        if len(clave) != BITS_CLAVE:
            raise EntradaInvalida(f"la clave AES-256 mide {BITS_CLAVE} bits, llegaron {len(clave)}")
        if len(nonce) != BITS_NONCE:
            raise EntradaInvalida(f"el nonce GCM mide {BITS_NONCE} bits, llegaron {len(nonce)}")
        return clave.a_bytes(), nonce.a_bytes()

    def cifrar(self, clave: Bits, nonce: Bits, texto: bytes, asociado: bytes) -> bytes:
        k, n = self._bytes(clave, nonce)
        if (k, n) in self._usados:
            raise NonceRepetido("este nonce ya cifró un mensaje con esta clave")
        self._usados.add((k, n))
        return bytes(AESGCM(k).encrypt(n, texto, asociado))

    def descifrar(self, clave: Bits, nonce: Bits, cifrado: bytes, asociado: bytes) -> bytes:
        k, n = self._bytes(clave, nonce)
        try:
            return bytes(AESGCM(k).decrypt(n, cifrado, asociado))
        except InvalidTag as exc:
            raise AutenticacionFallida("el cifrado o los datos asociados no autentican") from exc


class ReservaDeClave:
    """Reparte la clave certificada en trozos consecutivos (256 bits de clave + 96 de nonce); cada trozo sale una vez."""

    def __init__(self, certificada: Bits) -> None:
        self._bits = certificada
        self._cursor = 0

    @property
    def restantes(self) -> int:
        return (len(self._bits) - self._cursor) // (BITS_CLAVE + BITS_NONCE)

    def siguiente(self) -> tuple[Bits, Bits]:
        fin = self._cursor + BITS_CLAVE + BITS_NONCE
        if fin > len(self._bits):
            raise EntropiaInsuficiente(f"quedan {len(self._bits) - self._cursor} bits y un mensaje necesita {BITS_CLAVE + BITS_NONCE}")
        medio = self._cursor + BITS_CLAVE
        clave, nonce = self._bits[self._cursor : medio], self._bits[medio:fin]
        self._cursor = fin
        return clave, nonce
