"""Fachada pública y estable. La CLI es un cliente más de ella; tests/arquitectura/test_api.py congela sus firmas."""

from __future__ import annotations

from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado, ejecutar
from qrecauda.composicion import fuente_de, validador_de
from qrecauda.transversal.configuracion import Configuracion
from qrecauda.transversal.observabilidad import RelojMonotonico

__all__ = ["Configuracion", "Resultado", "generar_clave"]


def generar_clave(cfg: Configuracion) -> Resultado:
    p = ParametrosPipeline(cfg.qubits, cfg.shots, epsilon=2.0**-cfg.epsilon_exp)
    return ejecutar(fuente_de(cfg), validador_de(cfg), RelojMonotonico(), p)
