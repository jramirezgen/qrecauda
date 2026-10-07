"""CLI: parsea argumentos, llama a la fachada, presenta y devuelve un código de salida de `codigos`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qrecauda import api
from qrecauda.dominio.errores import ErrorQRecauda
from qrecauda.entrada.codigos import OK, VEREDICTO_RECHAZADO, codigo_de
from qrecauda.presentacion import json_canonico, tabla


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="qrecauda", description=__doc__)
    ap.add_argument("--config", type=Path, default=None, help="TOML de configuración (los secretos, por ruta)")
    ap.add_argument("--formato", choices=("tabla", "json"), default="tabla", help="presentación del veredicto")
    args = ap.parse_args(argv)
    try:
        res = api.generar_clave(api.Configuracion.cargar(args.config))
    except ErrorQRecauda as exc:
        print(f"✗ {type(exc).__name__}: {exc}", file=sys.stderr)
        return codigo_de(exc)
    print(json_canonico(res.veredicto) if args.formato == "json" else tabla(res.veredicto))
    return OK if res.veredicto.aprobado else VEREDICTO_RECHAZADO
