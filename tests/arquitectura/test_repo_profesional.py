"""El repo trae lo que se espera de un proyecto abierto: archivos de comunidad, enlaces de la documentación y nada personal."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

COMUNIDAD = (
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CITATION.cff",
    ".editorconfig",
    "docs/USO.md",
    ".github/workflows/ci.yml",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug.md",
    ".github/ISSUE_TEMPLATE/propuesta.md",
)
# Los archivos de esta entrega; el resto del repo lo cubren otros tests.
NUEVOS = tuple(c for c in COMUNIDAD if c not in ("LICENSE",))
RUTAS_PROHIBIDAS = ("/" + "home/", "/" + "mnt/")


def test_existen_los_archivos_de_comunidad() -> None:
    faltan = [c for c in COMUNIDAD if not (RAIZ / c).is_file()]
    assert not faltan, f"faltan archivos de comunidad: {faltan}"


def test_el_readme_enlaza_la_guia_de_uso_y_las_normas() -> None:
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    for destino in ("docs/USO.md", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md", "CITATION.cff", "LICENSE"):
        assert f"]({destino})" in readme, f"el README no enlaza {destino}"


def test_los_enlaces_relativos_del_readme_existen() -> None:
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    destinos = {d.split("#")[0] for d in re.findall(r"\]\(([^)\s]+)\)", readme) if not d.startswith(("http", "#"))}
    rotos = sorted(d for d in destinos if d and not (RAIZ / d).exists())
    assert not rotos, f"enlaces rotos en el README: {rotos}"


def test_citation_cff_solo_nombra_al_alias() -> None:
    cff = (RAIZ / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(r"^version:\s*0\.1\.0\s*$", cff, re.M)
    assert re.search(r"^license:\s*Apache-2\.0\s*$", cff, re.M)
    autores = cff.split("authors:", 1)[1]
    assert "alias: kaitokid" in autores
    assert not re.search(r"family-names|given-names|^\s*-?\s*name:", autores, re.M), "un autor con nombre real en CITATION.cff"
    assert "jefferson" not in cff.lower()


def test_pyproject_autor_es_el_alias() -> None:
    import tomllib

    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert proyecto["authors"] == [{"name": "kaitokid"}]
    assert {"Homepage", "Repository", "Issues", "Changelog"} <= set(proyecto["urls"])


def test_los_archivos_nuevos_no_llevan_rutas_absolutas() -> None:
    propios = (*NUEVOS, "pyproject.toml", "tests/arquitectura/test_repo_profesional.py")
    con_ruta = [f"{n}: {r}" for n in propios for r in RUTAS_PROHIBIDAS if r in (RAIZ / n).read_text(encoding="utf-8")]
    assert not con_ruta, f"rutas absolutas en archivos versionados: {con_ruta}"
