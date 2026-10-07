"""F3.01: FuenteAer sobre AerSimulator con SamplerV2. Sin red ni credenciales."""

from __future__ import annotations

import numpy as np
import pytest
import qiskit_aer

from qrecauda.adaptadores.aer import FuenteAer
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Origen
from qrecauda.puertos import FuenteDeBits


def test_implementa_el_puerto_y_declara_origen_simulado() -> None:
    fuente: FuenteDeBits = FuenteAer(semilla=1)
    m = fuente.generar(3, 64)
    assert m.origen is Origen.SIMULADOR_AER
    assert not m.reclama_origen_cuantico
    assert (m.qubits, m.shots, len(m.bits)) == (3, 64, 192)
    assert m.procedencia.backend == "AerSimulator"
    assert m.procedencia.version == qiskit_aer.__version__
    assert m.procedencia.job_id == ""


def test_misma_semilla_mismos_bits_y_semillas_distintas_difieren() -> None:
    a = FuenteAer(semilla=42).generar(4, 256).bits
    assert a == FuenteAer(semilla=42).generar(4, 256).bits
    assert a != FuenteAer(semilla=43).generar(4, 256).bits


def test_orden_qubit_mayor() -> None:
    """Fija el orden con un circuito determinista: X sólo en el qubit 1 de 3. Qubit-mayor ⇒ el bloque del qubit 1 son todo
    unos y los demás ceros. Si el orden fuera disparo-mayor, los unos quedarían intercalados."""
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(3)
    qc.x(1)
    qc.measure_all()
    shots = 5
    bits = FuenteAer(semilla=0)._muestrear(qc, shots)
    esperado = np.concatenate([np.zeros(shots), np.ones(shots), np.zeros(shots)]).astype(np.uint8)
    assert np.array_equal(bits, esperado)


def test_h_da_aproximadamente_uniforme() -> None:
    m = FuenteAer(semilla=7).generar(4, 5000)
    assert abs(m.bits.proporcion_de_unos() - 0.5) < 0.01


@pytest.mark.parametrize(("q", "s"), [(0, 10), (2, 0), (-1, 5)])
def test_entradas_invalidas(q: int, s: int) -> None:
    with pytest.raises(EntradaInvalida):
        FuenteAer(semilla=1).generar(q, s)


def test_max_parallel_threads_llega_a_las_opciones_de_aer_y_no_cambia_los_bits() -> None:
    """P.E3 / T4: `max_parallel_threads=1` es parte de «un hilo». Sin pedirlo no se añade ninguna opción (comportamiento previo)."""
    assert FuenteAer(semilla=1)._opciones_backend() is None
    assert FuenteAer(semilla=1, max_parallel_threads=1)._opciones_backend() == {"backend_options": {"max_parallel_threads": 1}}
    assert FuenteAer(semilla=1, noise_model=None, max_parallel_threads=1).generar(3, 128).bits == FuenteAer(semilla=1).generar(3, 128).bits


def test_hilos_invalidos_se_rechazan() -> None:
    with pytest.raises(EntradaInvalida):
        FuenteAer(semilla=1, max_parallel_threads=0)
