"""Fachada pública y estable. La CLI es un cliente más de ella; tests/arquitectura/test_api.py congela sus firmas."""

from __future__ import annotations

from pathlib import Path

from qrecauda import composicion
from qrecauda.aplicacion.pipeline import Resultado
from qrecauda.datos import ManifiestoDeCorrida, VeredictoDeEureka
from qrecauda.transversal.configuracion import Configuracion

__all__ = ["Configuracion", "ManifiestoDeCorrida", "Resultado", "VeredictoDeEureka", "correr", "generar_clave", "juzgar"]


def generar_clave(cfg: Configuracion) -> Resultado:
    return composicion.ejecutar(cfg)


def correr(declaracion: Path, raiz: Path) -> ManifiestoDeCorrida:
    """F2.07: corre cada semilla de `declaracion` (relativa a `raiz`, la raíz del repo) y escribe `registro/corridas/<id>.json`."""
    return composicion.correr_declaracion(declaracion, raiz)


def juzgar(eureka: str, raiz: Path) -> VeredictoDeEureka:
    """F2.07: aplica el criterio de `declaraciones/<eureka>.toml` a la corrida ya hecha y añade una línea a `registro/veredictos.jsonl`."""
    return composicion.juzgar_eureka(eureka, raiz)
