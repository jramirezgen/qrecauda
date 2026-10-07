"""Almacen — JSON canónico en disco, append-only y atómico (DAG F2.06). Lo que se escribe no se pisa."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path

from qrecauda.datos import serializar
from qrecauda.dominio.errores import EntradaInvalida


class AlmacenJson:
    """Implementa `Almacen`."""

    def __init__(self, raiz: Path) -> None:
        self._raiz = raiz

    def _ruta(self, nombre: str) -> Path:
        if not nombre or "/" in nombre or nombre.startswith("."):
            raise EntradaInvalida(f"nombre de artefacto inválido: {nombre!r}")
        return self._raiz / f"{nombre}.json"

    def guardar(self, nombre: str, artefacto: Mapping[str, object]) -> str:
        destino = self._ruta(nombre)
        if destino.exists():
            raise EntradaInvalida(f"{destino.name} ya existe: el registro es append-only")
        texto = serializar(artefacto)
        self._raiz.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(texto, encoding="utf-8")
        os.replace(tmp, destino)  # atómico: nadie ve un fichero a medias
        return hashlib.sha256(texto.encode()).hexdigest()

    def leer(self, nombre: str) -> dict[str, object]:
        datos = json.loads(self._ruta(nombre).read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            raise EntradaInvalida(f"{nombre}: se esperaba un objeto JSON")
        return datos
