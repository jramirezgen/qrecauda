"""Transpilación a forma ISA: pass manager local de qiskit y, detrás de un flag, AIRouting/StagedPassManager de qiskit-ibm-transpiler
(DAG F3.03 y F3.07). Es un paso del adaptador de fuente, no un puerto propio: el núcleo no sabe qué es un circuito.

La vía por omisión es la local (`generate_preset_pass_manager` contra el backend). La de IA (`ia=True`) exige `qiskit_ibm_transpiler`
(NO está en el entorno: es un extra de pago de red y credenciales). Si falta, o el servicio falla, se DEGRADA a la local con un
`UserWarning` y un log de nivel WARNING y `Transpilado.motivo` lo dice: nunca en silencio.

⚠️ sin verificar: la fábrica real de la vía de IA (`_fabrica_ia_real`) sigue la API documentada de qiskit-ibm-transpiler, que no se
pudo leer aquí por no estar instalado; los tests la cubren con un doble inyectado (`fabrica_ia`).
"""

from __future__ import annotations

import importlib.util
import logging
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from qiskit import QuantumCircuit
from qiskit.exceptions import QiskitError
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator

from qrecauda.dominio.errores import EntradaInvalida

_log = logging.getLogger(__name__)

FabricaIA = Callable[[Any, int], Any]  # (backend, nivel de optimización) -> objeto con `.run(circuito)`
_FALLOS_DE_LA_IA = (QiskitError, ImportError, OSError, RuntimeError, ValueError, TypeError, KeyError, AttributeError)


@dataclass(frozen=True, slots=True)
class Transpilado:
    circuito: QuantumCircuit
    via: str  # «local» (pass manager de qiskit) | «ia» (qiskit_ibm_transpiler)
    motivo: str  # por qué esa vía

    @property
    def profundidad(self) -> int:
        return int(self.circuito.depth())

    @property
    def puertas_dos_qubits(self) -> int:
        return sum(1 for i in self.circuito.data if i.operation.num_qubits == 2 and i.operation.name not in ("barrier",))


def _fabrica_ia_real(backend: Any, nivel: int) -> Any:
    """Pass manager por etapas con el enrutado de IA en lugar del de qiskit. ⚠️ sin verificar la API (paquete no instalado)."""
    from qiskit.transpiler import PassManager, StagedPassManager
    from qiskit_ibm_transpiler.ai.routing import AIRouting  # type: ignore[import-not-found,unused-ignore]

    base = generate_preset_pass_manager(optimization_level=nivel, backend=backend, seed_transpiler=0)
    enrutado = PassManager([AIRouting(backend_name=getattr(backend, "name", None), optimization_level=nivel, layout_mode="optimize")])
    etapas = ["init", "layout", "routing", "translation", "optimization", "scheduling"]
    return StagedPassManager(
        stages=etapas, **{e: (enrutado if e == "routing" else getattr(base, e)) for e in etapas if getattr(base, e, None) is not None}
    )


def _degradar(motivo: str) -> str:
    texto = f"vía de IA degradada a la local: {motivo}"
    _log.warning(texto)
    warnings.warn(texto, UserWarning, stacklevel=3)
    return texto


def a_isa(
    circuito: QuantumCircuit,
    backend: Any | None = None,
    *,
    puertas_base: Sequence[str] | None = None,
    nivel_optimizacion: int = 1,
    semilla: int | None = 0,
    ia: bool = False,
    fabrica_ia: FabricaIA | None = None,
) -> Transpilado:
    """Devuelve `circuito` en forma ISA para `backend` (por defecto `AerSimulator`) o, si se da, para `puertas_base`.

    `ia=True` pide la vía de IA; `fabrica_ia` sólo se pasa en las pruebas (un doble sin red ni paquete)."""
    if circuito.num_qubits < 1:
        raise EntradaInvalida("no se puede transpilar un circuito sin qubits")
    if ia and puertas_base is None:
        if fabrica_ia is None and importlib.util.find_spec("qiskit_ibm_transpiler") is None:
            motivo = _degradar("qiskit_ibm_transpiler no está instalado (extra no incluido); se usa el pass manager de qiskit")
        else:
            try:
                resultado = (fabrica_ia or _fabrica_ia_real)(backend if backend is not None else AerSimulator(), nivel_optimizacion).run(
                    circuito
                )
                _log.info("transpilación: vía de IA (AIRouting en un StagedPassManager)")
                return Transpilado(resultado, "ia", "servicio de IA de qiskit-ibm-transpiler (AIRouting) pedido con el flag")
            except _FALLOS_DE_LA_IA as e:
                motivo = _degradar(f"el servicio de IA falló ({type(e).__name__}: {e}); se usa el pass manager de qiskit")
    else:
        motivo = "vía local: IA no pedida" if not ia else "vía local: con puertas base fijas no hay enrutado de IA"
        _log.info("transpilación: vía local (%s)", motivo)
    if puertas_base is not None:
        pm = generate_preset_pass_manager(optimization_level=nivel_optimizacion, basis_gates=list(puertas_base), seed_transpiler=semilla)
    else:
        pm = generate_preset_pass_manager(
            optimization_level=nivel_optimizacion, backend=backend if backend is not None else AerSimulator(), seed_transpiler=semilla
        )
    return Transpilado(pm.run(circuito), "local", motivo)
