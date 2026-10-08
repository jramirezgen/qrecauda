"""Los criterios puros de E4 (docs/preinscripciones/E4.md) y la configuración del modo de IBM."""

from __future__ import annotations

import numpy as np
import pytest

from qrecauda.aplicacion.criterios_e4 import sesgo_medio_por_qubit, sesgos_por_qubit
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia
from qrecauda.transversal.configuracion import MODOS_IBM, Configuracion


def _muestra(filas: list[list[int]]) -> Muestra:
    d = np.array(filas, dtype=np.uint8)
    return Muestra(
        bits=Bits(np.ascontiguousarray(d).reshape(-1)),
        origen=Origen.PRNG_CLASICO,
        qubits=d.shape[0],
        shots=d.shape[1],
        procedencia=Procedencia("t", "", ""),
    )


def test_el_sesgo_por_qubit_lleva_signo_y_sigue_el_orden_qubit_mayor():
    s = sesgos_por_qubit(_muestra([[1, 1, 1, 0], [0, 0, 0, 1], [1, 0, 1, 0]]))
    assert s == pytest.approx([0.25, -0.25, 0.0])
    assert sesgo_medio_por_qubit(s) == pytest.approx(0.5 / 3)


def test_una_muestra_con_bits_de_mas_o_sin_qubits_no_se_compara():
    m = _muestra([[1, 0], [0, 1]])
    object.__setattr__(m, "shots", 5)  # frozen: se fuerza la incoherencia que el constructor ya no permitiría
    with pytest.raises(EntradaInvalida):
        sesgos_por_qubit(m)
    with pytest.raises(EntradaInvalida):
        sesgo_medio_por_qubit([])


def test_el_modo_trabajo_es_valido_y_uno_desconocido_no():
    assert "trabajo" in MODOS_IBM
    Configuracion(ibm_modo="trabajo")
    with pytest.raises(EntradaInvalida):
        Configuracion(ibm_modo="otro")
