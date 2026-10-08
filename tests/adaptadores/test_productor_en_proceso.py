"""ProductorEnProceso con un proceso `spawn` REAL y un generador trivial: orden, contrapresión, errores del hijo y parada."""

from __future__ import annotations

import functools
import os
import time

import numpy as np
import pytest
from generadores_de_prueba import fabrica

from qrecauda.adaptadores.productor_en_proceso import ProductorEnProceso
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida


def _productor(capacidad=2, **kw):
    espera = kw.pop("espera_de_parada_s", 20.0)
    return ProductorEnProceso(functools.partial(fabrica, **kw), capacidad, espera)


def test_entrega_las_claves_en_orden_y_el_informe_las_cuenta():
    p = _productor(pausa_s=0.01)
    p.iniciar()
    try:
        claves = [p.tomar(30.0) for _ in range(4)]
    finally:
        informe = p.detener()
    assert [c.meta.indice for c in claves if c] == [0, 1, 2, 3]
    assert np.array_equal(claves[0].clave.datos, np.unpackbits(np.packbits(claves[0].clave.datos))[:704])
    assert len(claves[0].clave) == 704 and claves[0].rotulo == "validación del pipeline" and claves[0].origen == "simulador_aer"
    assert len(informe.claves) >= 4 and informe.pared_ns > 0 and informe.cpu_ns > 0 and not informe.forzado
    assert informe.nucleos == tuple(sorted(os.sched_getaffinity(0)))


def test_la_cola_es_acotada_y_el_bloqueo_se_mide_aparte():
    p = _productor(capacidad=1, pausa_s=0.0)
    p.iniciar()
    try:
        time.sleep(3.0)  # el hijo arranca (spawn), llena la cola y se bloquea
        assert p.listas() <= 1
        primera = p.tomar(10.0)
        assert primera is not None and primera.meta.indice == 0
    finally:
        informe = p.detener()
    assert len(informe.claves) <= 4  # con cola de 1 no puede haber producido muchas más: contrapresión real
    assert any(m.bloqueado_ns > 0 for m in informe.claves)


def test_tomar_sin_esperar_devuelve_none_si_no_hay_nada():
    p = _productor(pausa_s=30.0, espera_de_parada_s=0.5)
    p.iniciar()
    try:
        assert p.tomar(0.0) is None
        time.sleep(3.0)  # que el hijo arranque y entre en generar() antes de pedirle parar
    finally:
        informe = p.detener()
    assert informe.forzado  # dormía 30 s dentro de generar(): hubo que matarlo, y el informe lo dice


def test_un_fallo_del_hijo_llega_al_consumidor_como_corrida_invalida():
    p = _productor(falla_en=0)
    p.iniciar()
    try:
        with pytest.raises(CorridaInvalida, match="falla de prueba"):
            p.tomar(30.0)
    finally:
        p.detener()


def test_el_hijo_se_fija_a_su_nucleo():
    nucleo = sorted(os.sched_getaffinity(0))[-1]
    p = _productor(nucleo=nucleo)
    p.iniciar()
    try:
        assert p.tomar(30.0) is not None
    finally:
        informe = p.detener()
    assert informe.nucleos == (nucleo,)


def test_usos_incorrectos():
    with pytest.raises(EntradaInvalida):
        ProductorEnProceso(fabrica, 0)
    p = _productor()
    with pytest.raises(EntradaInvalida):
        p.tomar(0.0)
    with pytest.raises(EntradaInvalida):
        p.detener()
    p.iniciar()
    try:
        with pytest.raises(EntradaInvalida):
            p.iniciar()
    finally:
        p.detener()
