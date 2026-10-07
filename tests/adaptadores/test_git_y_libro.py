"""Adaptadores de F2.07: el historial git como testigo y el libro de veredictos append-only."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from qrecauda.adaptadores.git import HistorialGit
from qrecauda.adaptadores.libro_jsonl import LibroJsonl
from qrecauda.dominio.errores import EntradaInvalida


def _git(raiz: Path, *a: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env |= {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", "-C", str(raiz), *a], check=True, capture_output=True, text=True, env=env).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    return tmp_path


def _commit(repo: Path, nombre: str, texto: str) -> str:
    (repo / nombre).write_text(texto)
    _git(repo, "add", nombre)
    _git(repo, "commit", "-q", "-m", f"toca {nombre}")
    return _git(repo, "rev-parse", "HEAD")


def test_la_preinscripcion_precede_a_la_corrida_y_no_al_reves(repo):
    pre = _commit(repo, "pre.md", "a")
    despues = _commit(repo, "otro.txt", "b")
    h = HistorialGit(repo)
    assert h.commit_actual() == despues and h.ultimo_commit(("pre.md",)) == pre
    assert h.precede(pre, despues) and h.precede(pre, pre)  # correr justo tras commitear: mismo commit
    assert not h.precede(despues, pre)


def test_modificado_ve_cambios_sin_commit_y_ultimo_commit_se_niega_si_no_hay_historia(repo):
    _commit(repo, "pre.md", "a")
    h = HistorialGit(repo)
    assert not h.modificado(("pre.md",))
    (repo / "pre.md").write_text("cambiada")
    assert h.modificado(("pre.md",))
    with pytest.raises(EntradaInvalida):
        h.ultimo_commit(("nunca_commiteado.md",))


def test_libro_solo_anade_en_json_canonico(tmp_path):
    libro = LibroJsonl(tmp_path / "registro" / "veredictos.jsonl")
    libro.anadir({"b": 1, "a": True})
    libro.anadir({"a": False})
    lineas = (tmp_path / "registro" / "veredictos.jsonl").read_text().splitlines()
    assert lineas[0] == '{"a":true,"b":1}' and json.loads(lineas[1]) == {"a": False}
