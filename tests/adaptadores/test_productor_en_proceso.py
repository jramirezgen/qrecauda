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
    p.iniciar()
    try:
        with pytest.raises(EntradaInvalida):
            p.iniciar()
    finally:
        p.detener()


# ------------------------------------------------------------------ R.02: huérfanos, errores raros y detener() idempotente


def test_detener_sin_haber_iniciado_no_levanta_ni_tapa_el_error_real():
    informe = _productor().detener()
    assert informe.claves == () and not informe.forzado
    try:
        try:
            raise ValueError("el error real")
        finally:
            _productor().detener()  # como en ejecutor_e3b: en un `finally`
    except ValueError as e:
        assert str(e) == "el error real"


def test_cualquier_excepcion_del_hijo_llega_con_tipo_y_mensaje():
    p = _productor(falla_en=0, falla_rara=True)
    p.iniciar()
    try:
        with pytest.raises(CorridaInvalida, match="KeyError.*clave-que-no-esta"):
            p.tomar(30.0)
    finally:
        p.detener()


def test_el_hijo_se_va_si_el_padre_muere(tmp_path):
    import signal
    import subprocess
    import sys

    guion = tmp_path / "padre.py"
    guion.write_text(
        "import functools, sys, time\n"
        f"sys.path.insert(0, {os.path.dirname(__file__)!r})\n"
        "from generadores_de_prueba import fabrica\n"
        "from qrecauda.adaptadores.productor_en_proceso import ProductorEnProceso\n"
        "if __name__ == '__main__':\n"
        "    p = ProductorEnProceso(functools.partial(fabrica, pausa_s=0.01), 2)\n"
        "    p.iniciar()\n"
        "    print(p._proceso.pid, flush=True)\n"
        "    time.sleep(120)\n"
    )
    padre = subprocess.Popen([sys.executable, str(guion)], stdout=subprocess.PIPE, text=True)
    try:
        assert padre.stdout is not None
        hijo = int(padre.stdout.readline())
        os.kill(hijo, 0)  # vive
        padre.send_signal(signal.SIGKILL)  # sin posibilidad de limpiar nada
        padre.wait(10)
        limite = time.monotonic() + 20
        vivo = True
        while vivo and time.monotonic() < limite:
            try:
                os.kill(hijo, 0)
                time.sleep(0.2)
            except ProcessLookupError:
                vivo = False
        assert not vivo, "el hijo huérfano sigue produciendo claves"
    finally:
        padre.kill()
