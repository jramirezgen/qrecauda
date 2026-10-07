"""Todo tipo público del núcleo y todo puerto tiene su entrada en GLOSARIO.md (vocabulario cerrado, lección E1)."""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "qrecauda"
GLOSARIO = (RAIZ / "docs" / "GLOSARIO.md").read_text()
CAPAS_PUBLICAS = ["dominio", "puertos", "datos", "aplicacion"]


def _clases_publicas():
    nombres = set()
    for capa in CAPAS_PUBLICAS:
        for p in (SRC / capa).rglob("*.py"):
            for n in ast.parse(p.read_text()).body:
                if isinstance(n, ast.ClassDef) and not n.name.startswith("_"):
                    nombres.add(n.name)
    return nombres


def test_cada_tipo_publico_esta_en_el_glosario():
    sin = sorted(c for c in _clases_publicas() if c not in GLOSARIO)
    assert not sin, f"faltan en docs/GLOSARIO.md: {sin}"
