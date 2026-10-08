"""Lo que una corrida produce y lo que el juez concluye: Medicion → ManifiestoDeCorrida → VeredictoDeEureka."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from qrecauda.datos.esquema import leer_esquema
from qrecauda.datos.informe import ExperimentoE2, ExperimentoE3, ExperimentoE3b, InformeCorrida, MedidaDeFuente
from qrecauda.dominio.errores import EntradaInvalida


@dataclass(frozen=True, slots=True)
class Medicion:
    """Lo que el ejecutor entrega por semilla: artefactos tipados y el resultado de los controles que corrió (id → pasó)."""

    informes: tuple[InformeCorrida, ...] = ()
    e2: tuple[ExperimentoE2, ...] = ()
    e3: tuple[ExperimentoE3, ...] = ()
    fuentes: tuple[MedidaDeFuente, ...] = ()
    controles: Mapping[str, bool] = field(default_factory=dict)
    e3b: tuple[ExperimentoE3b, ...] = ()


@dataclass(frozen=True, slots=True)
class ManifiestoDeCorrida:
    """El registro de una corrida: qué artefactos escribió (nombre, tipo, sha256), con qué commit y qué preinscripción."""

    corrida: str
    eureka: str
    preinscripcion_sha: str
    commit: str
    entorno: Mapping[str, str]
    artefactos: tuple[tuple[str, str, str], ...]  # (nombre en el Almacén, «informe»|«e2»|«e3»|«e3b»|«fuente», sha256)
    controles: Mapping[str, bool]
    esquema: int = 1

    def a_mapa(self) -> dict[str, object]:
        return {
            "esquema": self.esquema, "corrida": self.corrida, "eureka": self.eureka,
            "preinscripcion_sha": self.preinscripcion_sha, "commit": self.commit, "entorno": dict(self.entorno),
            "artefactos": [list(a) for a in self.artefactos], "controles": dict(self.controles),
        }  # fmt: skip

    @classmethod
    def desde_mapa(cls, d: Mapping[str, object]) -> ManifiestoDeCorrida:
        v = leer_esquema(d, 1, que="manifiesto de corrida")
        try:
            return cls(
                str(d["corrida"]), str(d["eureka"]), str(d["preinscripcion_sha"]), str(d["commit"]),
                dict(d["entorno"]),  # type: ignore[call-overload]
                tuple((str(a[0]), str(a[1]), str(a[2])) for a in d["artefactos"]),  # type: ignore[attr-defined]
                {str(k): bool(x) for k, x in d["controles"].items()},  # type: ignore[attr-defined]
                v,
            )  # fmt: skip
        except (KeyError, ValueError, TypeError, IndexError) as exc:
            raise EntradaInvalida(f"manifiesto de corrida malformado: {exc!r}") from exc


@dataclass(frozen=True, slots=True)
class Criterio:
    id: str  # «T1/20261007», «medio/20261008»…
    cumple: bool
    detalle: str
    decide: bool = True  # False: se reporta (p. ej. el nivel realista de E2) pero no entra en la conjunción


@dataclass(frozen=True, slots=True)
class VeredictoDeEureka:
    eureka: str
    corrida: str
    desenlace: str  # «CUMPLE» | «CUMPLE_PARCIAL» | «NULO» | «INCONCLUSO» | «NO_CUMPLE»
    resumen: str
    criterios: tuple[Criterio, ...]
    preinscripcion_sha: str
    commit: str
    esquema: int = 1

    @property
    def aprobado(self) -> bool:
        return self.desenlace == "CUMPLE"

    def a_mapa(self) -> dict[str, object]:
        return {
            "esquema": self.esquema, "eureka": self.eureka, "corrida": self.corrida, "desenlace": self.desenlace,
            "aprobado": self.aprobado, "resumen": self.resumen, "preinscripcion_sha": self.preinscripcion_sha,
            "commit": self.commit,
            "criterios": [{"id": c.id, "cumple": c.cumple, "decide": c.decide, "detalle": c.detalle} for c in self.criterios],
        }  # fmt: skip
