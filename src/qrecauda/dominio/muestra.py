"""`Muestra`: bits crudos de una fuente más la procedencia mínima para auditarlos."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .bits import Bits


class Origen(StrEnum):
    """De dónde vienen los bits. NO es un adorno: decide qué se puede afirmar de ellos."""

    PRNG_CLASICO = "prng_clasico"  # línea base: determinista, predecible dada la semilla
    SIMULADOR_AER = "simulador_aer"  # ⚠️ el muestreo de Aer es pseudoaleatorio: no es entropía cuántica
    HARDWARE_IBM = "hardware_ibm"  # la única fuente que puede reclamar origen cuántico


@dataclass(frozen=True, slots=True)
class Procedencia:
    """De qué ejecución salieron los bits. `HARDWARE_IBM` sin `job_id` no se puede construir: un doble de pruebas no
    puede pasar por hardware real (hallazgo R.00-14)."""

    backend: str = ""
    job_id: str = ""
    version: str = ""  # versión del SDK que produjo los bits


@dataclass(frozen=True, slots=True)
class Muestra:
    bits: Bits
    origen: Origen
    qubits: int
    shots: int
    mitigada: bool = False
    procedencia: Procedencia = field(default_factory=Procedencia)

    def __post_init__(self) -> None:
        if self.qubits < 1 or self.shots < 1:
            raise ValueError("qubits y shots deben ser positivos")
        if self.origen is Origen.HARDWARE_IBM and not self.procedencia.job_id:
            raise ValueError("Origen.HARDWARE_IBM exige procedencia.job_id: sin trabajo real no hay hardware")

    @property
    def reclama_origen_cuantico(self) -> bool:
        return self.origen is Origen.HARDWARE_IBM

    def mitigada_con(self, bits: Bits, *, conserva_bits_por_disparo: bool) -> Muestra:
        """Muestra tras una mitigación. Si la técnica remuestrea desde una cuasi-distribución (p. ej. mthree), los bits
        nuevos los pone un PRNG y el origen se DEGRADA: la mitigación no puede heredar el origen cuántico."""
        origen = self.origen if conserva_bits_por_disparo else Origen.PRNG_CLASICO
        return Muestra(bits, origen, self.qubits, self.shots, True, self.procedencia if conserva_bits_por_disparo else Procedencia())
