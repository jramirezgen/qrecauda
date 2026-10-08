"""Línea base clásica: PRNG con semilla. Es la columna «PRNG» de la demo del pitch (slide 4), no una fuente de claves."""

from __future__ import annotations

import numpy as np

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Muestra, Origen


class FuentePrng:
    """Implementa `FuenteDeBits`. Determinista: misma semilla ⇒ mismos bits (eso es justo lo que el pitch denuncia)."""

    def __init__(self, semilla: int, sesgo: float = 0.0) -> None:
        self._rng = np.random.default_rng(semilla)
        self._p1 = 0.5 + sesgo  # un sesgo >0 emula un bit lector asimétrico para probar al extractor

    def generar(self, qubits: int, shots: int) -> Muestra:
        bits = (self._rng.random(qubits * shots) < self._p1).astype(np.uint8)
        return Muestra(Bits(bits), Origen.PRNG_CLASICO, qubits, shots)


class FuenteMarkov:
    """Implementa `FuenteDeBits`: cadena de dos estados que CONSERVA el bit con probabilidad `permanencia` (como el spike S.04).

    Control positivo de E1 (C.E1d): h_min real = −log2(permanencia) si permanencia > ½ (0,8 → 0,322), y el MCV no la ve
    porque mira sólo la frecuencia (FUNDAMENTO, discrepancia 8). Sin sentido físico: un defecto con respuesta conocida."""

    def __init__(self, semilla: int, permanencia: float) -> None:
        if not 0.0 <= permanencia <= 1.0:
            raise EntradaInvalida(f"la permanencia debe estar en [0, 1], llegó {permanencia}")
        self._rng, self._cambio = np.random.default_rng(semilla), 1.0 - permanencia

    def generar(self, qubits: int, shots: int) -> Muestra:
        bits = (np.cumsum(self._rng.random(qubits * shots) < self._cambio) % 2).astype(np.uint8)
        return Muestra(Bits(bits), Origen.PRNG_CLASICO, qubits, shots)


class FuentePeriodica:
    """Implementa `FuenteDeBits`: un patrón («00001111») repetido; h_min real 0. Control positivo de E1 (C.E1d)."""

    def __init__(self, patron: str) -> None:
        if not patron or set(patron) - {"0", "1"}:
            raise EntradaInvalida(f"el patrón periódico sólo admite 0 y 1 y no puede ser vacío, llegó {patron!r}")
        self._base = np.frombuffer(patron.encode(), dtype=np.uint8) - ord("0")

    def generar(self, qubits: int, shots: int) -> Muestra:
        return Muestra(Bits(np.resize(self._base, qubits * shots).astype(np.uint8)), Origen.PRNG_CLASICO, qubits, shots)
