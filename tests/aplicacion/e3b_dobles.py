"""Dobles de E3b: reloj y temporizador deterministas, un productor que entrega claves de una lista y una sonda con CPU fijada a mano.

El cifrado y el registro de consumo son los REALES (`aes_gcm`); sólo el tiempo y el proceso productor son falsos.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.datos import ClaveEntregada, Declaracion, InformeDelProductor, MetaClave
from qrecauda.dominio.bits import Bits

RAIZ = Path(__file__).resolve().parents[2]
MS = 1_000_000
BITS_CLAVE = 3520  # 10 trozos de 352 bits
ROTULO = "validación del pipeline"


class RelojFalso:
    def __init__(self, paso: int = MS) -> None:
        self.t, self.paso = 0, paso

    def ahora_ns(self) -> int:
        self.t += self.paso
        return self.t


class TemporizadorFalso:
    """Adelanta el reloj hasta la llegada programada (si ya pasó, no hace nada)."""

    def __init__(self, reloj: RelojFalso) -> None:
        self.reloj = reloj

    def esperar_hasta_ns(self, t_ns: int) -> None:
        self.reloj.t = max(self.reloj.t, t_ns)


class SondaFalsa:
    def __init__(self, reloj: RelojFalso, *, factor_cpu: float = 0.5, carga: float = 0.1) -> None:
        self.reloj, self.factor, self.carga = reloj, factor_cpu, carga

    def esperar_reposo(self, maximo: float, tope_s: float) -> None:
        return None

    def carga_previa(self) -> float:
        return self.carga

    def cpu_proceso_ns(self) -> int:
        return int(self.reloj.t * self.factor)

    def cpu_con_hijos_ns(self) -> int:
        return self.cpu_proceso_ns()

    def maquina(self) -> dict[str, str]:
        return {"cpu": "doble", "nucleos": "20", "ram": "16 GB", "kernel": "6.x"}


def clave_entregada(
    i: int, *, t_gen_ms: int = 100, fin_ms: int = 50, rotulo: str = ROTULO, origen: str = "simulador_aer"
) -> ClaveEntregada:
    rng = np.random.default_rng(1000 + i)
    bits = Bits((rng.random(BITS_CLAVE) < 0.5).astype(np.uint8))
    huella = f"{i:012x}"
    return ClaveEntregada(bits, MetaClave(i, 20261007 * 100 + i, BITS_CLAVE, 0, t_gen_ms * MS, 0.9, fin_ms * MS, huella), rotulo, origen)


class ProductorFalso:
    """Entrega `claves` en orden. `esperan`: índices que no están listos a `tomar(0.0)` pero sí tras esperar."""

    def __init__(
        self, claves: list[ClaveEntregada], *, esperan: frozenset[int] = frozenset(), informe: InformeDelProductor | None = None
    ) -> None:
        self.cola, self.esperan, self._informe, self._todas = list(claves), set(esperan), informe, tuple(claves)
        self.iniciado = self.detenido = False
        self.esperas_pedidas: list[float | None] = []

    def iniciar(self) -> None:
        self.iniciado = True

    def tomar(self, espera_s: float | None) -> ClaveEntregada | None:
        self.esperas_pedidas.append(espera_s)
        if not self.cola:
            return None
        if espera_s == 0.0 and self.cola[0].meta.indice in self.esperan:
            return None
        return self.cola.pop(0)

    def listas(self) -> int:
        return len(self.cola)

    def detener(self) -> InformeDelProductor:
        self.detenido = True
        if self._informe is not None:
            return self._informe
        return InformeDelProductor((8,), 10_000 * MS, 4_000 * MS, 4_000 * MS, tuple(c.meta for c in self._todas))


def declaracion_diminuta(
    *, transacciones: int = 20, tx_por_s: float = 100.0, ajustes: dict[str, dict[str, object]] | None = None
) -> Declaracion:
    """E3b con la demanda reducida (0,2 s a λ=100): mismos umbrales, mismos controles."""
    d = cargar_declaracion(Path("declaraciones/E3b.toml"), RAIZ)
    t = {k: dict(v) for k, v in d.tablas.items()}
    t["demanda"].update(tx_por_s=tx_por_s, duracion_s=transacciones / tx_por_s, transacciones=transacciones, consumo_bps=tx_por_s * 352)
    for tabla, campos in (ajustes or {}).items():
        t[tabla].update(campos)
    return replace(d, tablas=t)
