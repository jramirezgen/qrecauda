"""Validador — batería NIST SP 800-22 con nistrng (DAG F5.01). Se contrasta con adaptadores/estadistica en un TEST
(C2: los adaptadores no se importan entre sí), no aquí.

Pruebas usadas: sesgo (M1, de dominio), monobit (M3), runs (M4) y frecuencia por bloques (M5, §2.2).
⚠️ Comportamientos de nistrng 1.2.3 que se respetan sin forzarlos:
- `RunsTest._execute` NO comprueba el prerrequisito de frecuencia (§2.3.4); lo hace `is_eligible`. Aquí, si no es elegible,
  el p-valor es 0.0 (misma convención que adaptadores/estadistica). nistrng usa `>` y estadistica `>=` en el borde |π−½| = 2/√n.
- `FrequencyWithinBlockTest` fija M=20 y N=n//20, y si N ≥ 100 usa N=99 y M=n//99 (descarta la cola); exige n ≥ 100.
- La M5 de este adaptador es esa prueba por bloques, no el χ² de bytes de estadistica: son pruebas distintas.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from nistrng.sp800_22r1a.test_frequency_within_block import FrequencyWithinBlockTest
from nistrng.sp800_22r1a.test_monobit import MonobitTest
from nistrng.sp800_22r1a.test_runs import RunsTest

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import sesgo
from qrecauda.dominio.errores import EntradaInvalida, EntropiaInsuficiente
from qrecauda.dominio.metricas import Medida, Metrica, medir

ALFA = 0.01  # nivel de significación de SP 800-22
BITS_MIN_BLOQUES = 100  # mínimo de FrequencyWithinBlockTest


def p_monobit(bits: Bits) -> float:
    return float(MonobitTest()._execute(bits.datos).score)


def p_runs(bits: Bits) -> float:
    prueba = RunsTest()
    if not prueba.is_eligible(bits.datos):
        return 0.0
    return float(prueba._execute(bits.datos).score)


def p_frecuencia_por_bloques(bits: Bits) -> float:
    if len(bits) < BITS_MIN_BLOQUES:
        raise EntropiaInsuficiente(f"la frecuencia por bloques necesita ≥ {BITS_MIN_BLOQUES} bits, llegaron {len(bits)}")
    return float(FrequencyWithinBlockTest()._execute(bits.datos).score)


class ValidadorNist:
    """Implementa `Validador`: M1 sesgo (la de dominio, igual que `estadistica`) y, con nistrng, M3 monobit, M4 runs, M5 bloques."""

    def evaluar(self, bits: Bits) -> tuple[Medida, ...]:
        return (
            medir(Metrica.SESGO, sesgo(bits)),
            medir(Metrica.MONOBIT, p_monobit(bits)),
            medir(Metrica.RUNS, p_runs(bits)),
            medir(Metrica.CHI2, p_frecuencia_por_bloques(bits)),
        )


@dataclass(frozen=True, slots=True)
class Proporcion:
    """Criterio de SP 800-22 §4.2.1: la proporción de aprobados cae en 1−α ± 3·√(α(1−α)/N)."""

    aprobados: int
    total: int
    proporcion: float
    minimo: float
    maximo: float

    @property
    def cumple(self) -> bool:
        return self.minimo <= self.proporcion <= self.maximo


def proporcion_aprobados(p_valores: Sequence[float], alfa: float = ALFA) -> Proporcion:
    """Una secuencia aprueba si p ≥ α (§4.2.1). Un único p no es el criterio: lo es la proporción sobre N secuencias."""
    n = len(p_valores)
    if n == 0:
        raise EntradaInvalida("la proporción de aprobados necesita al menos una secuencia")
    if not 0.0 < alfa < 1.0:
        raise EntradaInvalida(f"alfa debe estar en (0, 1), llegó {alfa}")
    aprobados = int(np.count_nonzero(np.asarray(p_valores, dtype=float) >= alfa))
    medio = 1.0 - alfa
    holgura = 3.0 * math.sqrt(alfa * (1.0 - alfa) / n)
    return Proporcion(aprobados, n, aprobados / n, medio - holgura, medio + holgura)
