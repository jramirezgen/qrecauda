"""Los criterios y controles de E4 (docs/preinscripciones/E4.md), como funciones puras sobre lo ya medido.

UNA sola definición: el ejecutor calcula los controles con ellas y el juez los recalcula sobre los artefactos releídos.
Las tolerancias salen de la declaración (`[criterios.h1]`), no se teclean aquí.
"""

from __future__ import annotations

from collections.abc import Sequence

from qrecauda.aplicacion.criterios_e1 import CLAVE, ESTRUCTURA, n1_cumple, pasan
from qrecauda.datos import InformeCorrida
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Muestra, Origen

PRNG, AER_CRUDA, AER_TWIRL, HW_CRUDA, HW_TWIRL = "C.E4a", "C.E4b", "C.E4c", "C.E4d", "C.E4e"
CORRIDAS = (PRNG, AER_CRUDA, AER_TWIRL, HW_CRUDA, HW_TWIRL)
__all__ = [
    "AER_CRUDA", "AER_TWIRL", "CLAVE", "CORRIDAS", "ESTRUCTURA", "HW_CRUDA", "HW_TWIRL", "PRNG",
    "h1_detalle", "h2_cumple", "n1_cumple", "pasan", "s1_cumple", "sesgo_medio_por_qubit", "sesgos_por_qubit", "v1_cumple",
]  # fmt: skip


def sesgos_por_qubit(m: Muestra) -> list[float]:
    """p̂_q(1) − ½ por qubit (con signo), en el orden de la muestra (qubit-mayor). En hardware el qubit q es el q-ésimo MEDIDO, no el
    físico q: por eso H1 compara sólo el agregado (E4.md, «Límite de la comparación»)."""
    if len(m.bits) != m.qubits * m.shots:
        raise EntradaInvalida(f"la muestra trae {len(m.bits)} bits y {m.qubits}×{m.shots} esperados")
    d = m.bits.datos.reshape(m.qubits, m.shots)
    return [float(x) - 0.5 for x in d.mean(axis=1)]


def sesgo_medio_por_qubit(sesgos: Sequence[float]) -> float:
    """Media de |p̂_q(1) − ½| sobre los qubits: el agregado que H1 compara."""
    if not sesgos:
        raise EntradaInvalida("sin sesgos por qubit no hay agregado")
    return sum(abs(s) for s in sesgos) / len(sesgos)


def _por_qubit(i: InformeCorrida) -> list[float]:
    v = i.reporte.get("sesgos_por_qubit")
    if not isinstance(v, list) or not v or not all(isinstance(x, int | float) and not isinstance(x, bool) for x in v):
        raise EntradaInvalida(f"{i.corrida}/{i.semilla} no trae reporte.sesgos_por_qubit: no se compara lo que no se midió")
    return [float(x) for x in v]


def h1_detalle(hw_cruda: InformeCorrida, gemelo_cruda: InformeCorrida, tolerancia: float) -> tuple[bool, float, float]:
    """H1 (por trabajo): el mayor |sesgo por qubit del hardware crudo − el del gemelo en Aer| ≤ tolerancia. Los dos corren los mismos
    circuitos en los mismos qubits físicos, así que la comparación es qubit a qubit. → (cumple, máx |Δ|, media |Δ|)."""
    a, b = _por_qubit(hw_cruda), _por_qubit(gemelo_cruda)
    if len(a) != len(b):
        raise EntradaInvalida(f"{len(a)} qubits en el hardware y {len(b)} en el gemelo: no son comparables")
    difs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return max(difs) <= tolerancia, max(difs), sum(difs) / len(difs)


def h2_cumple(hw_twirl: InformeCorrida) -> bool:
    """H2 (por trabajo): la clave del hardware con twirling pasa M1–M5."""
    return hw_twirl.veredicto.calidad_de_clave_aprobada


def s1_cumple(aer_cruda: InformeCorrida, aer_twirl: InformeCorrida, hw_cruda: InformeCorrida, hw_twirl: InformeCorrida) -> bool:
    """S1: el simulador corrió la MISMA declaración que el hardware: mismos qubits y mismos disparos totales por trabajo."""
    return (aer_cruda.qubits, aer_cruda.shots) == (hw_cruda.qubits, hw_cruda.shots) and (aer_twirl.qubits, aer_twirl.shots) == (
        hw_twirl.qubits,
        hw_twirl.shots,
    )


def v1_cumple(hw: Sequence[InformeCorrida], minimo_trabajos: int) -> bool:
    """V1: hay al menos `minimo_trabajos` trabajos DISTINTOS, todos de origen hardware_ibm y en un backend que no es un falso."""
    if not hw or any(i.origen is not Origen.HARDWARE_IBM for i in hw):
        return False
    if any(i.procedencia.backend.startswith("fake") for i in hw):
        return False
    return len({i.procedencia.job_id for i in hw}) >= minimo_trabajos
