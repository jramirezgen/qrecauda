"""R.02: scripts/ibm_run.sh valida el tope y los permisos del token ANTES de gastar nada. `uv` se sustituye por un doble que imprime."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ibm_run.sh"


@pytest.fixture
def entorno(tmp_path: Path) -> dict[str, str]:
    falso = tmp_path / "bin"
    falso.mkdir()
    uv = falso / "uv"
    uv.write_text('#!/usr/bin/env bash\necho "UV $*"\n')
    uv.chmod(0o755)
    return {**os.environ, "PATH": f"{falso}:{os.environ['PATH']}", "MAX_SEGUNDOS_QPU": ""}


def _correr(entorno: dict[str, str], *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env={**entorno, **extra}, check=False)


def _token(tmp_path: Path, modo: int) -> Path:
    t = tmp_path / "token.txt"
    t.write_text("tok-SECRETO-0123456789abcdef")
    t.chmod(modo)
    return t


@pytest.mark.parametrize("malo", ["nan", "inf", "1e12", "0", "-5", "90s", "999999"])
def test_un_tope_absurdo_aborta_con_codigo_2_antes_de_llamar_a_uv(entorno, tmp_path, malo):
    r = _correr(entorno, "demo", str(_token(tmp_path, 0o600)), MAX_SEGUNDOS_QPU=malo)
    assert r.returncode == 2 and "MAX_SEGUNDOS_QPU" in r.stderr and "UV" not in r.stdout


def test_un_tope_valido_se_reenvia_y_sin_tope_el_array_vacio_no_rompe(entorno, tmp_path):
    t = _token(tmp_path, 0o600)
    con = _correr(entorno, "demo", str(t), MAX_SEGUNDOS_QPU="90.5")
    sin = _correr(entorno, "demo", str(t))
    assert con.returncode == 0 and "--max-segundos-qpu 90.5" in con.stdout
    assert sin.returncode == 0 and "--max-segundos-qpu" not in sin.stdout and "unbound" not in sin.stderr


def test_real_aborta_si_el_token_es_legible_por_otros(entorno, tmp_path):
    t = _token(tmp_path, 0o644)
    r = _correr(entorno, "real", str(t))
    if "AVISO" in r.stderr:  # /tmp en un sistema de ficheros sin permisos POSIX fiables: sólo avisa
        pytest.skip("el sistema de ficheros de /tmp no guarda permisos POSIX")
    assert r.returncode == 3 and "chmod 600" in r.stderr and "UV" not in r.stdout
    assert stat.S_IMODE(t.stat().st_mode) == 0o644 and "tok-SECRETO" not in r.stdout + r.stderr


def test_demo_con_token_abierto_avisa_pero_sigue(entorno, tmp_path):
    r = _correr(entorno, "demo", str(_token(tmp_path, 0o644)))
    assert r.returncode == 0 and "UV run qrecauda demo --fuente ibm" in r.stdout
