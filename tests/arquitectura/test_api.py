"""Congela las firmas de la fachada pública: cambiarlas es un cambio de versión, no un descuido.

Y comprueba que la CLI es un cliente MÁS de la fachada: no importa composición, adaptadores ni aplicación."""

import ast
import inspect
from dataclasses import fields
from pathlib import Path

from qrecauda import api, presentacion
from qrecauda.entrada import cli

SRC = Path(__file__).resolve().parents[2] / "src" / "qrecauda"


def test_firmas_congeladas():
    assert sorted(api.__all__) == [
        "Configuracion", "ManifiestoDeCorrida", "Resultado", "ResultadoDemo", "VeredictoDeEureka",
        "correr", "demo", "generar_clave", "hardware", "juzgar",
    ]  # fmt: skip
    assert str(inspect.signature(api.generar_clave)) == "(cfg: 'Configuracion') -> 'Resultado'"
    assert str(inspect.signature(api.correr)) == "(declaracion: 'Path', raiz: 'Path') -> 'ManifiestoDeCorrida'"
    assert str(inspect.signature(api.juzgar)) == "(eureka: 'str', raiz: 'Path') -> 'VeredictoDeEureka'"
    assert str(inspect.signature(api.demo)) == (
        "(cfg: 'Configuracion', *, rapido: 'bool' = False, fuente: 'str' = 'aer', ensayo: 'bool' = False, "
        "max_segundos_qpu: 'float | None' = None) -> 'ResultadoDemo'"
    )
    assert str(inspect.signature(api.hardware)) == (
        "(raiz: 'Path', *, cfg: 'Configuracion | None' = None, declaracion: 'Path' = PosixPath('declaraciones/E4.toml'), "
        "ensayo: 'bool' = False, max_segundos_qpu: 'float | None' = None, ia: 'bool' = False) -> 'ManifiestoDeCorrida'"
    )


def test_campos_de_la_configuracion_congelados():
    assert [(f.name, str(f.type)) for f in fields(api.Configuracion)] == [
        ("backend", "str"),
        ("qubits", "int"),
        ("shots", "int"),
        ("semilla", "int"),
        ("epsilon_exp", "int"),
        ("ibm_token_ruta", "str"),
        ("ibm_backend", "str"),
        ("ibm_modo", "str"),
        ("mitigacion", "str"),
        ("nivel_ruido", "str"),
        ("validador", "str"),
    ]


def test_firmas_de_presentacion_y_cli_congeladas():
    assert sorted(presentacion.__all__) == [
        "json_canonico", "json_de", "json_de_demo", "resumen_de_corrida", "tabla", "tabla_de_demo", "tabla_de_eureka",
    ]  # fmt: skip
    assert str(inspect.signature(presentacion.tabla)) == "(veredicto: 'Veredicto') -> 'str'"
    assert str(inspect.signature(presentacion.json_canonico)) == "(veredicto: 'Veredicto') -> 'str'"
    assert str(inspect.signature(cli.main)) == "(argv: 'list[str] | None' = None) -> 'int'"


def _importados(ruta: Path) -> set[str]:
    """Módulos `qrecauda.*` que importa el fichero (con `from qrecauda import api` ⇒ `qrecauda.api`)."""
    mods: set[str] = set()
    for n in ast.walk(ast.parse(ruta.read_text())):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.update(f"{n.module}.{a.name}" for a in n.names) if n.module == "qrecauda" else mods.add(n.module)
        elif isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
    return {m for m in mods if m.startswith("qrecauda")}


def test_la_cli_es_un_cliente_mas_de_la_fachada():
    """DISENO §3: la entrada importa la fachada, la jerarquía de errores y la presentación; nada más del núcleo."""
    permitido = {"qrecauda.api", "qrecauda.dominio.errores", "qrecauda.entrada.codigos", "qrecauda.presentacion"}
    for p in (SRC / "entrada").glob("*.py"):
        sobran = _importados(p) - permitido
        assert not sobran, f"{p.name} importa fuera de la fachada: {sorted(sobran)}"


def test_solo_la_composicion_elige_adaptadores():
    """Nadie por encima ni por debajo de la raíz de composición importa un adaptador concreto (los tests sí)."""
    for p in SRC.rglob("*.py"):
        rel = p.relative_to(SRC)
        if rel.parts[0] in {"adaptadores", "composicion.py"} or rel.name == "__init__.py" and rel.parts[0] == "adaptadores":
            continue
        malos = {m for m in _importados(p) if m.startswith("qrecauda.adaptadores")}
        assert not malos, f"{rel} importa adaptadores ({sorted(malos)}): sólo composicion.py los elige"
