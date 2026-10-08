"""F3.07 / F7.07: `qrecauda demo` y `qrecauda hardware` por la CLI, sobre un repo git sintético en tmp
(nunca toca declaraciones/ ni registro/ reales).

El ensayo corre todo el camino de IBM (selección de backend, transpilación ISA, SamplerV2, registro del trabajo) contra `fake_sherbrooke`:
sin red ni credencial; los bits los pone Aer, así que NO es registro y el control V1 (trabajos reales) falla a propósito."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from qrecauda.dominio.errores import FuenteNoDisponible, PresupuestoQpuExcedido
from qrecauda.entrada import cli
from qrecauda.entrada.codigos import CODIGOS, OK
from qrecauda.transversal.configuracion import entorno_sin_git

RAIZ = Path(__file__).resolve().parents[2]


def _git(raiz, *args):
    subprocess.run(
        ["git", "-C", str(raiz), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, env=entorno_sin_git(),
    )  # fmt: skip


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    r = tmp_path_factory.mktemp("repo_e4")
    (r / "declaraciones").mkdir()
    (r / "docs" / "preinscripciones").mkdir(parents=True)
    texto = (RAIZ / "declaraciones" / "E4.toml").read_text().replace("shots = 100_000", "shots = 64_000")
    assert "shots = 64_000" in texto
    (r / "declaraciones" / "E4.toml").write_text(texto)
    shutil.copy(RAIZ / "declaraciones" / "PARAMETROS.toml", r / "declaraciones" / "PARAMETROS.toml")
    shutil.copy(RAIZ / "docs" / "preinscripciones" / "E4.md", r / "docs" / "preinscripciones" / "E4.md")
    _git(r, "init", "-q")
    _git(r, "add", "declaraciones", "docs")
    _git(r, "commit", "-q", "-m", "P.E4: preinscripción de prueba")
    return r


def _cli(repo, *args):
    return cli.main(["--raiz", str(repo), *args])


def test_demo_rapido_por_la_cli_imprime_tabla_y_rotulo(repo, capsys):
    assert _cli(repo, "demo", "--rapido") == OK
    out = capsys.readouterr().out
    assert "simulado: Aer es pseudoaleatorio, sin origen cuántico" in out and "AES-256-GCM" in out and "descifrado OK" in out


def test_demo_en_json_es_parseable(repo, capsys):
    assert _cli(repo, "--formato", "json", "demo", "--rapido") == OK
    assert len(json.loads(capsys.readouterr().out)["ramas"]) == 3


def test_demo_ibm_sin_token_ni_ensayo_es_fuente_no_disponible(repo, capsys):
    assert _cli(repo, "demo", "--rapido", "--fuente", "ibm") == CODIGOS[FuenteNoDisponible]
    assert "token" in capsys.readouterr().err


def test_hardware_sin_token_ni_ensayo_se_niega_y_no_escribe_nada(repo, capsys):
    assert _cli(repo, "hardware") == CODIGOS[FuenteNoDisponible]
    assert not (repo / "registro").exists()


def test_hardware_con_presupuesto_insuficiente_aborta_antes_de_enviar_codigo_11(repo, capsys):
    assert CODIGOS[PresupuestoQpuExcedido] == 11
    assert _cli(repo, "hardware", "--ensayo", "--max-segundos-qpu", "1") == 11
    assert "PresupuestoQpuExcedido" in capsys.readouterr().err
    assert not (repo / "salidas" / "ensayo_e4").exists() or not any((repo / "salidas" / "ensayo_e4").glob("C.E4*_informe_*.json"))


def test_hardware_ensayo_de_punta_a_punta_escribe_fuera_del_registro(repo, capsys):
    assert _cli(repo, "hardware", "--ensayo") == OK
    cap = capsys.readouterr()
    assert "NO son registro" in cap.err
    carpeta = repo / "salidas" / "ensayo_e4"
    informes = sorted(carpeta.glob("C.E4*_informe_*.json"))
    assert len(informes) == 15  # 5 corridas × 3 semillas
    assert not (repo / "registro").exists()
    todos = [json.loads(p.read_text()) for p in informes]
    d = next(i for i in todos if i["corrida"] == "C.E4e")
    assert sorted({i["corrida"] for i in todos}) == ["C.E4a", "C.E4b", "C.E4c", "C.E4d", "C.E4e"]
    assert d["reporte"]["trabajo"]["backend"] == "fake_sherbrooke" and d["reporte"]["trabajo"]["job_id"]
    assert len(d["reporte"]["sesgos_por_qubit"]) == 8
