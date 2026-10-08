"""Defectos inyectados en una fuente real (E5, el control negativo del pipeline completo).

Un defecto es una función determinista de (bits, semilla) que introduce DEPENDENCIA ENTRE BITS, lo que las pruebas de frecuencia y la
cota MCV no ven. Se aplica DESPUÉS de la lectura y del twirling (`MitigadorConDefecto`): el twirling real corre, sobre Aer, y su salida
llega al extractor ya contaminada, como lo haría una electrónica de lectura con memoria. Sin sentido físico fino: un defecto con
respuesta conocida, igual que `FuenteMarkov` y `FuentePeriodica` en C.E1d.

- `persistencia`: con probabilidad `copia` el bit repite al anterior (cadena de Markov; sesgo = el de los bits frescos).
- `patron`: con probabilidad `peso` el bit toma el valor de un patrón periódico (fuente semideterminista).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import numpy as np

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Muestra
from qrecauda.puertos import FuenteDeBits, Mitigador

Defecto = Callable[[Bits], Bits]


def persistencia(copia: float, semilla: int) -> Defecto:
    """b_i = b_{i-1} con probabilidad `copia`; si no, el bit fresco de entrada. Determinista dada la semilla."""
    _probabilidad(copia, "copia")

    def aplicar(bits: Bits) -> Bits:
        n = len(bits)
        if n == 0:
            return bits
        fresco = np.random.default_rng(semilla).random(n) >= copia
        fresco[0] = True
        ultimo = np.maximum.accumulate(np.where(fresco, np.arange(n), 0))
        return Bits(bits.datos[ultimo])

    return aplicar


def patron(peso: float, texto: str, semilla: int) -> Defecto:
    """b_i = patrón[i mod |patrón|] con probabilidad `peso`; si no, el bit de entrada. Determinista dada la semilla."""
    _probabilidad(peso, "peso")
    if not texto or set(texto) - {"0", "1"}:
        raise EntradaInvalida(f"el patrón sólo admite 0 y 1 y no puede ser vacío, llegó {texto!r}")
    base = np.frombuffer(texto.encode(), dtype=np.uint8) - ord("0")

    def aplicar(bits: Bits) -> Bits:
        n = len(bits)
        impone = np.random.default_rng(semilla).random(n) < peso
        return Bits(np.where(impone, np.resize(base, n), bits.datos).astype(np.uint8))

    return aplicar


def _probabilidad(x: float, nombre: str) -> None:
    if not 0.0 <= x <= 1.0:
        raise EntradaInvalida(f"{nombre} debe estar en [0, 1], llegó {x}")


class FuenteConDefecto:
    """Implementa `FuenteDeBits`: la fuente interior y el defecto sobre sus bits. Conserva origen, qubits, shots y procedencia."""

    def __init__(self, interior: FuenteDeBits, defecto: Defecto) -> None:
        self._interior, self._defecto = interior, defecto

    def generar(self, qubits: int, shots: int) -> Muestra:
        m = self._interior.generar(qubits, shots)
        return replace(m, bits=self._defecto(m.bits))


class MitigadorConDefecto:
    """Implementa `Mitigador`: el mitigador real y, DESPUÉS, el defecto. La muestra sigue marcada `mitigada`."""

    def __init__(self, interior: Mitigador, defecto: Defecto) -> None:
        self._interior, self._defecto = interior, defecto

    def mitigar(self, muestra: Muestra) -> Muestra:
        m = self._interior.mitigar(muestra)
        return replace(m, bits=self._defecto(m.bits))
