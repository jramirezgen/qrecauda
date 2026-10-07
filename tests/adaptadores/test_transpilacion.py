"""F3.03: transpilación a forma ISA con caída local registrada."""

from __future__ import annotations

import logging

import pytest
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from qrecauda.adaptadores.aer import FuenteAer
from qrecauda.adaptadores.aer.transpilacion import Transpilado, a_isa
from qrecauda.dominio.errores import EntradaInvalida


def _hadamard(n: int) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    qc.h(range(n))
    qc.measure_all()
    return qc


def test_via_local_registrada(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="qrecauda.adaptadores.aer.transpilacion"):
        t = a_isa(_hadamard(3))
    assert isinstance(t, Transpilado)
    assert t.via == "local"
    assert t.motivo  # dice por qué no se usó el servicio de IA
    assert any("local" in r.getMessage() for r in caplog.records)


def test_salida_en_forma_isa_sobre_el_backend() -> None:
    be = AerSimulator()
    t = a_isa(_hadamard(3), backend=be)
    permitidas = set(be.operation_names) | {"measure", "barrier"}
    assert {i.operation.name for i in t.circuito.data} <= permitidas


def test_base_restringida_descompone_h() -> None:
    t = a_isa(_hadamard(2), puertas_base=("rz", "sx", "cx", "measure"))
    nombres = {i.operation.name for i in t.circuito.data}
    assert "h" not in nombres
    assert nombres <= {"rz", "sx", "cx", "measure", "barrier"}


def test_transpilado_sigue_siendo_hadamard_al_muestrear() -> None:
    t = a_isa(_hadamard(2), puertas_base=("rz", "sx", "cx", "measure"))
    bits = FuenteAer(semilla=3)._muestrear(t.circuito, 4000)
    assert abs(bits.mean() - 0.5) < 0.05


def test_circuito_invalido() -> None:
    with pytest.raises(EntradaInvalida):
        a_isa(QuantumCircuit(0))
