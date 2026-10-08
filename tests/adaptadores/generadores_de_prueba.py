"""Generadores de claves SIMPLES, de nivel de módulo para que crucen a un proceso `spawn` (el hijo los importa por nombre)."""

from __future__ import annotations

import os
import time

import numpy as np

from qrecauda.datos import ClaveEntregada, MetaClave
from qrecauda.dominio.bits import Bits


class GeneradorRapido:
    def __init__(self, pausa_s: float = 0.0, falla_en: int | None = None, nucleo: int | None = None, falla_rara: bool = False) -> None:
        self.pausa_s, self.falla_en, self.falla_rara = pausa_s, falla_en, falla_rara
        if nucleo is not None:
            os.sched_setaffinity(0, {nucleo})

    def generar(self, indice: int) -> ClaveEntregada:
        if self.falla_en == indice and self.falla_rara:
            raise KeyError("clave-que-no-esta")  # una excepción que ninguna lista de «fallos esperados» nombraba
        if self.falla_en == indice:
            raise ValueError("falla de prueba en el hijo")
        t0 = time.perf_counter_ns()
        time.sleep(self.pausa_s)
        rng = np.random.default_rng(indice)
        bits = Bits((rng.random(704) < 0.5).astype(np.uint8))
        fin = time.perf_counter_ns()
        return ClaveEntregada(
            bits, MetaClave(indice, indice, len(bits), 0, fin - t0, 0.9, fin, f"{indice:012x}"), "validación del pipeline", "simulador_aer"
        )


def fabrica(pausa_s: float = 0.0, falla_en: int | None = None, nucleo: int | None = None, falla_rara: bool = False) -> GeneradorRapido:
    return GeneradorRapido(pausa_s, falla_en, nucleo, falla_rara)
