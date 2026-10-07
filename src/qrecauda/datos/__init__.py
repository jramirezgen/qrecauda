"""Datos: esquemas versionados y serialización canónica de los artefactos (manifiesto, informe de métricas).

Regla: todo artefacto lleva `esquema` = (nombre, versión). Un lector viejo rechaza un esquema futuro.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from qrecauda.datos.esquema import leer_esquema
from qrecauda.datos.informe import ESQUEMA_INFORME, ExperimentoE2, ExperimentoE3, InformeCorrida
from qrecauda.dominio.errores import EntradaInvalida

__all__ = ["ESQUEMA_INFORME", "ExperimentoE2", "ExperimentoE3", "InformeCorrida", "leer_esquema", "leer_informe", "serializar"]


def serializar(artefacto: Mapping[str, object]) -> str:
    """JSON canónico: claves ordenadas, sin espacios sobrantes, UTF-8. Mismo contenido ⇒ mismos bytes."""
    return json.dumps(artefacto, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def leer_informe(texto: str) -> dict[str, object]:
    datos = json.loads(texto)
    if not isinstance(datos, dict):
        raise EntradaInvalida("el informe no es un objeto JSON")
    leer_esquema(datos, ESQUEMA_INFORME, que="informe")
    return dict(datos)
