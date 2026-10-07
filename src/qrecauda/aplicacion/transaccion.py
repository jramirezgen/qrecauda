"""Caso de uso F6.02: transacción de peaje/Metro cifrada con la clave certificada de un pipeline.

Sólo conoce puertos y dominio (C1/C3): el cifrador y la fabricación de la reserva de clave llegan inyectados.
La clave sale SIEMPRE de `Resultado.clave`, y el rótulo sale del `Origen` declarado de la muestra: sólo hardware IBM
con `job_id` puede decir «entropía cuántica»; todo lo demás (Aer incluido) es «validación del pipeline» (D-002).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from qrecauda.aplicacion.pipeline import Resultado
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.puertos import Cifrador, ReservaDeClaves

ROTULO_VALIDACION = "validación del pipeline"
ROTULO_CUANTICO = "entropía cuántica (hardware IBM)"


@dataclass(frozen=True, slots=True)
class Transaccion:
    estacion: str
    tarifa_centimos: int
    tarjeta: str

    def a_bytes(self) -> bytes:
        return json.dumps(
            {"estacion": self.estacion, "tarifa_centimos": self.tarifa_centimos, "tarjeta": self.tarjeta},
            sort_keys=True,
            ensure_ascii=False,
        ).encode()

    @classmethod
    def desde_bytes(cls, crudo: bytes) -> Transaccion:
        d = json.loads(crudo)
        return cls(d["estacion"], d["tarifa_centimos"], d["tarjeta"])


@dataclass(frozen=True, slots=True)
class TransaccionCifrada:
    cifrado: bytes
    nonce: Bits
    asociado: bytes  # la estación viaja autenticada, en claro
    rotulo: str


class ServicioDeTransacciones:
    def __init__(self, resultado: Resultado, cifrador: Cifrador, crear_reserva: Callable[[Bits], ReservaDeClaves]) -> None:
        # Sólo la calidad de la clave (M1–M5). M6/M7 internas se miden hasta Toeplitz y las juzga C.E3 de extremo a extremo (P.E3).
        if not resultado.veredicto.calidad_de_clave_aprobada:
            raise EntradaInvalida("la clave no está certificada: M1–M5 no aprueban, no se cifra con ella")
        self._cifrador = cifrador
        self._reserva = crear_reserva(resultado.clave)
        self._rotulo = ROTULO_CUANTICO if resultado.muestra.reclama_origen_cuantico else ROTULO_VALIDACION
        self._claves: dict[bytes, Bits] = {}  # nonce → clave, para descifrar lo que este servicio cifró

    @property
    def restantes(self) -> int:
        return self._reserva.restantes

    def cifrar(self, tx: Transaccion) -> TransaccionCifrada:
        clave, nonce = self._reserva.siguiente()
        asociado = tx.estacion.encode()
        cifrado = self._cifrador.cifrar(clave, nonce, tx.a_bytes(), asociado)
        self._claves[nonce.a_bytes()] = clave
        return TransaccionCifrada(cifrado, nonce, asociado, self._rotulo)

    def descifrar(self, t: TransaccionCifrada) -> Transaccion:
        clave = self._claves.get(t.nonce.a_bytes())
        if clave is None:
            raise EntradaInvalida("ese nonce no salió de esta reserva de clave")
        return Transaccion.desde_bytes(self._cifrador.descifrar(clave, t.nonce, t.cifrado, t.asociado))
