"""`Registradora`: envuelve una fuente y recuerda la última muestra CRUDA, y `huella`: el sha256 de unos bits."""

from __future__ import annotations

import hashlib

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.muestra import Muestra
from qrecauda.puertos import FuenteDeBits


class Registradora:
    """El pipeline sólo devuelve la muestra que entró al extractor (la mitigada): para auditar la cruda hay que guardarla al pasar."""

    def __init__(self, interior: FuenteDeBits) -> None:
        self._interior = interior
        self.ultima: Muestra | None = None

    def generar(self, qubits: int, shots: int) -> Muestra:
        self.ultima = self._interior.generar(qubits, shots)
        return self.ultima

    @property
    def cruda(self) -> Muestra:
        assert self.ultima is not None  # el pipeline llamó a la fuente
        return self.ultima


def huella(bits: Bits) -> str:
    return hashlib.sha256(bits.datos.tobytes()).hexdigest()
