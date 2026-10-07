"""Las capas de .importlinter son las de qrecauda.CAPAS, y `lint-imports` pasa. Un import prohibido sembrado falla."""

import configparser
import os
import subprocess
from pathlib import Path

import qrecauda

RAIZ = Path(__file__).resolve().parents[2]


def _lint():
    return subprocess.run(["lint-imports"], cwd=RAIZ, capture_output=True, text=True)


def test_las_capas_declaradas_coinciden():
    cp = configparser.ConfigParser()
    cp.read(RAIZ / ".importlinter", encoding="utf-8")
    capas = [x.strip().removeprefix("qrecauda.") for x in cp["importlinter:contract:capas"]["layers"].split("\n") if x.strip()]
    assert tuple(c.replace(" | ", "|").replace("qrecauda.", "") for c in capas) == qrecauda.CAPAS


def test_lint_imports_pasa():
    r = _lint()
    assert r.returncode == 0, r.stdout + r.stderr


def test_un_import_prohibido_sembrado_hace_fallar_el_contrato(tmp_path):
    """Se siembra en una COPIA del árbol: el test nunca escribe dentro de src/ (si se interrumpe, no deja basura)."""
    import shutil

    copia = tmp_path / "repo"
    shutil.copytree(RAIZ / "src", copia / "src")
    shutil.copy(RAIZ / ".importlinter", copia / ".importlinter")
    shutil.copy(RAIZ / "pyproject.toml", copia / "pyproject.toml")
    (copia / "src" / "qrecauda" / "dominio" / "_sembrado.py").write_text("import qrecauda.transversal.configuracion  # noqa\n")
    env = {**os.environ, "PYTHONPATH": str(copia / "src")}
    r = subprocess.run(["lint-imports"], cwd=copia, capture_output=True, text=True, env=env)
    assert r.returncode != 0
