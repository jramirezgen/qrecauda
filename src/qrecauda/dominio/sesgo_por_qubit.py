"""Sesgo de lectura POR QUBIT (estadístico de P.E2): media sobre los qubits de |p̂_q − ½|, con p̂_q la frecuencia de unos del qubit.

Es la misma definición de S.02 y de `sesgo_mthree`. Los bits llegan en orden QUBIT-MAYOR (todos los disparos del qubit 0, luego los del 1…),
que es el que producen `FuenteAer` y `TwirlingLectura`. Puro: el remuestreo (que sortea) vive en la aplicación.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida


def frecuencias_de_unos(bits: Bits, qubits: int) -> NDArray[np.float64]:
    """p̂_q para cada qubit, de una secuencia qubit-mayor de `qubits` bloques iguales."""
    if qubits < 1 or len(bits) == 0 or len(bits) % qubits:
        raise EntradaInvalida(f"{len(bits)} bits no se reparten en {qubits} qubits iguales")
    return np.asarray(bits.datos.reshape(qubits, -1).mean(axis=1), dtype=np.float64)


def sesgo_medio(p_unos: NDArray[np.float64]) -> float:
    return float(np.abs(p_unos - 0.5).mean())


def sesgo_maximo(p_unos: NDArray[np.float64]) -> float:
    """El pooled puede cancelar qubits de signo opuesto; el máximo por qubit no (P.E2, nivel realista)."""
    return float(np.abs(p_unos - 0.5).max())
