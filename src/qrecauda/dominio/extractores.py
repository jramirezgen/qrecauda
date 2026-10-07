"""Extractores de aleatoriedad: von Neumann (quita sesgo), Peres (lo recicla) y Toeplitz (destila, LHL).

Todo es función pura de sus argumentos. La semilla de Toeplitz entra como `Bits`, nunca se sortea aquí.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.linalg import matmul_toeplitz

from .bits import Bits
from .errores import EntradaInvalida, EntropiaInsuficiente


def von_neumann(bits: Bits) -> Bits:
    """Pares no solapados: 01 → 0, 10 → 1, 00 y 11 se descartan. Exacto si los bits son IID de cualquier sesgo."""
    pares = bits.datos[: len(bits) // 2 * 2].reshape(-1, 2)
    distintos = pares[:, 0] != pares[:, 1]
    return Bits(pares[distintos, 0])


def peres(bits: Bits, profundidad: int = 8) -> Bits:
    """Von Neumann iterado (Peres 1992): además de los pares distintos, recicla la paridad y los pares iguales."""
    if profundidad < 0:
        raise EntradaInvalida("la profundidad de Peres no puede ser negativa")
    if len(bits) < 2 or profundidad == 0:
        return Bits(np.empty(0, dtype=np.uint8))
    pares = bits.datos[: len(bits) // 2 * 2].reshape(-1, 2)
    distintos = pares[:, 0] != pares[:, 1]
    salida = Bits(pares[distintos, 0])
    paridad = Bits(pares[:, 0] ^ pares[:, 1])
    iguales = Bits(pares[~distintos, 0])
    return salida.concatenar(peres(paridad, profundidad - 1)).concatenar(peres(iguales, profundidad - 1))


def longitud_segura(n: int, h_min: float, epsilon: float) -> int:
    """Leftover Hash Lemma: m = ⌊n·h_min − 2·log2(1/ε)⌋ bits a distancia ≤ ε de uniformes."""
    if not 0 < epsilon < 1:
        raise EntradaInvalida(f"epsilon debe estar en (0, 1): {epsilon}")
    if not 0 <= h_min <= 1:
        raise EntradaInvalida(f"h_min es bits de entropía por bit, en [0, 1]: {h_min}")
    m = math.floor(n * h_min - 2 * math.log2(1 / epsilon))
    if m < 1:
        raise EntropiaInsuficiente(f"n={n}, h_min={h_min:.4f}, ε={epsilon}: no sale ni un bit seguro")
    return m


def toeplitz(bits: Bits, semilla: Bits, m: int) -> Bits:
    """Hash universal T·x mod 2 con T (m×n) de Toeplitz definida por `semilla` (n+m−1 bits uniformes e independientes)."""
    n = len(bits)
    if m < 1 or m > n:
        raise EntradaInvalida(f"m={m} fuera de [1, n={n}]")
    if len(semilla) != n + m - 1:
        raise EntradaInvalida(f"la semilla necesita n+m−1={n + m - 1} bits, llegaron {len(semilla)}")
    s = semilla.datos.astype(np.float64)
    primera_columna = s[n - 1 : n - 1 + m]
    primera_fila = s[:n][::-1]
    producto = matmul_toeplitz((primera_columna, primera_fila), bits.datos.astype(np.float64))
    return Bits(np.rint(producto).astype(np.int64) % 2)
