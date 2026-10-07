"""La raíz de composición aplica lo transversal a cada semilla: previo, candado de máquina y BLAS a un hilo. Sin Aer: interior falso."""

from pathlib import Path

import pytest

from qrecauda import composicion
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.datos import Medicion
from qrecauda.dominio.errores import CandadoOcupado, CorridaInvalida
from qrecauda.transversal.concurrencia import candado
from qrecauda.transversal.reproducibilidad import hilos_blas

RAIZ = Path(__file__).resolve().parents[2]


class Interior:
    def __init__(self) -> None:
        self.hilos: list[dict[str, int]] = []

    def ejecutar(self, decl, semilla):
        self.hilos.append(hilos_blas())
        return Medicion()


def test_ejecuta_con_blas_a_un_hilo_y_el_candado_tomado(tmp_path):
    d = cargar_declaracion(Path("declaraciones/E2.toml"), RAIZ)
    interior = Interior()
    ruta = tmp_path / "c.lock"
    envoltura = composicion._EnMaquina(interior, ruta, lambda decl: None, 0.0)
    envoltura.ejecutar(d, 1)
    assert interior.hilos and all(n == 1 for n in interior.hilos[0].values())
    with candado(ruta, 0.0):  # soltado tras la semilla: se puede volver a tomar
        pass


def test_con_el_candado_ocupado_no_mide_nada(tmp_path):
    d = cargar_declaracion(Path("declaraciones/E2.toml"), RAIZ)
    interior, ruta = Interior(), tmp_path / "c.lock"
    with candado(ruta), pytest.raises(CandadoOcupado):
        composicion._EnMaquina(interior, ruta, lambda decl: None, 0.0).ejecutar(d, 1)
    assert interior.hilos == []


def test_la_comprobacion_previa_corta_antes_de_tomar_el_candado(tmp_path):
    d = cargar_declaracion(Path("declaraciones/E2.toml"), RAIZ)

    def previo(decl):
        raise CorridaInvalida("no")

    interior = Interior()
    with pytest.raises(CorridaInvalida):
        composicion._EnMaquina(interior, tmp_path / "c.lock", previo, 0.0).ejecutar(d, 1)
    assert interior.hilos == [] and not (tmp_path / "c.lock").exists()
