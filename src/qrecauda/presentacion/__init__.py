"""Presentación: formatea resultados (JSON canónico, tabla de texto, Markdown) y NO orquesta nada."""

from __future__ import annotations

from qrecauda.dominio.metricas import Veredicto


def tabla(veredicto: Veredicto) -> str:
    filas = [f"{'métrica':<18}{'valor':>14}{'umbral':>12}  cumple"]
    filas += [f"{m.metrica.value:<18}{m.valor:>14.6g}{m.umbral:>12.6g}  {'sí' if m.cumple else 'NO'}" for m in veredicto.medidas]
    filas.append(f"VEREDICTO: {'APROBADO' if veredicto.aprobado else 'RECHAZADO ' + ', '.join(m.value for m in veredicto.fallos())}")
    return "\n".join(filas)
