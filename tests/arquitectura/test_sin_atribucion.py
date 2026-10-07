"""El hook commit-msg rechaza la atribución a un modelo, y ningún commit de la historia la lleva."""

import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
HOOK = RAIZ / "scripts" / "hooks" / "commit-msg"


def _hook(texto: str, tmp_path: Path) -> int:
    f = tmp_path / "msg"
    f.write_text(texto)
    return subprocess.run([str(HOOK), str(f)]).returncode


def test_el_hook_rechaza_los_trailers_de_modelo(tmp_path):
    assert _hook("x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n", tmp_path) == 1
    assert _hook("x\n\n🤖 Generated with Claude Code\n", tmp_path) == 1
    assert _hook("F1.01: Bits inmutable\n", tmp_path) == 0


def test_ningun_commit_de_la_historia_atribuye_a_un_modelo():
    r = subprocess.run(["git", "log", "--format=%an%n%cn%n%B"], cwd=RAIZ, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return  # repo sin commits todavía
    assert "anthropic" not in r.stdout.lower() and "co-authored-by: claude" not in r.stdout.lower()
