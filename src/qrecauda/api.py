"""Fachada pública y estable. La CLI es un cliente más de ella; tests/arquitectura/test_api.py congela sus firmas."""

from __future__ import annotations

from pathlib import Path

from qrecauda import composicion
from qrecauda.aplicacion.demo import ResultadoDemo
from qrecauda.aplicacion.pipeline import Resultado
from qrecauda.datos import ManifiestoDeCorrida, VeredictoDeEureka
from qrecauda.transversal.configuracion import Configuracion

__all__ = [
    "Configuracion",
    "ManifiestoDeCorrida",
    "Resultado",
    "ResultadoDemo",
    "VeredictoDeEureka",
    "correr",
    "demo",
    "generar_clave",
    "hardware",
    "juzgar",
]


def generar_clave(cfg: Configuracion) -> Resultado:
    return composicion.ejecutar(cfg)


def correr(declaracion: Path, raiz: Path) -> ManifiestoDeCorrida:
    """F2.07: corre cada semilla de `declaracion` (relativa a `raiz`, la raíz del repo) y escribe `registro/corridas/<id>.json`."""
    return composicion.correr_declaracion(declaracion, raiz)


def juzgar(eureka: str, raiz: Path) -> VeredictoDeEureka:
    """F2.07: aplica el criterio de `declaraciones/<eureka>.toml` a la corrida ya hecha y añade una línea a `registro/veredictos.jsonl`."""
    return composicion.juzgar_eureka(eureka, raiz)


def demo(
    cfg: Configuracion,
    *,
    rapido: bool = False,
    fuente: str = "aer",
    ensayo: bool = False,
    max_segundos_qpu: float | None = None,
    shots: int | None = None,
) -> ResultadoDemo:
    """F7.07: PRNG, Aer sin mitigar y Aer con twirling lado a lado, y un peaje y un trayecto de Metro cifrados con la mejor clave.
    Determinista dada `cfg.semilla`, sin red ni credencial. `fuente="ibm"` añade el hardware (token por ruta en `cfg`); `ensayo`, su
    camino completo contra un backend falso. Rotulada «simulado» salvo hardware real. `cfg.dimensionado` elige «mcv» (por omisión)
    o «conservador» (90B; exige >= 1 Mbit por rama: pide `shots` >= 125000 con 8 qubits); `shots` sustituye los de las ramas de Aer."""
    return composicion.demo_de(cfg, rapido=rapido, fuente=fuente, ensayo=ensayo, max_segundos_qpu=max_segundos_qpu, shots=shots)


def hardware(
    raiz: Path,
    *,
    cfg: Configuracion | None = None,
    declaracion: Path = Path("declaraciones/E4.toml"),
    ensayo: bool = False,
    max_segundos_qpu: float | None = None,
    ia: bool = False,
) -> ManifiestoDeCorrida:
    """F3.07: el contraste de E4 (mismo circuito en Aer realista y en el hardware, un trabajo por semilla). El token sale de
    `cfg.ibm_token_ruta` (una RUTA). Real ⇒ `registro/corridas/`; `ensayo` ⇒ backend falso, sin cuota, en `salidas/ensayo_e4/`."""
    c = cfg if cfg is not None else Configuracion()
    return composicion.correr_hardware(
        raiz, declaracion, token_ruta=c.ibm_token_ruta, backend=c.ibm_backend, ensayo=ensayo, max_segundos_qpu=max_segundos_qpu, ia=ia,
        instancia=c.ibm_instancia,
    )  # fmt: skip
