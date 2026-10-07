"""CLI: parsea argumentos, llama a la fachada, presenta y devuelve un código de salida de `codigos`.

Sin subcomando, genera una clave (F2.03). `correr <declaracion.toml>` y `juzgar <ID>` son F2.07: de la declaración al veredicto.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qrecauda import api
from qrecauda.dominio.errores import ErrorQRecauda
from qrecauda.entrada.codigos import OK, VEREDICTO_RECHAZADO, codigo_de
from qrecauda.presentacion import json_canonico, json_de, resumen_de_corrida, tabla, tabla_de_eureka


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="qrecauda", description=__doc__)
    ap.add_argument("--config", type=Path, default=None, help="TOML de configuración (los secretos, por ruta)")
    ap.add_argument("--formato", choices=("tabla", "json"), default="tabla", help="presentación del resultado")
    ap.add_argument("--raiz", type=Path, default=Path.cwd(), help="raíz del repo (donde viven declaraciones/ y registro/)")
    sub = ap.add_subparsers(dest="orden")
    correr = sub.add_parser("correr", help="correr una declaración y escribir registro/corridas/")
    correr.add_argument("declaracion", type=Path, help="p. ej. declaraciones/E1.toml, relativa a la raíz")
    juzgar = sub.add_parser("juzgar", help="aplicar el criterio de la declaración a la corrida ya hecha")
    juzgar.add_argument("eureka", metavar="ID", help="p. ej. E1")
    return ap


def _correr(args: argparse.Namespace) -> int:
    m = api.correr(args.declaracion, args.raiz)
    print(json_de(m) if args.formato == "json" else resumen_de_corrida(m))
    return OK


def _juzgar(args: argparse.Namespace) -> int:
    v = api.juzgar(args.eureka, args.raiz)
    print(json_de(v) if args.formato == "json" else tabla_de_eureka(v))
    return OK if v.aprobado else VEREDICTO_RECHAZADO


def _generar(args: argparse.Namespace) -> int:
    res = api.generar_clave(api.Configuracion.cargar(args.config))
    print(json_canonico(res.veredicto) if args.formato == "json" else tabla(res.veredicto))
    return OK if res.veredicto.aprobado else VEREDICTO_RECHAZADO


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    orden = {"correr": _correr, "juzgar": _juzgar}.get(args.orden, _generar)
    try:
        return orden(args)
    except ErrorQRecauda as exc:
        print(f"✗ {type(exc).__name__}: {exc}", file=sys.stderr)
        return codigo_de(exc)
