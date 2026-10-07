"""Validador estadístico propio (scipy): M1 sesgo, M3 monobit, M4 runs, M5 chi². Fórmulas de NIST SP 800-22 §2.1, §2.3.

El adaptador `nist` (nistrng) se contrasta con éste en un contract test: si discrepan, uno de los dos está mal.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.special import erfc
from scipy.stats import chisquare

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import sesgo
from qrecauda.dominio.errores import EntropiaInsuficiente
from qrecauda.dominio.metricas import Medida, Metrica, medir


def p_monobit(bits: Bits) -> float:
    n = len(bits)
    s = float(2 * int(bits.datos.sum()) - n)
    return float(erfc(abs(s) / math.sqrt(n) / math.sqrt(2)))


def p_runs(bits: Bits) -> float:
    n = len(bits)
    pi = bits.proporcion_de_unos()
    if abs(pi - 0.5) >= 2 / math.sqrt(n):  # prerrequisito de NIST: si falla la frecuencia, runs no se evalúa
        return 0.0
    v = 1 + int(np.count_nonzero(bits.datos[1:] != bits.datos[:-1]))
    return float(erfc(abs(v - 2 * n * pi * (1 - pi)) / (2 * math.sqrt(2 * n) * pi * (1 - pi))))


def p_chi2_bytes(bits: Bits) -> float:
    """Uniformidad del histograma de bytes (256 casillas). Necesita ≥ 5·256 bytes para que χ² sea fiable."""
    if len(bits) < 8 * 5 * 256:
        raise EntropiaInsuficiente(f"χ² de bytes necesita ≥ {8 * 5 * 256} bits, llegaron {len(bits)}")
    octetos = np.packbits(bits.datos[: len(bits) // 8 * 8])
    return float(chisquare(np.bincount(octetos, minlength=256)).pvalue)


class ValidadorEstadistico:
    """Implementa `Validador`."""

    def evaluar(self, bits: Bits) -> tuple[Medida, ...]:
        return (
            medir(Metrica.SESGO, sesgo(bits)),
            medir(Metrica.MONOBIT, p_monobit(bits)),
            medir(Metrica.RUNS, p_runs(bits)),
            medir(Metrica.CHI2, p_chi2_bytes(bits)),
        )
