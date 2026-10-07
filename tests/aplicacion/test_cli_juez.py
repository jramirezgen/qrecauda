"""F2.07: `qrecauda correr <declaracion.toml>` y `qrecauda juzgar <ID>` de punta a punta, sobre un repo git sintético en tmp.

La declaración es sintética (X1, backend prng): ejercita la ruta real —Almacén, Historial git, libro— sin tocar declaraciones/ del repo.
"""

import json
import subprocess

import pytest

from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida
from qrecauda.entrada import cli
from qrecauda.entrada.codigos import CODIGOS, OK
from qrecauda.transversal.configuracion import entorno_sin_git

TOML = """\
[experimento]
id = "X1"
nodo_corrida = "C.X1"

[cadena]
qubits = 8
shots = 20000
semillas = [20261007, 20261008]

[configuracion]
backend = "prng"
"""


def _git(raiz, *args):
    subprocess.run(
        ["git", "-C", str(raiz), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, env=entorno_sin_git(),
    )  # fmt: skip


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "declaraciones").mkdir()
    (tmp_path / "docs" / "preinscripciones").mkdir(parents=True)
    (tmp_path / "declaraciones" / "X1.toml").write_text(TOML)
    (tmp_path / "docs" / "preinscripciones" / "X1.md").write_text("# X1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "declaraciones", "docs")
    _git(tmp_path, "commit", "-q", "-m", "P.X1: preinscripción")
    return tmp_path


def _cli(repo, *args):
    return cli.main(["--raiz", str(repo), *args])


def test_correr_escribe_el_manifiesto_y_los_informes_por_el_almacen(repo, capsys):
    assert _cli(repo, "correr", "declaraciones/X1.toml") == OK
    assert "CORRIDA C.X1 (X1): 2 artefactos" in capsys.readouterr().out
    corridas = repo / "registro" / "corridas"
    manifiesto = json.loads((corridas / "C.X1.json").read_text())
    assert manifiesto["eureka"] == "X1" and len(manifiesto["artefactos"]) == 2
    assert all((corridas / f"{nombre}.json").is_file() for nombre, _, _ in manifiesto["artefactos"])
    assert manifiesto["preinscripcion_sha"] == manifiesto["commit"]  # aquí la preinscripción es el HEAD


def test_juzgar_aplica_el_criterio_y_anade_una_linea_al_libro(repo, capsys):
    assert _cli(repo, "correr", "declaraciones/X1.toml") == OK
    capsys.readouterr()
    assert _cli(repo, "--formato", "json", "juzgar", "X1") == OK
    v = json.loads(capsys.readouterr().out)
    assert v["desenlace"] == "CUMPLE" and [c["id"] for c in v["criterios"]] == ["clave/20261007", "clave/20261008"]
    libro = (repo / "registro" / "veredictos.jsonl").read_text().splitlines()
    assert len(libro) == 1 and json.loads(libro[0])["eureka"] == "X1"


def test_juzgar_sin_haber_corrido_es_corrida_invalida_codigo_9(repo, capsys):
    assert _cli(repo, "juzgar", "X1") == CODIGOS[CorridaInvalida] == 9
    assert "CorridaInvalida" in capsys.readouterr().err
    assert not (repo / "registro" / "veredictos.jsonl").exists()


def test_juzgar_se_niega_si_la_preinscripcion_cambio_despues_de_la_corrida(repo, capsys):
    assert _cli(repo, "correr", "declaraciones/X1.toml") == OK
    (repo / "docs" / "preinscripciones" / "X1.md").write_text("# X1 movida\n")
    _git(repo, "add", "docs")
    _git(repo, "commit", "-q", "-m", "mueve el criterio")
    assert _cli(repo, "juzgar", "X1") == 9
    assert "cambió después" in capsys.readouterr().err


def test_correr_se_niega_con_la_preinscripcion_sin_commit(repo):
    (repo / "docs" / "preinscripciones" / "X1.md").write_text("# X1 sin commit\n")
    assert _cli(repo, "correr", "declaraciones/X1.toml") == CODIGOS[CorridaInvalida]


def test_declaracion_sin_preinscripcion_o_id_ilegal_es_entrada_invalida(repo):
    (repo / "declaraciones" / "X2.toml").write_text(TOML.replace("X1", "X2"))
    assert _cli(repo, "correr", "declaraciones/X2.toml") == CODIGOS[EntradaInvalida]
    assert _cli(repo, "juzgar", "../etc") == CODIGOS[EntradaInvalida]


def test_e2_con_declaracion_incompleta_se_niega_no_se_simula(repo):
    """E2 ya tiene ejecutor real: una declaración sin sus tablas es corrida inválida (9), nunca una simulación."""
    (repo / "docs" / "preinscripciones" / "E2.md").write_text("# E2\n")
    (repo / "declaraciones" / "E2.toml").write_text(TOML.replace("X1", "E2"))
    assert _cli(repo, "correr", "declaraciones/E2.toml") == 9


def test_un_control_exigido_y_no_medido_es_corrida_invalida(repo, capsys):
    """Un control exigido que el ejecutor no mide no es un NO CUMPLE: es corrida inválida (9), no un veredicto."""
    (repo / "declaraciones" / "X1.toml").write_text(TOML + '\n[controles]\nrequeridos = ["K1"]\n')
    _git(repo, "add", "declaraciones")
    _git(repo, "commit", "-q", "-m", "exige un control")
    assert _cli(repo, "correr", "declaraciones/X1.toml") == OK
    assert _cli(repo, "juzgar", "X1") == 9
    assert "falta el control K1" in capsys.readouterr().err
