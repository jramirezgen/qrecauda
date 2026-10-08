"""Fijar un proceso a un núcleo: sólo a uno permitido, y se restaura al salir."""

import os

import pytest

from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.transversal.reproducibilidad import afinidad, fijar_afinidad, nucleo_fijo


def test_nucleo_fijo_fija_y_restaura():
    previa = afinidad()
    with nucleo_fijo(previa[0]) as efectiva:
        assert efectiva == (previa[0],) == afinidad()
    assert afinidad() == previa


def test_un_nucleo_no_permitido_falla_sin_fijar_otro():
    previa = afinidad()
    with pytest.raises(EntradaInvalida, match="no está entre los permitidos"):
        fijar_afinidad(10_000)
    assert afinidad() == previa


def test_un_hijo_valida_contra_los_permitidos_declarados_no_contra_su_fijacion_heredada():
    previa = afinidad()
    try:
        with nucleo_fijo(previa[0]):
            if len(previa) > 1:
                assert fijar_afinidad(previa[-1], previa) == (previa[-1],)
            with pytest.raises(EntradaInvalida):
                fijar_afinidad(10_000, previa)
    finally:
        os.sched_setaffinity(0, previa)
