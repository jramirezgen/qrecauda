"""Informes de corrida: lo que cada corrida escribe en registro/corridas/. Tipados, versionados y validados al leer.

Esquema 2 (el 1 nunca se escribió): añade procedencia, sha256 de la muestra cruda, semilla, ε, validador, estimador, medidas por
etapa, sha de la preinscripción y commit — lo que hace falta para auditar una corrida sin preguntar a nadie (hallazgo R.00-15).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from qrecauda.datos.esquema import leer_esquema
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.metricas import Medida, Metrica, Veredicto
from qrecauda.dominio.muestra import Origen, Procedencia

ESQUEMA_INFORME = 2
Etapas = Mapping[str, tuple[Medida, ...]]


def _medidas_a_lista(ms: tuple[Medida, ...]) -> list[list[object]]:
    return [[m.metrica.value, m.valor, m.umbral, m.cumple] for m in ms]


def _medidas_desde_lista(ls: object) -> tuple[Medida, ...]:
    return tuple(Medida(Metrica(m[0]), float(m[1]), float(m[2]), bool(m[3])) for m in ls)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class InformeCorrida:
    corrida: str  # id del nodo del DAG (p. ej. «C.E1b»)
    eureka: str  # «E1»…
    semilla: int
    origen: Origen
    procedencia: Procedencia
    qubits: int
    shots: int
    mitigada: bool
    epsilon: float
    profundidad_peres: int
    validador: str
    estimador: str
    h_min_entrada: float  # decide la longitud segura
    h_min_salida: float  # M2; ≈ 1 por construcción, no basta como prueba
    bits_crudos: int
    bits_clave: int
    sha256_muestra_cruda: str  # la muestra en sí vive en registro/muestras/ (fuera de git); aquí queda su huella
    etapas: Etapas  # «cruda» | «mitigada» | «clave» → M1/M3/M4/M5
    veredicto: Veredicto  # sobre la clave
    preinscripcion_sha: str
    commit: str
    entorno: Mapping[str, str] = field(default_factory=dict)  # versiones exactas (transversal/reproducibilidad)
    esquema: int = ESQUEMA_INFORME

    def a_mapa(self) -> dict[str, object]:
        return {
            "esquema": self.esquema,
            "corrida": self.corrida,
            "eureka": self.eureka,
            "semilla": self.semilla,
            "origen": self.origen.value,
            "procedencia": {"backend": self.procedencia.backend, "job_id": self.procedencia.job_id, "version": self.procedencia.version},
            "qubits": self.qubits,
            "shots": self.shots,
            "mitigada": self.mitigada,
            "epsilon": self.epsilon,
            "profundidad_peres": self.profundidad_peres,
            "validador": self.validador,
            "estimador": self.estimador,
            "h_min_entrada": self.h_min_entrada,
            "h_min_salida": self.h_min_salida,
            "bits_crudos": self.bits_crudos,
            "bits_clave": self.bits_clave,
            "sha256_muestra_cruda": self.sha256_muestra_cruda,
            "etapas": {k: _medidas_a_lista(v) for k, v in self.etapas.items()},
            "aprobado": self.veredicto.aprobado,
            "medidas": _medidas_a_lista(self.veredicto.medidas),
            "preinscripcion_sha": self.preinscripcion_sha,
            "commit": self.commit,
            "entorno": dict(self.entorno),
        }

    @classmethod
    def desde_mapa(cls, d: Mapping[str, object]) -> InformeCorrida:
        v = leer_esquema(d, ESQUEMA_INFORME, que="informe")
        try:
            pr = d["procedencia"]
            return cls(
                corrida=str(d["corrida"]),
                eureka=str(d["eureka"]),
                semilla=int(d["semilla"]),  # type: ignore[call-overload]
                origen=Origen(str(d["origen"])),
                procedencia=Procedencia(str(pr["backend"]), str(pr["job_id"]), str(pr["version"])),  # type: ignore[index]
                qubits=int(d["qubits"]),  # type: ignore[call-overload]
                shots=int(d["shots"]),  # type: ignore[call-overload]
                mitigada=bool(d["mitigada"]),
                epsilon=float(d["epsilon"]),  # type: ignore[arg-type]
                profundidad_peres=int(d["profundidad_peres"]),  # type: ignore[call-overload]
                validador=str(d["validador"]),
                estimador=str(d["estimador"]),
                h_min_entrada=float(d["h_min_entrada"]),  # type: ignore[arg-type]
                h_min_salida=float(d["h_min_salida"]),  # type: ignore[arg-type]
                bits_crudos=int(d["bits_crudos"]),  # type: ignore[call-overload]
                bits_clave=int(d["bits_clave"]),  # type: ignore[call-overload]
                sha256_muestra_cruda=str(d["sha256_muestra_cruda"]),
                etapas={k: _medidas_desde_lista(x) for k, x in d["etapas"].items()},  # type: ignore[attr-defined]
                veredicto=Veredicto(_medidas_desde_lista(d["medidas"])),
                preinscripcion_sha=str(d["preinscripcion_sha"]),
                commit=str(d["commit"]),
                entorno=dict(d["entorno"]),  # type: ignore[call-overload]
                esquema=v,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise EntradaInvalida(f"informe malformado: {exc}") from exc


@dataclass(frozen=True, slots=True)
class ExperimentoE2:
    """Una celda de E2: sesgo de lectura antes y después de una técnica, a un nivel de ruido, con su intervalo."""

    corrida: str
    semilla: int
    nivel: str  # «bajo» | «medio» | «alto» | «realista»
    tecnica: str  # «ninguna» | «twirling_propio» | «mthree»
    shots: int
    sesgo_crudo: float
    sesgo_residual: float
    intervalo_residual: tuple[float, float]  # IC al 95 % del sesgo residual
    esquema: int = 1
    sesgo_maximo_por_qubit: float | None = None  # máx. por qubit de |p̂_q − ½| del residuo (P.E2, nivel realista); opcional

    def a_mapa(self) -> dict[str, object]:
        mapa: dict[str, object] = {
            "esquema": self.esquema, "corrida": self.corrida, "semilla": self.semilla, "nivel": self.nivel,
            "tecnica": self.tecnica, "shots": self.shots, "sesgo_crudo": self.sesgo_crudo,
            "sesgo_residual": self.sesgo_residual, "intervalo_residual": list(self.intervalo_residual),
        }  # fmt: skip
        if self.sesgo_maximo_por_qubit is not None:
            mapa["sesgo_maximo_por_qubit"] = self.sesgo_maximo_por_qubit
        return mapa

    @classmethod
    def desde_mapa(cls, d: Mapping[str, object]) -> ExperimentoE2:
        v = leer_esquema(d, 1, que="experimento E2")
        try:
            lo, hi = d["intervalo_residual"]  # type: ignore[misc]  # fmt: skip
            maximo = d.get("sesgo_maximo_por_qubit")
            return cls(str(d["corrida"]), int(d["semilla"]), str(d["nivel"]), str(d["tecnica"]),  # type: ignore[call-overload]
                       int(d["shots"]), float(d["sesgo_crudo"]), float(d["sesgo_residual"]), (float(lo), float(hi)), v,  # type: ignore[arg-type,call-overload,has-type]
                       None if maximo is None else float(maximo))  # type: ignore[arg-type]  # fmt: skip
        except (KeyError, ValueError, TypeError) as exc:
            raise EntradaInvalida(f"experimento E2 malformado: {exc}") from exc


@dataclass(frozen=True, slots=True)
class ExperimentoE3:
    """E3: tasa y latencia con su definición (preinscrita) y la máquina en que se midieron."""

    corrida: str
    semilla: int
    repeticiones: int
    calentamiento: int
    m6_bits_por_s: float  # bits de clave / segundo de reloj de pared, un hilo
    m7_p95_ms: float  # extremo a extremo
    m7_max_ms: float
    maquina: Mapping[str, str]
    esquema: int = 1
    reporte: Mapping[str, object] = field(default_factory=dict)  # lo que P.E3 manda reportar sin decidir (JSON puro); opcional

    def a_mapa(self) -> dict[str, object]:
        mapa: dict[str, object] = {
            "esquema": self.esquema, "corrida": self.corrida, "semilla": self.semilla, "repeticiones": self.repeticiones,
            "calentamiento": self.calentamiento, "m6_bits_por_s": self.m6_bits_por_s, "m7_p95_ms": self.m7_p95_ms,
            "m7_max_ms": self.m7_max_ms, "maquina": dict(self.maquina),
        }  # fmt: skip
        if self.reporte:
            mapa["reporte"] = dict(self.reporte)
        return mapa

    @classmethod
    def desde_mapa(cls, d: Mapping[str, object]) -> ExperimentoE3:
        v = leer_esquema(d, 1, que="experimento E3")
        try:
            return cls(str(d["corrida"]), int(d["semilla"]), int(d["repeticiones"]), int(d["calentamiento"]),  # type: ignore[call-overload]
                       float(d["m6_bits_por_s"]), float(d["m7_p95_ms"]), float(d["m7_max_ms"]), dict(d["maquina"]), v,  # type: ignore[arg-type,call-overload]
                       dict(d.get("reporte", {})))  # type: ignore[call-overload]  # fmt: skip
        except (KeyError, ValueError, TypeError) as exc:
            raise EntradaInvalida(f"experimento E3 malformado: {exc}") from exc
