"""Fachada pública y estable. La CLI es un cliente más de ella; tests/arquitectura/test_api.py congela sus firmas."""

from __future__ import annotations

from qrecauda import composicion
from qrecauda.aplicacion.pipeline import Resultado
from qrecauda.transversal.configuracion import Configuracion

__all__ = ["Configuracion", "Resultado", "generar_clave"]


def generar_clave(cfg: Configuracion) -> Resultado:
    return composicion.ejecutar(cfg)
