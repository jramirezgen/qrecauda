"""Trinquetes por AST: lo que el DISENO.md promete en prosa se comprueba aquí."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "qrecauda"


def _py(sub: str = ""):
    return [p for p in (SRC / sub).rglob("*.py")]


def test_os_environ_solo_en_configuracion():
    malos = []
    for p in _py():
        if p == SRC / "transversal" / "configuracion.py":
            continue
        t = p.read_text()
        if "os.environ" in t or "getenv" in t:
            malos.append(str(p.relative_to(SRC)))
    assert not malos, f"os.environ/getenv sólo en transversal/configuracion.py: {malos}"


def test_ningun_except_exception_silencioso():
    malos = []
    for p in _py():
        for n in ast.walk(ast.parse(p.read_text())):
            if isinstance(n, ast.ExceptHandler) and (
                n.type is None or (isinstance(n.type, ast.Name) and n.type.id in {"Exception", "BaseException"})
            ):
                malos.append(f"{p.relative_to(SRC)}:{n.lineno}")
    assert not malos, malos


def test_ninguna_credencial_en_el_codigo():
    import re

    patron = re.compile(r"(ibm_?quantum|api[_-]?key|token)\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]", re.I)
    assert not [str(p) for p in _py() if patron.search(p.read_text())]


def test_dominio_sin_aleatoriedad_global():
    """DISENO promete «sin aleatoriedad global»: C4 veta `random`, esto veta `numpy.random` y `default_rng`."""
    malos = []
    for p in _py("dominio"):
        for n in ast.walk(ast.parse(p.read_text())):
            if isinstance(n, ast.Attribute) and n.attr == "random" and isinstance(n.value, ast.Name) and n.value.id in {"np", "numpy"}:
                malos.append(f"{p.relative_to(SRC)}:{n.lineno}")
            if isinstance(n, ast.Name) and n.id == "default_rng":
                malos.append(f"{p.relative_to(SRC)}:{n.lineno}")
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("numpy.random"):
                malos.append(f"{p.relative_to(SRC)}:{n.lineno}")
    assert not malos, f"el dominio no puede sortear nada: la semilla llega por el puerto FuenteDeSemilla ({malos})"
