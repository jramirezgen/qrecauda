"""Configuración: UN objeto inmutable, validado UNA vez en la raíz de composición. Única lectora de `os.environ`."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from qrecauda.dominio.errores import EntradaInvalida

BACKENDS = ("prng", "aer_ruidoso", "ibm")


@dataclass(frozen=True, slots=True)
class Configuracion:
    backend: str = "prng"
    qubits: int = 8
    shots: int = 100_000
    semilla: int = 20261007
    epsilon_exp: int = 64  # ε = 2^-epsilon_exp
    ibm_token_ruta: str = ""  # RUTA al fichero del token; el valor no vive aquí

    def __post_init__(self) -> None:
        if self.backend not in BACKENDS:
            raise EntradaInvalida(f"backend {self.backend!r} fuera de {BACKENDS}")
        if not 1 <= self.qubits <= 127:
            raise EntradaInvalida(f"qubits={self.qubits} fuera de [1, 127]")
        if self.shots < 1:
            raise EntradaInvalida("shots debe ser positivo")
        if not 8 <= self.epsilon_exp <= 128:
            raise EntradaInvalida("epsilon_exp fuera de [8, 128]")
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
