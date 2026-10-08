"""CLI: parsea argumentos, llama a la fachada, presenta y devuelve un código de salida de `codigos`.

Sin subcomando, genera una clave (F2.03). `correr <declaracion.toml>` y `juzgar <ID>` son F2.07: de la declaración al veredicto.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from qrecauda import api
from qrecauda.dominio.errores import ErrorQRecauda
from qrecauda.entrada.codigos import OK, VEREDICTO_RECHAZADO, codigo_de
from qrecauda.presentacion import json_canonico, json_de, json_de_demo, resumen_de_corrida, tabla, tabla_de_demo, tabla_de_eureka


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
    demo = sub.add_parser(
        "demo", help="la cadena entera en un minuto: PRNG, Aer sin mitigar y Aer con twirling, y dos transacciones cifradas"
    )
    demo.add_argument("--rapido", action="store_true", help="menos disparos: segundos en vez de un minuto")
    demo.add_argument("--semilla", type=int, default=None, help="semilla (por omisión la de la configuración)")
    demo.add_argument("--shots", type=int, default=None, help="disparos de las ramas de Aer (por omisión 100000, o 40000 con --rapido)")
    demo.add_argument(
        "--dimensionado", choices=("mcv", "conservador"), default=None,
        help="«mcv» (por omisión) o «conservador» (mínimo con el 90B; exige >= 1 Mbit por rama: sube --shots)",
    )  # fmt: skip
    _opciones_ibm(demo)
    demo.add_argument("--fuente", choices=("aer", "ibm"), default="aer", help="«ibm» añade el hardware (o su --ensayo)")
    hw = sub.add_parser("hardware", help="E4: el mismo circuito en Aer y en el hardware de IBM (>= 3 trabajos) a registro/corridas/")
    hw.add_argument("--declaracion", type=Path, default=Path("declaraciones/E4.toml"), help="por omisión declaraciones/E4.toml")
    hw.add_argument("--ia", action="store_true", help="enrutado con IA (qiskit_ibm_transpiler); si falta, degrada CON aviso")
    _opciones_ibm(hw)
    return ap


def _opciones_ibm(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--token-file", type=Path, default=None, metavar="RUTA", help="RUTA del fichero con el token de IBM (nunca el valor)")
    ap.add_argument("--backend", default="", help="nombre del backend de IBM; vacío = el menos ocupado con >= 8 qubits")
    ap.add_argument("--ensayo", action="store_true", help="todo el camino contra un backend falso de IBM: sin cuota ni credencial")
    ap.add_argument("--max-segundos-qpu", type=float, default=None, help="tope de segundos de QPU (finito, > 0): aborta ANTES de enviar")
    ap.add_argument("--instancia", default="", help="instancia de IBM (CRN o nombre); vacío = la que elija el servicio")


def _config_con_ibm(args: argparse.Namespace) -> api.Configuracion:
    cfg = api.Configuracion.cargar(args.config)
    cambios: dict[str, object] = {"ibm_backend": args.backend or cfg.ibm_backend}
    if args.token_file is not None:
        cambios["ibm_token_ruta"] = str(args.token_file)
    if args.instancia:
        cambios["ibm_instancia"] = args.instancia
    if getattr(args, "semilla", None) is not None:
        cambios["semilla"] = args.semilla
    if getattr(args, "dimensionado", None) is not None:
        cambios["dimensionado"] = args.dimensionado
    return replace(cfg, **cambios)  # type: ignore[arg-type]


def _demo(args: argparse.Namespace) -> int:
    d = api.demo(
        _config_con_ibm(args), rapido=args.rapido, fuente=args.fuente, ensayo=args.ensayo, max_segundos_qpu=args.max_segundos_qpu,
        shots=args.shots,
    )  # fmt: skip
    print(json_de_demo(d) if args.formato == "json" else tabla_de_demo(d))
    return OK


def _hardware(args: argparse.Namespace) -> int:
    m = api.hardware(
        args.raiz,
        cfg=_config_con_ibm(args),
        declaracion=args.declaracion,
        ensayo=args.ensayo,
        max_segundos_qpu=args.max_segundos_qpu,
        ia=args.ia,
    )
    print(json_de(m) if args.formato == "json" else resumen_de_corrida(m))
    if args.ensayo:
        print("ENSAYO contra un backend falso: los artefactos están en salidas/ensayo_e4/ y NO son registro.", file=sys.stderr)
    return OK


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
    orden = {"correr": _correr, "juzgar": _juzgar, "demo": _demo, "hardware": _hardware}.get(args.orden, _generar)
    try:
        return orden(args)
    except ErrorQRecauda as exc:
        print(f"✗ {type(exc).__name__}: {exc}", file=sys.stderr)
        return codigo_de(exc)
