"""Presupuesto de QPU: cuánto tiempo de máquina cuesta un envío y cuándo se aborta antes de enviarlo (DAG F3.07).

El plan abierto de IBM Quantum da una cuota mensual pequeña de tiempo de QPU. ⚠️ sin verificar la cuota vigente: se lee del
servicio (`QiskitRuntimeService.usage()`) cuando lo expone, y nunca se supone. La estimación es un modelo grueso del cargo
(`disparos × (retardo de repetición + duración del circuito) + sobrecarga por trabajo`); ⚠️ sin verificar contra el cargo real
de IBM: tras cada trabajo real el registro guarda el uso medido junto a lo estimado para poder calibrar este modelo.
Puro: sin SDK ni red.
"""

from __future__ import annotations

from dataclasses import dataclass

from qrecauda.dominio.errores import EntradaInvalida, PresupuestoQpuExcedido

REP_DELAY_POR_OMISION_S = (
    250e-6  # el `default_rep_delay` de los backends actuales de IBM (leído de FakeSherbrooke); ⚠️ sin verificar en real
)
SOBRECARGA_POR_TRABAJO_S = 3.0  # ⚠️ sin verificar: margen fijo por trabajo (carga, calibración de arranque); deliberadamente conservador
TOPE_POR_OMISION_S = 60.0  # lo que se permite gastar si el usuario no dice otra cosa: un minuto de QPU


@dataclass(frozen=True, slots=True)
class EstimacionQpu:
    segundos: float
    shots_totales: int
    circuitos: int
    por_disparo_s: float
    sobrecarga_s: float
    nota: str = "⚠️ sin verificar contra el cargo real de IBM"


def estimar_segundos_qpu(
    shots_totales: int,
    circuitos: int,
    duracion_circuito_s: float,
    rep_delay_s: float | None,
    sobrecarga_s: float = SOBRECARGA_POR_TRABAJO_S,
) -> EstimacionQpu:
    """`shots_totales` suma los disparos de TODOS los circuitos del trabajo; `circuitos` es cuántos PUBs lleva."""
    if shots_totales < 1 or circuitos < 1:
        raise EntradaInvalida(f"shots y circuitos deben ser positivos, llegó {shots_totales}, {circuitos}")
    por_disparo = (REP_DELAY_POR_OMISION_S if rep_delay_s is None else rep_delay_s) + max(duracion_circuito_s, 0.0)
    return EstimacionQpu(shots_totales * por_disparo + sobrecarga_s, shots_totales, circuitos, por_disparo, sobrecarga_s)


def exigir_presupuesto(*, estimado_s: float, tope_s: float | None, restante_s: float | None, ya_gastado_s: float) -> None:
    """Aborta con `PresupuestoQpuExcedido` si lo ya gastado más lo estimado pasa el tope o lo que queda de cuota. No gasta nada."""
    if tope_s is not None and tope_s <= 0:
        raise EntradaInvalida(f"el tope de segundos de QPU debe ser positivo, llegó {tope_s}")
    total = ya_gastado_s + estimado_s
    if tope_s is not None and total > tope_s:
        raise PresupuestoQpuExcedido(
            f"el envío costaría ≈ {estimado_s:.1f} s de QPU (ya gastados {ya_gastado_s:.1f} s): "
            f"{total:.1f} s pasa el tope de {tope_s:.1f} s; "
            f"no se envía nada (sube --max-segundos-qpu o baja los shots)"
        )
    if restante_s is not None and estimado_s > restante_s:
        raise PresupuestoQpuExcedido(
            f"el envío costaría ≈ {estimado_s:.1f} s de QPU y al servicio le quedan {restante_s:.1f} s de cuota: no se envía nada"
        )
