"""El hook commit-msg rechaza la atribución a un modelo, y ningún commit de la historia la lleva."""

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
HOOK = RAIZ / "scripts" / "hooks" / "commit-msg"


def _hook(texto: str, tmp_path: Path) -> int:
    f = tmp_path / "msg"
    f.write_text(texto)
    return subprocess.run([str(HOOK), str(f)]).returncode


@pytest.mark.parametrize(
    "mensaje",
    [
        "x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n",
        "x\n\nCo-authored-by: Sonnet 5.5 <n@x.com>\n",
        "x\n\nCo-authored-by: Una Persona <p@x.com>\n",  # cualquier Co-authored-by: nunca se atribuye
        "x\n\nAssisted-by: Opus\n",
        "x\n\nGenerated-by: GPT-5\n",
        "x\n\n🤖 Generated with Claude Code\n",
        "x\n\nescrito con ayuda de Gemini\n",
        "x\n\nlo revisó copilot\n",
        "haiku: arreglo\n",
    ],
)
def test_el_hook_rechaza_atribuciones_y_menciones_a_modelos(mensaje, tmp_path):
    assert _hook(mensaje, tmp_path) == 1


def test_el_hook_deja_pasar_un_mensaje_normal_y_los_comentarios_de_git(tmp_path):
    assert _hook("F1.01: Bits inmutable\n", tmp_path) == 0
    assert _hook("F1.01: Bits inmutable\n\n# Co-authored-by: lo que sugiere git en un comentario\n", tmp_path) == 0
    assert _hook("Gptimizar el ciclo\n", tmp_path) == 0  # una palabra que sólo contiene «gpt» no es un modelo


def test_ningun_commit_de_la_historia_atribuye_a_un_modelo(tmp_path):
    """El mismo criterio que el hook, aplicado a cada mensaje y a los nombres de autor/committer de `git log`."""
    r = subprocess.run(["git", "log", "--format=%H"], cwd=RAIZ, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return  # repo sin commits todavía
    malos = []
    for sha in r.stdout.split():
        m = subprocess.run(["git", "show", "-s", "--format=%an <%ae>%n%cn <%ce>%n%n%B", sha], cwd=RAIZ, capture_output=True, text=True)
        if _hook(m.stdout, tmp_path) != 0:
            malos.append(sha[:7])
    assert not malos, f"commits que el hook habría rechazado: {malos}"


def test_el_pre_push_se_niega_si_la_ci_local_esta_en_rojo(tmp_path):
    (tmp_path / "scripts").mkdir()
    for nombre, codigo in (("rojo", 1), ("verde", 0)):
        ci = tmp_path / "scripts" / "ci_local.sh"
        ci.write_text(f"#!/usr/bin/env bash\nexit {codigo}\n")
        ci.chmod(0o755)
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        r = subprocess.run([str(RAIZ / "scripts" / "hooks" / "pre-push")], cwd=tmp_path)
        assert r.returncode == codigo, nombre


def test_los_hooks_estan_instalados():
    r = subprocess.run(["git", "config", "core.hooksPath"], cwd=RAIZ, capture_output=True, text=True)
    assert r.stdout.strip() == "scripts/hooks"
