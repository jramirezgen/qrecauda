"""Estimador de min-entropía NIST SP 800-90B (DAG F5.02): envuelve el binario oficial `ea_non_iid` v1.1.8 como lo dejó S.04.

El binario se compila FUERA del repo con `bash spikes/S04_90b/build_nist.sh` (red y g++ la primera vez). Aquí no se compila:
si falta, se aborta con la instrucción. Se contrasta con la cota MCV de dominio/entropia en un test.
⚠️ El mínimo de los 10 estimadores es una cota inferior conservadora (S.04: IID p=0,7 → 0,322 frente a 0,515 teórico).
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntropiaInsuficiente, ErrorQRecauda, FuenteNoDisponible

BINARIO_EN_CACHE = Path.home() / ".cache" / "qrecauda" / "nist90b" / "ea_non_iid"  # fuera de /tmp: un directorio de usuario no es de todos
BINARIO_HEREDADO = Path("/tmp/qrecauda_nist90b/ea_non_iid")  # donde lo dejaba 0.1.0 y donde lo cachea la CI antigua
DIR_MUESTRA_RAPIDO = Path("/dev/shm")  # RAM: la muestra (bits de claves candidatas) no toca el disco si hay alternativa


def ubicar_binario() -> Path:
    """El binario en la caché del usuario; si sólo existe el heredado de /tmp se usa ése (compatibilidad); si no hay ninguno, la caché."""
    return BINARIO_HEREDADO if not BINARIO_EN_CACHE.is_file() and BINARIO_HEREDADO.is_file() else BINARIO_EN_CACHE


BINARIO_POR_DEFECTO = ubicar_binario()
MUESTRAS_MIN = 1_000_000  # «at least 1 million entries (samples)» (S.04)
INSTRUCCION_BUILD = "bash spikes/S04_90b/build_nist.sh  # compila ea_non_iid en ~/.cache/qrecauda/nist90b (necesita red y g++)"
_H_ORIGINAL = re.compile(r"^H_original: (-?[0-9.]+)", re.M)


def verificar_propietario(binario: Path) -> None:
    """El binario se ejecuta con los permisos del usuario: debe ser suyo (o de root) y nadie más puede escribirlo."""
    st = binario.stat()
    if st.st_uid not in (os.getuid(), 0):
        raise FuenteNoDisponible(f"{binario} pertenece al uid {st.st_uid}, no a este usuario ni a root: no se ejecuta")
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise FuenteNoDisponible(f"{binario} es escribible por otros (modo {stat.S_IMODE(st.st_mode):o}): no se ejecuta")


@contextlib.contextmanager
def _muestra_temporal() -> Iterator[Path]:
    """Directorio 0700 (en RAM si existe /dev/shm) para la muestra; el fichero se trunca y se borra al salir, haya o no error."""
    base = str(DIR_MUESTRA_RAPIDO) if DIR_MUESTRA_RAPIDO.is_dir() and os.access(DIR_MUESTRA_RAPIDO, os.W_OK) else None
    d = Path(tempfile.mkdtemp(prefix="qrecauda90b-", dir=base))  # mkdtemp crea con 0700
    try:
        yield d / "s.bin"
    finally:
        with contextlib.suppress(OSError):
            (d / "s.bin").write_bytes(b"")  # truncar antes de desvincular: en un disco, el contenido no queda en el bloque
        shutil.rmtree(d, ignore_errors=True)


def _ejecutar_en_grupo(orden: list[str], tiempo_max_s: float) -> subprocess.CompletedProcess[str]:
    """`subprocess.run` pero en una sesión propia: si se agota el tiempo o se interrumpe, se mata el grupo entero (OpenMP incluido)."""
    with subprocess.Popen(  # noqa: S603
        orden, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
    ) as proc:
        terminado = False
        try:
            salida, error = proc.communicate(timeout=tiempo_max_s)
            terminado = True
        finally:
            if not terminado:  # tiempo agotado o interrupción: matar el grupo entero antes de que salga la excepción
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
    return subprocess.CompletedProcess(orden, proc.returncode, salida, error)


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
        verificar_propietario(self._binario)
        with _muestra_temporal() as fichero:
            fichero.write_bytes(bits.datos.tobytes())  # un símbolo de 1 bit por byte
            try:
                r = _ejecutar_en_grupo([str(self._binario), "-i", "-a", str(fichero), "1"], self._tiempo_max_s)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise FuenteNoDisponible(f"ea_non_iid no pudo ejecutarse: {e}") from e
        m = _H_ORIGINAL.search(r.stdout)
        if r.returncode != 0 or m is None:
            raise ErrorQRecauda(f"ea_non_iid terminó con código {r.returncode} sin H_original: {r.stderr.strip()[:200]}")
        return min(1.0, max(0.0, float(m.group(1))))  # NIST imprime «-0.000000» para cero
