"""F3.07: el estimador de uso de QPU y el tope que aborta ANTES de enviar. Puro: sin SDK, sin red."""

import pytest

from qrecauda.dominio.errores import EntradaInvalida, PresupuestoQpuExcedido
from qrecauda.dominio.presupuesto_qpu import (
    REP_DELAY_POR_OMISION_S,
    SOBRECARGA_POR_TRABAJO_S,
    estimar_segundos_qpu,
    exigir_presupuesto,
    validar_tope_qpu,
)


def test_la_estimacion_es_disparos_por_ciclo_mas_sobrecarga():
    e = estimar_segundos_qpu(shots_totales=100_000, circuitos=1, duracion_circuito_s=1.5e-6, rep_delay_s=250e-6)
    assert e.segundos == pytest.approx(100_000 * (250e-6 + 1.5e-6) + SOBRECARGA_POR_TRABAJO_S)
    assert e.shots_totales == 100_000 and e.circuitos == 1


def test_sin_dato_del_backend_se_usa_el_retardo_por_omision():
    a = estimar_segundos_qpu(1000, 1, 0.0, None)
    b = estimar_segundos_qpu(1000, 1, 0.0, REP_DELAY_POR_OMISION_S)
    assert a.segundos == b.segundos


def test_la_estimacion_nace_sin_verificar():
    assert "sin verificar" in estimar_segundos_qpu(10, 1, 0.0, None).nota


@pytest.mark.parametrize("shots,circuitos", [(0, 1), (10, 0), (-1, 1)])
def test_entradas_imposibles_abortan(shots, circuitos):
    with pytest.raises(EntradaInvalida):
        estimar_segundos_qpu(shots, circuitos, 0.0, None)


def test_el_tope_aborta_si_lo_estimado_lo_pasa():
    with pytest.raises(PresupuestoQpuExcedido, match="tope"):
        exigir_presupuesto(estimado_s=30.0, tope_s=20.0, restante_s=None, ya_gastado_s=0.0)


def test_el_tope_cuenta_lo_ya_gastado():
    exigir_presupuesto(estimado_s=10.0, tope_s=20.0, restante_s=None, ya_gastado_s=10.0)  # justo: 20 no pasa de 20
    with pytest.raises(PresupuestoQpuExcedido):
        exigir_presupuesto(estimado_s=10.1, tope_s=20.0, restante_s=None, ya_gastado_s=10.0)


def test_la_cuota_restante_del_servicio_tambien_aborta():
    with pytest.raises(PresupuestoQpuExcedido, match="cuota"):
        exigir_presupuesto(estimado_s=30.0, tope_s=None, restante_s=12.0, ya_gastado_s=0.0)


def test_sin_tope_ni_cuota_conocida_pasa_pero_no_aprueba_nada_mas():
    exigir_presupuesto(estimado_s=1e9, tope_s=None, restante_s=None, ya_gastado_s=0.0)


def test_un_tope_no_positivo_es_entrada_invalida():
    with pytest.raises(EntradaInvalida):
        exigir_presupuesto(estimado_s=1.0, tope_s=0.0, restante_s=None, ya_gastado_s=0.0)


@pytest.mark.parametrize("malo", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0, 1e12, 86_401.0])
def test_un_tope_que_no_es_finito_positivo_y_razonable_aborta_con_error_claro(malo: float) -> None:
    """R.02: `nan` hacía que `total > tope` fuese siempre falso (el aborto nunca saltaba); `inf` y 1e12 lo desactivaban."""
    with pytest.raises(EntradaInvalida, match="tope"):
        validar_tope_qpu(malo)
    with pytest.raises(EntradaInvalida, match="tope"):
        exigir_presupuesto(estimado_s=1.0, tope_s=malo, restante_s=None, ya_gastado_s=0.0)


def test_un_tope_valido_se_devuelve_igual() -> None:
    assert validar_tope_qpu(120) == 120.0 and validar_tope_qpu(86_400.0) == 86_400.0
