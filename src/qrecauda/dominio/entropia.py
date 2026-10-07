"""Cotas de entropía. Estas son estimaciones conservadoras de dominio; la batería completa de NIST SP 800-90B
es un adaptador (adaptadores/nist) y se contrasta con esta en un contract test."""

from __future__ import annotations

import math

from .bits import Bits
from .errores import EntradaInvalida

Z_99 = 2.5758293035489004  # cuantil 0,995 de la normal: cota superior al 99 % (NIST SP 800-90B §6.3.1)


def sesgo(bits: Bits) -> float:
    """|p(1) − 1/2|: lo que la métrica M1 («sesgo de lectura») compara con su umbral."""
    return abs(bits.proporcion_de_unos() - 0.5)


def min_entropia_mcv(bits: Bits) -> float:
    """Most Common Value: H_min = −log2(p_u), con p_u la cota superior al 99 % de la frecuencia del símbolo más común."""
    n = len(bits)
    if n < 2:
        raise EntradaInvalida("la min-entropía necesita al menos 2 bits")
    p_hat = max(bits.proporcion_de_unos(), 1 - bits.proporcion_de_unos())
    p_u = min(1.0, p_hat + Z_99 * math.sqrt(p_hat * (1 - p_hat) / (n - 1)))
    return -math.log2(p_u)


class EstimadorMCV:
    """Implementa `EstimadorDeEntropia` con la cota MCV. ⚠️ Es ciega a la dependencia entre bits (S.04, hallazgo R.00-2):
    sirve para fuentes IID; contra una cadena de Markov la sobreestima. El pipeline acepta otro estimador por el puerto."""

    def estimar(self, bits: Bits) -> float:
        return min_entropia_mcv(bits)
