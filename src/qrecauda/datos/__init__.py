"""Datos: esquemas versionados y serialización canónica de los artefactos (manifiesto, informe de métricas).

Regla: todo artefacto lleva `esquema` = (nombre, versión). Un lector viejo rechaza un esquema futuro.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from qrecauda.datos.informe import ESQUEMA_INFORME, InformeCorrida
from qrecauda.dominio.errores import EntradaInvalida, EsquemaFuturo

__all__ = ["ESQUEMA_INFORME", "InformeCorrida", "leer_informe", "serializar"]


def serializar(artefacto: Mapping[str, object]) -> str:
    """JSON canónico: claves ordenadas, sin espacios sobrantes, UTF-8. Mismo contenido ⇒ mismos bytes."""
    return json.dumps(artefacto, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def leer_informe(texto: str) -> dict[str, object]:
    datos = json.loads(texto)
    if not isinstance(datos, dict) or "esquema" not in datos:
        raise EntradaInvalida("el informe no declara `esquema`")
    if int(datos["esquema"]) > ESQUEMA_INFORME:
        raise EsquemaFuturo(f"esquema {datos['esquema']} > {ESQUEMA_INFORME}: actualiza qrecauda")
    return dict(datos)
