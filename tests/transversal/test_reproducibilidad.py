import numpy  # noqa: F401  (carga la BLAS que se va a limitar)
import pytest
from threadpoolctl import threadpool_info

from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.transversal.reproducibilidad import entorno, hilos_blas, un_hilo, verificar_un_hilo


def test_un_hilo_fuerza_y_restaura():
    antes = hilos_blas()
    with un_hilo():
        assert all(n == 1 for n in hilos_blas().values())
        verificar_un_hilo()
    assert hilos_blas() == antes


def test_verificar_un_hilo_falla_si_no_se_forzo():
    from threadpoolctl import threadpool_limits

    with threadpool_limits(limits=2):
        if not threadpool_info() or all(i["num_threads"] < 2 for i in threadpool_info()):
            pytest.skip("sin biblioteca BLAS con más de un hilo disponible")
        with pytest.raises(EntradaInvalida, match="hilo"):
            verificar_un_hilo()


def test_entorno_captura_versiones_y_marca_lo_ausente():
    e = entorno(("numpy", "paquete-que-no-existe-xyz"))
    assert e["numpy"][0].isdigit()
    assert e["paquete-que-no-existe-xyz"] == "no instalado"
    assert {"python", "plataforma"} <= set(e)
