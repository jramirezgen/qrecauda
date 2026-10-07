"""Estimador de min-entropía NIST SP 800-90B (DAG F5.02): envuelve el binario oficial `ea_non_iid` v1.1.8 como lo dejó S.04.

El binario se compila FUERA del repo con `bash spikes/S04_90b/build_nist.sh` (red y g++ la primera vez). Aquí no se compila:
si falta, se aborta con la instrucción. Se contrasta con la cota MCV de dominio/entropia en un test.
⚠️ El mínimo de los 10 estimadores es una cota inferior conservadora (S.04: IID p=0,7 → 0,322 frente a 0,515 teórico).
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntropiaInsuficiente, ErrorQRecauda, FuenteNoDisponible

BINARIO_POR_DEFECTO = Path("/tmp/qrecauda_nist90b/ea_non_iid")
MUESTRAS_MIN = 1_000_000  # «at least 1 million entries (samples)» (S.04)
INSTRUCCION_BUILD = "bash spikes/S04_90b/build_nist.sh  # compila ea_non_iid en /tmp/qrecauda_nist90b (necesita red y g++)"
_H_ORIGINAL = re.compile(r"^H_original: (-?[0-9.]+)", re.M)


class EstimadorNist90B:
    """Implementa `EstimadorDeEntropia`: h = H_original de `ea_non_iid -i -a`, a 1 bit por símbolo, acotado a [0, 1]."""

    def __init__(self, binario: Path = BINARIO_POR_DEFECTO, tiempo_max_s: float = 1800.0) -> None:
        self._binario = binario
        self._tiempo_max_s = tiempo_max_s

    def estimar(self, bits: Bits) -> float:
        if len(bits) < MUESTRAS_MIN:
            raise EntropiaInsuficiente(f"SP 800-90B exige ≥ {MUESTRAS_MIN} muestras, llegaron {len(bits)}")
        if not self._binario.is_file():
            raise FuenteNoDisponible(f"falta {self._binario}; compílalo con: {INSTRUCCION_BUILD}")
        with tempfile.TemporaryDirectory() as t:
            fichero = Path(t) / "s.bin"
            fichero.write_bytes(bits.datos.tobytes())  # un símbolo de 1 bit por byte
            try:
                r = subprocess.run(
                    [str(self._binario), "-i", "-a", str(fichero), "1"],
                    capture_output=True,
                    text=True,
                    timeout=self._tiempo_max_s,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                raise FuenteNoDisponible(f"ea_non_iid no pudo ejecutarse: {e}") from e
        m = _H_ORIGINAL.search(r.stdout)
        if r.returncode != 0 or m is None:
            raise ErrorQRecauda(f"ea_non_iid terminó con código {r.returncode} sin H_original: {r.stderr.strip()[:200]}")
        return min(1.0, max(0.0, float(m.group(1))))  # NIST imprime «-0.000000» para cero
