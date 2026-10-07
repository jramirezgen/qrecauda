"""SondaLocal: carga, CPU y máquina de verdad (sin dobles; sólo se comprueba forma y monotonía, no valores)."""

import time

from qrecauda.adaptadores.sonda_local import SondaLocal
from qrecauda.puertos import SondaDeMaquina


def test_implementa_el_puerto_y_la_cpu_avanza_con_el_trabajo():
    s: SondaDeMaquina = SondaLocal()
    a, h0 = s.cpu_proceso_ns(), s.cpu_con_hijos_ns()
    t = time.perf_counter()
    while time.perf_counter() - t < 0.05:
        pass  # quema CPU
    assert s.cpu_proceso_ns() - a > 20_000_000  # ≥ 20 ms de CPU tras 50 ms de bucle
    assert s.cpu_con_hijos_ns() >= h0 and s.carga_previa() >= 0.0


def test_la_cpu_de_los_hijos_esperados_cuenta_en_la_segunda_lectura_no_en_la_primera():
    import subprocess
    import sys

    s = SondaLocal()
    p0, h0 = s.cpu_proceso_ns(), s.cpu_con_hijos_ns()
    subprocess.run(
        [sys.executable, "-c", "t=__import__('time').perf_counter()\nwhile __import__('time').perf_counter()-t<0.2: pass"], check=True
    )
    dp, dh = s.cpu_proceso_ns() - p0, s.cpu_con_hijos_ns() - h0
    assert dh - dp > 100_000_000  # el hijo (≥ 0,1 s de CPU) sólo está en la lectura con hijos


def test_la_maquina_se_describe_con_cpu_nucleos_ram_y_kernel():
    m = SondaLocal().maquina()
    assert {"cpu", "nucleos_logicos", "ram_total_kb", "kernel", "python"} <= set(m)
    assert all(isinstance(v, str) and v for v in m.values())
