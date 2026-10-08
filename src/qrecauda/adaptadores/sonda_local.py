"""SondaDeMaquina — carga, CPU y descripción de la máquina local (DAG C.E3; P.E3 «máquina» y T4).

`cpu_proceso_ns` es `time.process_time_ns` (CPU de todos los hilos del proceso, sin hijos): lo que define T4. `cpu_con_hijos_ns`
suma los hijos ya esperados (`os.times`): el binario del 90B corre como hijo y `process_time` no lo cuenta; se reporta aparte.
La máquina se REGISTRA, no se promete (⚠️ en WSL2 los relojes no coinciden con los de Windows): modelo de CPU, núcleos lógicos, RAM,
kernel, plataforma y las versiones de `transversal.reproducibilidad.entorno()`.
"""

from __future__ import annotations

import os
import platform
import time
from pathlib import Path

from qrecauda.transversal.reproducibilidad import entorno


def _linea(ruta: str, prefijo: str) -> str:
    try:
        for linea in Path(ruta).read_text(encoding="utf-8", errors="replace").splitlines():
            if linea.startswith(prefijo):
                return linea.split(":", 1)[1].strip()
    except OSError:
        pass
    return "desconocido"


class SondaLocal:
    """Implementa `SondaDeMaquina`."""

    def carga_previa(self) -> float:
        return float(os.getloadavg()[0])

    def esperar_reposo(self, maximo: float, tope_s: float) -> None:
        """Deja decaer la carga que dejó la semilla anterior (la propia medición suma ≈ 1): espera hasta `tope_s` a que baje de `maximo`."""
        limite = time.monotonic() + tope_s
        while os.getloadavg()[0] >= maximo and time.monotonic() < limite:
            time.sleep(5)

    def cpu_proceso_ns(self) -> int:
        return time.process_time_ns()

    def cpu_con_hijos_ns(self) -> int:
        t = os.times()
        return round((t.user + t.system + t.children_user + t.children_system) * 1e9)

    def maquina(self) -> dict[str, str]:
        meminfo = _linea("/proc/meminfo", "MemTotal")
        return {
            "cpu": _linea("/proc/cpuinfo", "model name"),
            "nucleos_logicos": str(os.cpu_count()),
            "ram_total_kb": meminfo.removesuffix(" kB") if meminfo != "desconocido" else meminfo,
            "kernel": platform.release(),
            **entorno(),
        }
