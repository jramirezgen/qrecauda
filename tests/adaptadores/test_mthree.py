"""F4.01: twirling de lectura propio como `Mitigador` (D-009); mthree sólo como contraste. Sin red ni credenciales."""

from __future__ import annotations

import numpy as np
import pytest

from qrecauda.adaptadores.aer import FuenteAer
from qrecauda.adaptadores.aer.ruido import RUIDO_ALTO, RUIDO_MEDIO, CanalLectura, modelo_de_ruido
from qrecauda.adaptadores.mthree import TwirlingLectura, sesgo_mthree
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Muestra, Origen, Procedencia
from qrecauda.puertos import Mitigador

QUBITS, SHOTS = 4, 50_000  # 200 000 bits: error estándar de p1 ≈ 0.0011


def _sesgo(m: Muestra) -> float:
    return abs(m.bits.proporcion_de_unos() - 0.5)


def _cruda(canal: CanalLectura = RUIDO_MEDIO, semilla: int = 5) -> Muestra:
    return FuenteAer(semilla=semilla, noise_model=modelo_de_ruido(canal)).generar(QUBITS, SHOTS)


def test_implementa_el_puerto_y_marca_mitigada() -> None:
    mit: Mitigador = TwirlingLectura(modelo_de_ruido(RUIDO_MEDIO), semilla=1)
    cruda = _cruda()
    out = mit.mitigar(cruda)
    assert out.mitigada and not cruda.mitigada
    assert (out.qubits, out.shots, len(out.bits)) == (QUBITS, SHOTS, QUBITS * SHOTS)  # conserva los bits por disparo


def test_baja_el_sesgo_de_lectura_conocido() -> None:
    cruda = _cruda()
    assert _sesgo(cruda) > 0.025  # canal medio: sesgo analítico 0.03 (F3.02)
    out = TwirlingLectura(modelo_de_ruido(RUIDO_MEDIO), semilla=1).mitigar(cruda)
    assert _sesgo(out) < 0.006  # ≈5 errores estándar: ruido estadístico, no sesgo


def test_baja_el_sesgo_con_ruido_alto() -> None:
    cruda = _cruda(RUIDO_ALTO)
    out = TwirlingLectura(modelo_de_ruido(RUIDO_ALTO), semilla=2).mitigar(cruda)
    assert _sesgo(cruda) > 0.04
    assert _sesgo(out) < 0.006


def test_no_degrada_el_origen_porque_no_remuestrea() -> None:
    out = TwirlingLectura(modelo_de_ruido(RUIDO_MEDIO), semilla=1).mitigar(_cruda())
    assert out.origen is Origen.SIMULADOR_AER
    assert out.procedencia.backend == "AerSimulator"
    assert not out.reclama_origen_cuantico


def test_determinista_por_semilla() -> None:
    cruda = _cruda()
    nm = modelo_de_ruido(RUIDO_MEDIO)
    a = TwirlingLectura(nm, semilla=9).mitigar(cruda).bits
    assert a == TwirlingLectura(nm, semilla=9).mitigar(cruda).bits
    assert a != TwirlingLectura(nm, semilla=10).mitigar(cruda).bits


def test_shots_que_no_son_multiplo_del_bloque() -> None:
    cruda = FuenteAer(semilla=3, noise_model=modelo_de_ruido(RUIDO_MEDIO)).generar(3, 457)
    out = TwirlingLectura(modelo_de_ruido(RUIDO_MEDIO), semilla=1, bloque=100).mitigar(cruda)
    assert (len(out.bits), out.shots) == (3 * 457, 457)


def test_sin_ruido_no_inventa_sesgo() -> None:
    cruda = FuenteAer(semilla=3).generar(QUBITS, SHOTS)
    out = TwirlingLectura(None, semilla=1).mitigar(cruda)
    assert _sesgo(out) < 0.006


def test_orden_qubit_mayor_se_conserva() -> None:
    """X sólo en el qubit 1 (no hay H): la máscara se deshace por XOR, así que el bloque del qubit 1 sigue siendo todo unos."""
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(3)
    qc.x(1)
    qc.measure_all()
    bits = TwirlingLectura(None, semilla=0, bloque=7)._muestrear(qc, 20)
    esperado = np.concatenate([np.zeros(20), np.ones(20), np.zeros(20)]).astype(np.uint8)
    assert np.array_equal(bits, esperado)


def test_rechaza_lo_que_no_puede_remedir() -> None:
    mit = TwirlingLectura(None, semilla=1)
    ya = Muestra(Bits.desde([0, 1] * 8), Origen.SIMULADOR_AER, 1, 16, mitigada=True)
    with pytest.raises(EntradaInvalida, match="mitigada"):
        mit.mitigar(ya)
    hw = Muestra(Bits.desde([0, 1] * 8), Origen.HARDWARE_IBM, 1, 16, procedencia=Procedencia(backend="ibm_x", job_id="j1"))
    with pytest.raises(EntradaInvalida, match="re-ejecutar"):
        mit.mitigar(hw)


def test_parametros_invalidos() -> None:
    with pytest.raises(EntradaInvalida):
        TwirlingLectura(None, semilla=1, bloque=0)


def test_mthree_de_contraste_tambien_baja_el_sesgo() -> None:
    pytest.importorskip("mthree")
    antes, despues = sesgo_mthree(modelo_de_ruido(RUIDO_MEDIO), qubits=4, shots=20_000, semilla=11)
    assert antes > 0.025
    assert despues < 0.01


def test_twirling_pasa_max_parallel_threads_al_simulador() -> None:
    from qrecauda.adaptadores.mthree import TwirlingLectura

    assert TwirlingLectura(None, 1, max_parallel_threads=1)._simulador().options.max_parallel_threads == 1


def test_twirling_con_un_hilo_da_los_mismos_bits() -> None:
    from qrecauda.adaptadores.aer import FuenteAer
    from qrecauda.adaptadores.mthree import TwirlingLectura

    m = FuenteAer(semilla=3).generar(2, 400)
    assert TwirlingLectura(None, 5).mitigar(m).bits == TwirlingLectura(None, 5, max_parallel_threads=1).mitigar(m).bits
