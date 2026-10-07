"""Transpilación a forma ISA: AIRouting / StagedPassManager de qiskit-ibm-transpiler con caída a un pass manager local
(DAG F3.03). Es un paso del adaptador de fuente, no un puerto propio: el núcleo no sabe qué es un circuito.

El servicio de IA (`qiskit_ibm_transpiler`) NO está instalado y exige red y credenciales: por ahora la vía es siempre
la local y se registra (`Transpilado.via`, log). ⚠️ sin verificar: el comportamiento del servicio de IA.
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator

from qrecauda.dominio.errores import EntradaInvalida

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Transpilado:
    circuito: QuantumCircuit
    via: str  # "local" (pass manager de qiskit); "ia" quedaría para qiskit_ibm_transpiler cuando se cablee
    motivo: str  # por qué esa vía


def a_isa(
    circuito: QuantumCircuit,
    backend: Any | None = None,
    *,
    puertas_base: Sequence[str] | None = None,
    nivel_optimizacion: int = 1,
    semilla: int | None = 0,
) -> Transpilado:
    """Devuelve `circuito` en forma ISA para `backend` (por defecto `AerSimulator`) o, si se da, para `puertas_base`."""
    if circuito.num_qubits < 1:
        raise EntradaInvalida("no se puede transpilar un circuito sin qubits")
    if importlib.util.find_spec("qiskit_ibm_transpiler") is None:
        motivo = "qiskit_ibm_transpiler no está instalado"
    else:
        motivo = "servicio de IA instalado pero no cableado (exige red y credenciales)"
    _log.info("transpilación: vía local (%s)", motivo)
    if puertas_base is not None:
        pm = generate_preset_pass_manager(optimization_level=nivel_optimizacion, basis_gates=list(puertas_base), seed_transpiler=semilla)
    else:
        pm = generate_preset_pass_manager(
            optimization_level=nivel_optimizacion, backend=backend if backend is not None else AerSimulator(), seed_transpiler=semilla
        )
    return Transpilado(pm.run(circuito), "local", motivo)
