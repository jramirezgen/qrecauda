"""Temporizador — espera hasta un instante de `time.perf_counter_ns` (F6.03; E3b: llegadas programadas a λ tx/s).

Duerme hasta poco antes del instante (el `sleep` de WSL2 se pasa por ms) y gira el último tramo; el núcleo del consumidor es suyo.
"""

from __future__ import annotations

import time

MARGEN_DE_GIRO_NS = 1_500_000  # lo que se gira en vez de dormir


class TemporizadorLocal:
    """Implementa `Temporizador`."""

    def esperar_hasta_ns(self, instante_ns: int) -> None:
        while (falta := instante_ns - time.perf_counter_ns()) > MARGEN_DE_GIRO_NS:
            time.sleep((falta - MARGEN_DE_GIRO_NS) / 1e9)
        while time.perf_counter_ns() < instante_ns:
            pass
