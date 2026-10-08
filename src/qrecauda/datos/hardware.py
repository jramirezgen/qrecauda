"""Lo que un envío a IBM deja escrito: trabajo, backend, calibración, transpilación y tiempos (DAG F3.07).

Es JSON puro para ir en `InformeCorrida.reporte`. Nada de aquí es un secreto: ni token ni instancia.
En un ensayo (`ensayo=True`) el «backend» es un backend FALSO y los tiempos no significan nada: el registro lo dice y el juez lo exige.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from qrecauda.datos.esquema import leer_esquema
from qrecauda.dominio.errores import EntradaInvalida

ESQUEMA_REGISTRO_IBM = 1


@dataclass(frozen=True, slots=True)
class CalibracionQubit:
    """Calibración de un qubit FÍSICO usado, tal como la publica el backend (SI: segundos). `None`: el backend no la dio."""

    qubit: int
    t1_s: float | None
    t2_s: float | None
    error_lectura: float | None

    def a_mapa(self) -> dict[str, object]:
        return {"qubit": self.qubit, "t1_s": self.t1_s, "t2_s": self.t2_s, "error_lectura": self.error_lectura}

    @classmethod
    def desde_mapa(cls, d: Mapping[str, object]) -> CalibracionQubit:
        try:
            return cls(int(d["qubit"]), _opt(d["t1_s"]), _opt(d["t2_s"]), _opt(d["error_lectura"]))  # type: ignore[call-overload]
        except (KeyError, ValueError, TypeError) as exc:
            raise EntradaInvalida(f"calibración malformada: {exc!r}") from exc


def _opt(v: object) -> float | None:
    return None if v is None else float(v)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RegistroIbm:
    job_id: str
    backend: str
    version_sdk: str
    modo: str  # «trabajo» | «batch» | «session»
    ensayo: bool  # True: backend falso, sin cuota gastada y sin origen cuántico
    shots: int  # totales del trabajo (suma de todos los PUBs)
    pubs: int
    mascaras: int  # máscaras X del twirling (0: sin twirling)
    qubits_fisicos: tuple[int, ...]  # el físico que midió cada qubit lógico, en orden lógico
    profundidad: int  # del circuito transpilado más profundo
    puertas_dos_qubits: int
    via_transpilacion: str  # «local» | «ia»
    motivo_transpilacion: str
    calibracion_fecha: str  # ISO 8601 de la calibración que el backend declara; «» si no la expone
    calibracion: tuple[CalibracionQubit, ...]
    creado: str  # ISO 8601; «» si el servicio no lo da
    cola_s: float | None  # del envío al inicio de la ejecución (mundo real: la cola); None si no hay marcas
    ejecucion_s: float | None  # del inicio al final
    uso_qpu_s: float | None  # lo que IBM cargó, si ya lo calculó
    estimado_qpu_s: float
    esquema: int = ESQUEMA_REGISTRO_IBM
    extra: Mapping[str, object] = field(default_factory=dict)

    def a_mapa(self) -> dict[str, object]:
        return {
            "esquema": self.esquema, "job_id": self.job_id, "backend": self.backend, "version_sdk": self.version_sdk,
            "modo": self.modo, "ensayo": self.ensayo, "shots": self.shots, "pubs": self.pubs, "mascaras": self.mascaras,
            "qubits_fisicos": list(self.qubits_fisicos), "profundidad": self.profundidad,
            "puertas_dos_qubits": self.puertas_dos_qubits, "via_transpilacion": self.via_transpilacion,
            "motivo_transpilacion": self.motivo_transpilacion, "calibracion_fecha": self.calibracion_fecha,
            "calibracion": [c.a_mapa() for c in self.calibracion], "creado": self.creado, "cola_s": self.cola_s,
            "ejecucion_s": self.ejecucion_s, "uso_qpu_s": self.uso_qpu_s, "estimado_qpu_s": self.estimado_qpu_s,
            "extra": dict(self.extra),
        }  # fmt: skip

    @classmethod
    def desde_mapa(cls, d: Mapping[str, object]) -> RegistroIbm:
        v = leer_esquema(d, ESQUEMA_REGISTRO_IBM, que="registro de IBM")
        try:
            return cls(
                str(d["job_id"]), str(d["backend"]), str(d["version_sdk"]), str(d["modo"]), bool(d["ensayo"]), int(d["shots"]),  # type: ignore[call-overload]
                int(d["pubs"]), int(d["mascaras"]), tuple(int(q) for q in d["qubits_fisicos"]), int(d["profundidad"]),  # type: ignore[call-overload,attr-defined]
                int(d["puertas_dos_qubits"]), str(d["via_transpilacion"]), str(d["motivo_transpilacion"]),  # type: ignore[call-overload]
                str(d["calibracion_fecha"]), tuple(CalibracionQubit.desde_mapa(c) for c in d["calibracion"]),  # type: ignore[attr-defined]
                str(d["creado"]), _opt(d["cola_s"]), _opt(d["ejecucion_s"]), _opt(d["uso_qpu_s"]), float(d["estimado_qpu_s"]),  # type: ignore[arg-type]
                v, dict(d.get("extra", {})),  # type: ignore[call-overload]
            )  # fmt: skip
        except (KeyError, ValueError, TypeError) as exc:
            raise EntradaInvalida(f"registro de IBM malformado: {exc!r}") from exc
