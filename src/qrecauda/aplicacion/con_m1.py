"""`ConM1`: añade M1 = |p̂(1) − ½| a un validador que no lo trae (el de NIST sólo da M3, M4, M5)."""

from __future__ import annotations

from qrecauda.dominio import metricas as c
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import sesgo
from qrecauda.dominio.metricas import Medida, medir
from qrecauda.puertos import Validador


class ConM1:
    """Las preinscripciones miden M1 en cruda, mitigada y clave (P.E0, regla 4): con o sin M1 en el validador de fondo."""

    def __init__(self, interior: Validador) -> None:
        self._interior = interior

    def evaluar(self, bits: Bits) -> tuple[Medida, ...]:
        ms = self._interior.evaluar(bits)
        return ms if any(m.metrica is c.Metrica.SESGO for m in ms) else (medir(c.Metrica.SESGO, sesgo(bits)), *ms)
