"""Seguridad: los secretos entran por RUTA, nunca por valor, y no se imprimen ni truncados."""

from __future__ import annotations

from pathlib import Path

from qrecauda.dominio.errores import EntradaInvalida


def leer_secreto(ruta: Path) -> str:
    if not ruta.is_file():
        raise EntradaInvalida(f"no hay fichero de secreto en {ruta}")
    valor = ruta.read_text().strip()
    if not valor:
        raise EntradaInvalida(f"{ruta} está vacío")
    return valor


def describir(secreto: str) -> str:
    """Lo único que se puede mostrar de un secreto: que existe y cuánto mide."""
    return f"<secreto de {len(secreto)} caracteres>"
