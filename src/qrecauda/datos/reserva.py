"""Datos de la reserva asíncrona de claves (F6.03): lo que cruza del productor al consumidor y lo que el productor informa al parar.

Una clave viaja con su `MetaClave`; en cualquier informe, bitácora o manifiesto sólo entra la meta (huella corta), nunca la clave.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida


@dataclass(frozen=True, slots=True)
class MetaClave:
    """Qué se sabe de una clave sin la clave: su índice, su coste de generación y su huella sha256 de 12 hex."""

    indice: int
    semilla: int  # semilla·100 + i de la clave (la del primer intento)
    bits: int
    rechazos: int  # intentos descartados por M1–M5 antes de la clave aprobada
    t_gen_ns: int  # pared de TODOS los intentos de esta clave (los rechazados suman)
    h90b: float
    fin_ns: int  # reloj monotónico del sistema al terminar la generación
    huella: str
    bloqueado_ns: int = 0  # tiempo que esperó a que hubiera sitio en la cola (contrapresión); lo completa el informe final
    entregada: bool = True  # False: terminó de generarse pero la parada llegó antes de poder encolarla

    def a_mapa(self) -> dict[str, object]:
        return {
            "indice": self.indice, "semilla": self.semilla, "bits": self.bits, "rechazos": self.rechazos, "t_gen_ns": self.t_gen_ns,
            "h90b": self.h90b, "fin_ns": self.fin_ns, "huella": self.huella, "bloqueado_ns": self.bloqueado_ns,
            "entregada": self.entregada,
        }  # fmt: skip

    @classmethod
    def desde_mapa(cls, d: Mapping[str, object]) -> MetaClave:
        try:
            return cls(
                int(d["indice"]), int(d["semilla"]), int(d["bits"]), int(d["rechazos"]), int(d["t_gen_ns"]),  # type: ignore[call-overload]
                float(d["h90b"]), int(d["fin_ns"]), str(d["huella"]), int(d.get("bloqueado_ns", 0)), bool(d.get("entregada", True)),  # type: ignore[call-overload,arg-type]
            )  # fmt: skip
        except (KeyError, ValueError, TypeError) as exc:
            raise EntradaInvalida(f"meta de clave malformada: {exc!r}") from exc

    def con_bloqueo(self, bloqueado_ns: int, entregada: bool) -> MetaClave:
        return replace(self, bloqueado_ns=bloqueado_ns, entregada=entregada)


@dataclass(frozen=True, slots=True)
class ClaveEntregada:
    """Una clave aprobada por M1–M5 con su meta, su rótulo (D-002) y el origen de su muestra. `repr` no la muestra (Bits)."""

    clave: Bits
    meta: MetaClave
    rotulo: str
    origen: str


@dataclass(frozen=True, slots=True)
class InformeDelProductor:
    """Lo que el proceso productor informa al parar: dónde corrió, cuánta CPU gastó y la meta de cada clave que generó."""

    nucleos: tuple[int, ...]  # afinidad efectiva del proceso
    pared_ns: int  # desde que entra su función hasta que sale
    cpu_ns: int  # CPU propia + hijos esperados (p. ej. el binario del 90B) en esa ventana
    cpu_proceso_ns: int  # sólo la propia
    claves: tuple[MetaClave, ...]
    forzado: bool = False  # True: no paró a tiempo y hubo que terminarlo; sin este informe de primera mano

    @property
    def cpu_sobre_pared(self) -> float:
        return self.cpu_ns / self.pared_ns if self.pared_ns > 0 else float("inf")

    def a_mapa(self) -> dict[str, object]:
        return {
            "nucleos": list(self.nucleos), "pared_ns": self.pared_ns, "cpu_ns": self.cpu_ns, "cpu_proceso_ns": self.cpu_proceso_ns,
            "claves": [c.a_mapa() for c in self.claves], "forzado": self.forzado,
        }  # fmt: skip

    @classmethod
    def desde_mapa(cls, d: Mapping[str, object]) -> InformeDelProductor:
        try:
            return cls(
                tuple(int(n) for n in d["nucleos"]),  # type: ignore[attr-defined]
                int(d["pared_ns"]), int(d["cpu_ns"]), int(d["cpu_proceso_ns"]),  # type: ignore[call-overload]
                tuple(MetaClave.desde_mapa(c) for c in d["claves"]),  # type: ignore[attr-defined]
                bool(d.get("forzado", False)),
            )  # fmt: skip
        except (KeyError, ValueError, TypeError) as exc:
            raise EntradaInvalida(f"informe del productor malformado: {exc!r}") from exc
