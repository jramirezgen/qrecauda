"""Presentación: formatea resultados (JSON canónico, tabla de texto) y NO orquesta nada."""

from __future__ import annotations

from qrecauda.datos import ManifiestoDeCorrida, VeredictoDeEureka, serializar
from qrecauda.dominio.metricas import Veredicto

__all__ = ["json_canonico", "json_de", "resumen_de_corrida", "tabla", "tabla_de_eureka"]


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


def json_de(artefacto: ManifiestoDeCorrida | VeredictoDeEureka) -> str:
    """Manifiesto o veredicto de eureka como JSON canónico (lo mismo que se escribe en el registro)."""
    return serializar(artefacto.a_mapa())


def resumen_de_corrida(m: ManifiestoDeCorrida) -> str:
    controles = ", ".join(f"{k}={'ok' if ok else 'FALLA'}" for k, ok in sorted(m.controles.items())) or "ninguno"
    return "\n".join(
        (
            f"CORRIDA {m.corrida} ({m.eureka}): {len(m.artefactos)} artefactos en registro/corridas/",
            f"preinscripción {m.preinscripcion_sha[:8]}  corrida {m.commit[:8]}  controles: {controles}",
        )
    )


def tabla_de_eureka(v: VeredictoDeEureka) -> str:
    filas = [f"{'criterio':<22}  cumple  detalle"]
    filas += [f"{c.id:<22}  {'sí' if c.cumple else 'NO':<6}  {c.detalle}{'' if c.decide else '  (no decide)'}" for c in v.criterios]
    filas.append(f"VEREDICTO {v.eureka} sobre {v.corrida}: {v.desenlace}. {v.resumen}")
    return "\n".join(filas)
