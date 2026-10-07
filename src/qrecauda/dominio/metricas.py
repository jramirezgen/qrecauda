"""Las siete métricas de aceptación (M1…M7) y su umbral. Fuente única: la tabla del mensaje fundacional §5.

Un umbral no se teclea en otro sitio: lo importan el validador, el informe y el test de aceptación.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Metrica(StrEnum):
    SESGO = "M1_sesgo"  # |p(1) − 1/2| < 0,01
    MIN_ENTROPIA = "M2_min_entropia"  # > 0,9 bits por bit
    MONOBIT = "M3_nist_monobit"  # p-valor > 0,01
    RUNS = "M4_nist_runs"  # p-valor > 0,01
    CHI2 = "M5_chi_cuadrado"  # p-valor > 0,01
    TASA = "M6_tasa_bps"  # > 10 000 bit/s
    LATENCIA = "M7_latencia_ms"  # < 500 ms


@dataclass(frozen=True, slots=True)
class Umbral:
    valor: float
    mayor_es_mejor: bool


UMBRALES: dict[Metrica, Umbral] = {
    Metrica.SESGO: Umbral(0.01, mayor_es_mejor=False),
    Metrica.MIN_ENTROPIA: Umbral(0.9, mayor_es_mejor=True),
    Metrica.MONOBIT: Umbral(0.01, mayor_es_mejor=True),
    Metrica.RUNS: Umbral(0.01, mayor_es_mejor=True),
    Metrica.CHI2: Umbral(0.01, mayor_es_mejor=True),
    Metrica.TASA: Umbral(10_000.0, mayor_es_mejor=True),
    Metrica.LATENCIA: Umbral(500.0, mayor_es_mejor=False),
}


@dataclass(frozen=True, slots=True)
class Medida:
    metrica: Metrica
    valor: float
    umbral: float
    cumple: bool


def medir(metrica: Metrica, valor: float) -> Medida:
    """Compara contra el umbral con desigualdad ESTRICTA (el mensaje fundacional dice «<» y «>», no «≤»)."""
    u = UMBRALES[metrica]
    cumple = valor > u.valor if u.mayor_es_mejor else valor < u.valor
    return Medida(metrica, valor, u.valor, cumple)


@dataclass(frozen=True, slots=True)
class Veredicto:
    medidas: tuple[Medida, ...]

    @property
    def aprobado(self) -> bool:
        """Conjuntivo: fallar una métrica es fallar el veredicto, y un veredicto sin medidas no aprueba nada."""
        return bool(self.medidas) and all(m.cumple for m in self.medidas)

    def fallos(self) -> tuple[Metrica, ...]:
        return tuple(m.metrica for m in self.medidas if not m.cumple)
