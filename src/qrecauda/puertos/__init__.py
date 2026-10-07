"""Puertos: lo que el núcleo necesita del mundo, como `Protocol`. Cada adaptador implementa UNO (contrato C2)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.metricas import Medida
from qrecauda.dominio.muestra import Muestra


class FuenteDeBits(Protocol):
    """Hadamard + medición (o su sustituto). Devuelve bits crudos con su origen declarado."""

    def generar(self, qubits: int, shots: int) -> Muestra: ...


class Mitigador(Protocol):
    """Reduce el sesgo de lectura de una muestra. No inventa bits: devuelve otra `Muestra` marcada `mitigada`."""

    def mitigar(self, muestra: Muestra) -> Muestra: ...


class Validador(Protocol):
    """Mide M1–M5 sobre bits ya extraídos. Las métricas de tiempo (M6, M7) las pone la aplicación con el `Reloj`."""

    def evaluar(self, bits: Bits) -> tuple[Medida, ...]: ...


class EstimadorDeEntropia(Protocol):
    """Cota inferior de min-entropía por bit de una secuencia. El pipeline dimensiona la clave con ella, así que NO puede
    ser la misma función que luego la «certifica»: el adaptador 90B (S.04) es el contraste independiente."""

    def estimar(self, bits: Bits) -> float: ...


class EstimadorDeSesgo(Protocol):
    """⟨Z⟩ de una fuente con y sin mitigar. ZNE/PEC viven aquí, no en `Mitigador`: devuelven una estimación, no bits."""

    def estimar(self, muestra: Muestra) -> float: ...


class FuenteDeSemilla(Protocol):
    """Bits uniformes independientes para la semilla de Toeplitz (D-004), por un camino que no sea el del pool de datos."""

    def semilla(self, longitud: int) -> Bits: ...


class Cifrador(Protocol):
    """Cifrado autenticado con una clave QRNG (caso de uso del peaje/Metro)."""

    def cifrar(self, clave: Bits, nonce: Bits, texto: bytes, asociado: bytes) -> bytes: ...

    def descifrar(self, clave: Bits, nonce: Bits, cifrado: bytes, asociado: bytes) -> bytes: ...


class Almacen(Protocol):
    """Persistencia de artefactos canónicos. Append-only: guardar un nombre que ya existe es un error."""

    def guardar(self, nombre: str, artefacto: Mapping[str, object]) -> str: ...  # devuelve el sha256 del contenido

    def leer(self, nombre: str) -> dict[str, object]: ...


class Reloj(Protocol):
    def ahora_ns(self) -> int: ...


class Bitacora(Protocol):
    def registrar(self, evento: str, **campos: object) -> None: ...
