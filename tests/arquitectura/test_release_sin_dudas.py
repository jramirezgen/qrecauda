"""REL-0.2.0 (y 0.1.0): un release no arrastra dudas vigentes en FUNDAMENTO ni en las decisiones, y su título no excede el TRL."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DUDA = "⚠️"


def _vigentes(ruta: Path) -> list[str]:
    return [f"{ruta.relative_to(RAIZ)}:{i}" for i, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1) if DUDA in linea]


def test_fundamento_y_decisiones_no_tienen_marcadores_de_duda_vigentes() -> None:
    rutas = [RAIZ / "docs" / "FUNDAMENTO.md", *sorted((RAIZ / "docs" / "decisiones").glob("*.md"))]
    quedan = [x for r in rutas for x in _vigentes(r)]
    assert not quedan, f"marcadores de duda vigentes en un release: {quedan}"


def test_el_expediente_y_el_changelog_dicen_el_trl_que_sostiene_la_matriz() -> None:
    trl = (RAIZ / "docs" / "TRL.md").read_text(encoding="utf-8")
    sistema = re.search(r"TRL del sistema:\s*(\d)", trl)
    assert sistema, "docs/TRL.md debe declarar «TRL del sistema: N»"
    for version in ("0.1.0", "0.2.0"):
        exp = (RAIZ / "docs" / "releases" / f"EXPEDIENTE_{version}.md").read_text(encoding="utf-8")
        assert f"TRL del sistema: {sistema.group(1)}" in exp, version
        assert "certificad" not in exp.lower().replace("no entra", "").split("## 1.")[0], version
        assert version in (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8"), version


def test_la_version_del_paquete_es_la_del_release() -> None:
    from qrecauda import __version__

    assert __version__ == "0.2.0"
    assert 'version = "0.2.0"' in (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
