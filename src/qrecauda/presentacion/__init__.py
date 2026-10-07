"""Presentación: formatea resultados (JSON canónico, tabla de texto) y NO orquesta nada."""

from __future__ import annotations

from qrecauda.datos import serializar
from qrecauda.dominio.metricas import Veredicto

__all__ = ["json_canonico", "tabla"]


def tabla(veredicto: Veredicto) -> str:
    filas = [f"{'métrica':<18}{'valor':>14}{'umbral':>12}  cumple"]
    filas += [f"{m.metrica.value:<18}{m.valor:>14.6g}{m.umbral:>12.6g}  {'sí' if m.cumple else 'NO'}" for m in veredicto.medidas]
    filas.append(f"VEREDICTO: {'APROBADO' if veredicto.aprobado else 'RECHAZADO ' + ', '.join(m.value for m in veredicto.fallos())}")
    return "\n".join(filas)


def json_canonico(veredicto: Veredicto) -> str:
    """El veredicto como JSON canónico (mismo contenido ⇒ mismos bytes; la serialización es la de `datos`)."""
    return serializar(
        {
            "aprobado": veredicto.aprobado,
            "fallos": [m.value for m in veredicto.fallos()],
            "medidas": [{"metrica": m.metrica.value, "valor": m.valor, "umbral": m.umbral, "cumple": m.cumple} for m in veredicto.medidas],
        }
    )
