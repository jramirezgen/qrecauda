"""TemporizadorLocal: llega a la hora (ni antes ni mucho después) y no se queda si la hora ya pasó."""

import time

from qrecauda.adaptadores.temporizador_local import TemporizadorLocal


def test_espera_hasta_el_instante_pedido_sin_pasarse_mucho():
    destino = time.perf_counter_ns() + 30_000_000
    TemporizadorLocal().esperar_hasta_ns(destino)
    tarde = time.perf_counter_ns() - destino
    assert 0 <= tarde < 5_000_000  # < 5 ms en una máquina cargada de CI; el giro final apunta a decenas de µs


def test_un_instante_pasado_vuelve_de_inmediato():
    t0 = time.perf_counter_ns()
    TemporizadorLocal().esperar_hasta_ns(t0 - 10_000_000)
    assert time.perf_counter_ns() - t0 < 5_000_000
