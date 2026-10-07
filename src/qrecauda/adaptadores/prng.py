"""Línea base clásica: PRNG con semilla. Es la columna «PRNG» de la demo del pitch (slide 4), no una fuente de claves."""

from __future__ import annotations

import numpy as np

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.muestra import Muestra, Origen


class FuentePrng:
    """Implementa `FuenteDeBits`. Determinista: misma semilla ⇒ mismos bits (eso es justo lo que el pitch denuncia)."""

    def __init__(self, semilla: int, sesgo: float = 0.0) -> None:
        self._rng = np.random.default_rng(semilla)
        self._p1 = 0.5 + sesgo  # un sesgo >0 emula un bit lector asimétrico para probar al extractor

    def generar(self, qubits: int, shots: int) -> Muestra:
        bits = (self._rng.random(qubits * shots) < self._p1).astype(np.uint8)
        return Muestra(Bits(bits), Origen.PRNG_CLASICO, qubits, shots)
