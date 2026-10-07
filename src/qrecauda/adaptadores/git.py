"""Historial git como testigo de que la preinscripción precede a la corrida (puerto `Historial`)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.transversal.configuracion import entorno_sin_git


class HistorialGit:
    """Implementa `Historial`. Quita `GIT_*` del entorno: dentro de un hook heredarían el repo equivocado."""

    def __init__(self, raiz: Path) -> None:
        self._raiz = raiz

    def _git(self, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
        env = entorno_sin_git()
        r = subprocess.run(["git", "-C", str(self._raiz), *args], capture_output=True, text=True, env=env, check=False)
        if r.returncode not in ok:
            raise EntradaInvalida(f"git {' '.join(args)} falló ({r.returncode}): {r.stderr.strip()}")
        return r

    def commit_actual(self) -> str:
        return self._git("rev-parse", "HEAD").stdout.strip()

    def ultimo_commit(self, rutas: tuple[str, ...]) -> str:
        sha = self._git("log", "-1", "--format=%H", "--", *rutas).stdout.strip()
        if not sha:
            raise EntradaInvalida(f"ninguna de {rutas} está en el historial: la preinscripción no está commiteada")
        return sha

    def modificado(self, rutas: tuple[str, ...]) -> bool:
        return bool(self._git("status", "--porcelain", "--", *rutas).stdout.strip())

    def precede(self, antes: str, despues: str) -> bool:
        return self._git("merge-base", "--is-ancestor", antes, despues, ok=(0, 1)).returncode == 0
