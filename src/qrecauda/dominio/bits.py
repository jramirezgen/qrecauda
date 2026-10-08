"""`Bits`: secuencia inmutable de ceros y unos. Un valor ilegal no se puede construir (defense-in-depth, capa 1)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .errores import EntradaInvalida


@dataclass(frozen=True, slots=True, eq=False)
class Bits:
    datos: NDArray[np.uint8]

    def __post_init__(self) -> None:
        arr = np.array(self.datos, dtype=np.uint8, copy=True)  # copia: congelar no toca el array del llamante
        if arr.ndim != 1:
            raise EntradaInvalida(f"Bits es unidimensional, llegó ndim={arr.ndim}")
        if arr.size and int(np.max(arr)) > 1:
            raise EntradaInvalida("Bits sólo admite 0 y 1")
        arr.flags.writeable = False
        object.__setattr__(self, "datos", arr)

    @classmethod
    def desde(cls, valores: Iterable[int]) -> Bits:
        return cls(np.fromiter(valores, dtype=np.uint8))

    @classmethod
    def desde_bytes(cls, crudo: bytes) -> Bits:
        return cls(np.unpackbits(np.frombuffer(crudo, dtype=np.uint8)))

    def __repr__(self) -> str:
        # Una clave en un repr acaba en una traza o un assert: sólo longitud y huella corta (no reversible).
        return f"Bits(len={len(self)}, sha256={hashlib.sha256(self.datos.tobytes()).hexdigest()[:8]})"

    def __len__(self) -> int:
        return int(self.datos.size)

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Bits) and np.array_equal(self.datos, otro.datos)

    def __hash__(self) -> int:
        return hash(self.datos.tobytes())

    def __getitem__(self, corte: slice) -> Bits:
        return Bits(self.datos[corte])

    def concatenar(self, otro: Bits) -> Bits:
        return Bits(np.concatenate((self.datos, otro.datos)))

    def a_bytes(self) -> bytes:
        if len(self) % 8:
            raise EntradaInvalida(f"{len(self)} bits no son un número entero de bytes")
        return np.packbits(self.datos).tobytes()

    def proporcion_de_unos(self) -> float:
        if not len(self):
            raise EntradaInvalida("la proporción de unos de una secuencia vacía no está definida")
        return float(self.datos.mean())
