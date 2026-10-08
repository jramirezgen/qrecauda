"""Configuración: UN objeto inmutable, validado UNA vez en la raíz de composición. Única lectora de `os.environ`."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from qrecauda.dominio.errores import EntradaInvalida

BACKENDS = ("prng", "aer_ruidoso", "ibm")
MODOS_IBM = (
    "batch",
    "session",
    "trabajo",
)  # cómo agrupa SamplerV2 los trabajos; «trabajo» = suelto (el único del plan abierto, ⚠️ sin verificar)
MITIGACIONES = ("ninguna", "lectura")  # «lectura» = twirling de lectura propio (D-009)
NIVELES_RUIDO = ("bajo", "medio", "alto", "realista")  # «realista» = FakeSherbrooke congelado; los demás, canales sintéticos
VALIDADORES = ("estadistico", "nist")


@dataclass(frozen=True, slots=True)
class Configuracion:
    backend: str = "prng"
    qubits: int = 8
    shots: int = 100_000
    semilla: int = 20261007
    epsilon_exp: int = 64  # ε = 2^-epsilon_exp
    ibm_token_ruta: str = ""  # RUTA al fichero del token; el valor no vive aquí
    ibm_backend: str = ""  # nombre del backend de IBM; vacío = el menos ocupado con qubits suficientes
    ibm_modo: str = "batch"  # «batch», «session» o «trabajo» (SamplerV2 sobre IBM Runtime)
    mitigacion: str = "ninguna"
    nivel_ruido: str = "medio"  # sólo lo usa el backend aer_ruidoso
    validador: str = "estadistico"

    def __post_init__(self) -> None:
        if self.backend not in BACKENDS:
            raise EntradaInvalida(f"backend {self.backend!r} fuera de {BACKENDS}")
        if not 1 <= self.qubits <= 127:
            raise EntradaInvalida(f"qubits={self.qubits} fuera de [1, 127]")
        if self.shots < 1:
            raise EntradaInvalida("shots debe ser positivo")
        if not 8 <= self.epsilon_exp <= 128:
            raise EntradaInvalida("epsilon_exp fuera de [8, 128]")
        for nombre, valor, vocabulario in (
            ("mitigacion", self.mitigacion, MITIGACIONES),
            ("nivel_ruido", self.nivel_ruido, NIVELES_RUIDO),
            ("validador", self.validador, VALIDADORES),
            ("ibm_modo", self.ibm_modo, MODOS_IBM),
        ):
            if valor not in vocabulario:
                raise EntradaInvalida(f"{nombre} {valor!r} fuera de {vocabulario}")
        if self.mitigacion == "lectura" and self.backend != "aer_ruidoso":
            raise EntradaInvalida("la mitigación «lectura» re-ejecuta el circuito: sólo existe sobre backend aer_ruidoso")
        if self.backend == "ibm" and not self.ibm_token_ruta:
            raise EntradaInvalida("backend ibm exige ibm_token_ruta (ruta, nunca el valor)")

    @classmethod
    def desde_mapa(cls, mapa: Mapping[str, object]) -> Configuracion:
        sobran = set(mapa) - {f.name for f in fields(cls)}
        if sobran:
            raise EntradaInvalida(f"claves desconocidas en la configuración: {sorted(sobran)}")
        for f in fields(cls):
            if f.name in mapa:
                v = mapa[f.name]
                # bool es subclase de int: `qubits = true` no es un entero de configuración
                if type(v) is not {"str": str, "int": int}[str(f.type)]:
                    raise EntradaInvalida(f"tipo de {f.name}: se esperaba {f.type}, llegó {type(v).__name__}")
        return cls(**mapa)  # type: ignore[arg-type]

    def como_dict(self) -> dict[str, object]:
        """Para el manifiesto: claves ordenadas, sólo rutas (nunca el valor de un secreto)."""
        return dict(sorted(asdict(self).items()))

    @classmethod
    def cargar(cls, ruta: Path | None) -> Configuracion:
        base: dict[str, object] = tomllib.loads(ruta.read_text()) if ruta else {}
        if t := os.environ.get("QRECAUDA_IBM_TOKEN_FILE"):
            base.setdefault("ibm_token_ruta", t)
        return cls.desde_mapa(base)


def entorno_sin_git() -> dict[str, str]:
    """El entorno del proceso sin las variables `GIT_*`: dentro de un hook heredarían el repo equivocado al lanzar `git`."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def omp_num_threads() -> str | None:
    """`OMP_NUM_THREADS` tal cual está en el proceso (P.E3 lo exige a «1» ANTES de importar numpy/Aer). Única lectora, como el resto."""
    return os.environ.get("OMP_NUM_THREADS")
