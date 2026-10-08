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


# ------------------------------------------------------------------ F3.07: cableado opcional del servicio de IA


class _PmDoble:
    """Doble de un pass manager de IA: no toca el circuito pero deja constancia de que se usó."""

    def __init__(self) -> None:
        self.llamado = False

    def run(self, circuito: QuantumCircuit) -> QuantumCircuit:
        self.llamado = True
        return circuito


def test_sin_pedir_ia_la_via_es_local_y_no_avisa(recwarn: pytest.WarningsRecorder) -> None:
    t = a_isa(_hadamard(3))
    assert t.via == "local" and not [w for w in recwarn if "IA" in str(w.message)]


def test_con_el_flag_y_una_fabrica_la_via_es_ia() -> None:
    pm = _PmDoble()
    pedidos: list[int] = []

    def fabrica(backend: object, nivel: int) -> _PmDoble:
        pedidos.append(nivel)
        return pm

    t = a_isa(_hadamard(3), AerSimulator(), ia=True, fabrica_ia=fabrica, nivel_optimizacion=2)
    assert t.via == "ia" and pm.llamado and pedidos == [2]
    assert "IA" in t.motivo


def test_con_el_flag_y_sin_el_paquete_degrada_con_aviso_nunca_en_silencio(caplog: pytest.LogCaptureFixture) -> None:
    with (
        caplog.at_level(logging.WARNING, logger="qrecauda.adaptadores.aer.transpilacion"),
        pytest.warns(UserWarning, match="qiskit_ibm_transpiler"),
    ):
        t = a_isa(_hadamard(3), AerSimulator(), ia=True)
    assert t.via == "local"
    assert "degrad" in t.motivo and "qiskit_ibm_transpiler" in t.motivo
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_si_el_servicio_de_ia_falla_degrada_con_aviso() -> None:
    def fabrica(backend: object, nivel: int) -> _PmDoble:
        raise OSError("sin red")

    with pytest.warns(UserWarning, match="sin red"):
        t = a_isa(_hadamard(3), AerSimulator(), ia=True, fabrica_ia=fabrica)
    assert t.via == "local" and "degrad" in t.motivo


def test_el_transpilado_informa_profundidad_y_puertas_de_dos_qubits() -> None:
    t = a_isa(_hadamard(3), AerSimulator())
    assert t.profundidad == t.circuito.depth() and t.puertas_dos_qubits == 0
