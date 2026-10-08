"""Las capas de .importlinter son las de qrecauda.CAPAS, y `lint-imports` pasa. Un import prohibido sembrado falla."""

import configparser
import os
import subprocess
from pathlib import Path

import pytest

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


def _lint_con_sembrado(tmp_path, destino: str, linea: str):
    """Se siembra en una COPIA del árbol: el test nunca escribe dentro de src/ (si se interrumpe, no deja basura)."""
    import shutil

    copia = tmp_path / "repo"
    shutil.copytree(RAIZ / "src", copia / "src")
    shutil.copy(RAIZ / ".importlinter", copia / ".importlinter")
    shutil.copy(RAIZ / "pyproject.toml", copia / "pyproject.toml")
    (copia / "src" / "qrecauda" / destino / "_sembrado.py").write_text(linea + "  # noqa\n")
    env = {**os.environ, "PYTHONPATH": str(copia / "src")}
    return subprocess.run(["lint-imports"], cwd=copia, capture_output=True, text=True, env=env)


def test_un_import_prohibido_sembrado_hace_fallar_el_contrato(tmp_path):
    r = _lint_con_sembrado(tmp_path, "dominio", "import qrecauda.transversal.configuracion")
    assert r.returncode != 0


def test_c6_transversal_es_hoja_y_el_contrato_muerde(tmp_path):
    """C6: lo transversal sólo depende de la jerarquía de errores; no puede importar a quien lo usa."""
    assert "C6" in (RAIZ / ".importlinter").read_text()
    r = _lint_con_sembrado(tmp_path, "transversal", "import qrecauda.adaptadores.prng")
    assert r.returncode != 0 and "C6" in r.stdout


def _sembrar_en_existente(tmp_path, modulo: str, linea: str):
    """Como `_lint_con_sembrado`, pero añade el import a un módulo que ya existe (p. ej. un adaptador ya listado en C2)."""
    import shutil

    copia = tmp_path / "repo"
    shutil.copytree(RAIZ / "src", copia / "src")
    shutil.copy(RAIZ / ".importlinter", copia / ".importlinter")
    shutil.copy(RAIZ / "pyproject.toml", copia / "pyproject.toml")
    destino = copia / "src" / "qrecauda" / modulo
    destino.write_text(destino.read_text() + "\n" + linea + "  # noqa\n")
    env = {**os.environ, "PYTHONPATH": str(copia / "src")}
    return subprocess.run(["lint-imports"], cwd=copia, capture_output=True, text=True, env=env)


def test_c2_los_adaptadores_no_se_importan_y_el_contrato_muerde(tmp_path):
    r = _sembrar_en_existente(tmp_path, "adaptadores/nist.py", "import qrecauda.adaptadores.estadistica")
    assert r.returncode != 0 and "C2" in r.stdout


def test_c2_lista_todos_los_adaptadores_que_existen():
    """Un adaptador nuevo que no esté en la lista cerrada de C2 escaparía a la independencia (hueco R.01 M-1)."""
    cp = configparser.ConfigParser()
    cp.read(RAIZ / ".importlinter", encoding="utf-8")
    listados = {
        x.strip().removeprefix("qrecauda.adaptadores.")
        for x in cp["importlinter:contract:adaptadores-independientes"]["modules"].split("\n")
        if x.strip()
    }
    base = RAIZ / "src" / "qrecauda" / "adaptadores"
    en_disco = {p.stem for p in base.glob("*.py") if not p.stem.startswith("_")} | {
        p.name for p in base.iterdir() if (p / "__init__.py").exists()
    }
    assert listados == en_disco


@pytest.mark.parametrize("modulo", ["time", "random", "secrets", "os", "datetime", "uuid", "tempfile", "threading", "subprocess", "socket"])
def test_c4_el_dominio_puro_muerde_con_cada_modulo_vetado(tmp_path, modulo):
    r = _lint_con_sembrado(tmp_path, "dominio", f"import {modulo}")
    assert r.returncode != 0 and "C4" in r.stdout, modulo


@pytest.mark.parametrize("sdk", ["qiskit", "nistrng", "cryptography"])
@pytest.mark.parametrize("capa", ["aplicacion", "datos", "puertos", "dominio"])
def test_c5_los_sdk_solo_en_adaptadores_y_el_contrato_muerde(tmp_path, capa, sdk):
    r = _lint_con_sembrado(tmp_path, capa, f"import {sdk}")
    assert r.returncode != 0 and "C5" in r.stdout, (capa, sdk)


def test_c5b_el_borde_no_importa_un_sdk_directamente_y_el_contrato_muerde(tmp_path):
    r = _lint_con_sembrado(tmp_path, "transversal", "import cryptography")
    assert r.returncode != 0 and "C5b" in r.stdout


def test_el_dominio_no_toca_numpy_random():
    """import-linter no admite submódulos de paquetes externos (`numpy.random`): lo vigila este AST."""
    import ast

    malos = []
    for f in (RAIZ / "src" / "qrecauda" / "dominio").glob("*.py"):
        for nodo in ast.walk(ast.parse(f.read_text())):
            if (
                (
                    isinstance(nodo, ast.ImportFrom)
                    and (nodo.module or "").startswith("numpy")
                    and ((nodo.module or "").startswith("numpy.random") or any(a.name == "random" for a in nodo.names))
                )
                or isinstance(nodo, ast.Import)
                and any(a.name.startswith("numpy.random") for a in nodo.names)
                or (
                    isinstance(nodo, ast.Attribute)
                    and nodo.attr == "random"
                    and isinstance(nodo.value, ast.Name)
                    and nodo.value.id in {"np", "numpy"}
                )
            ):
                malos.append(f.name)
    assert not malos, malos
