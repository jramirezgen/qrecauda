"""EjecutorE2: mide UNA semilla de E2 exactamente como la fija docs/preinscripciones/E2.md. No decide nada: el juez decide (F2.07).

Por nivel (bajo, medio, alto de PARAMETROS.toml y el realista): la celda `ninguna` (crudo) y la `twirling_propio` (residuo), con el
estadístico de la preinscripción (media por qubit de |p̂_q − ½|) y su IC95 por bootstrap paramétrico binomial por qubit. Además los
controles C1 (el detector ve el sesgo inyectado), C2 (twirling sin ruido no inventa sesgo), C3 (twirling con canal simétrico tampoco),
C4 (puerta ZNE/PEC: ¿mueven ⟨Z⟩?; un efecto es hallazgo, no error) y C5 (mthree como contraste; si no corre, «no medido»).

Sólo habla con el `LaboratorioDeLectura` (puerto): no sabe qué SDK hay detrás; la raíz de composición lo elige.
Convenciones declaradas (⚠️ la preinscripción no las fija con este detalle):
- las celdas de contraste/puerta (`zne`, `pec`, `mthree`) no traen IC (esas técnicas devuelven cifras, no cuentas): su intervalo es (x, x);
- en `zne`/`pec` el sesgo es el AGREGADO |⟨Z⟩|/2 (ReporteSesgo), no la media por qubit;
- C4 guarda True si «sin efecto» (|Δ⟨Z⟩| < c4·|⟨Z⟩ antes|) y False si hay efecto (hallazgo); no está entre los controles que invalidan.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from qrecauda.datos import Declaracion, ExperimentoE2, Medicion, RuidoDeLectura
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.dominio.muestra import Muestra
from qrecauda.dominio.sesgo_por_qubit import frecuencias_de_unos, sesgo_maximo, sesgo_medio
from qrecauda.puertos import Bitacora, LaboratorioDeLectura

TWIRLING, NINGUNA, MTHREE, ZNE, PEC = "twirling_propio", "ninguna", "mthree", "zne", "pec"
NIVELES_C1 = ("medio", "alto")  # P.E2, tabla de controles: «`ninguna` en medio y alto»
NIVEL_C4 = "medio"  # P.E2: «`EstimadorDeSesgo` con y sin técnica, en medio»


def _intervalo(p_unos: NDArray[np.float64], shots: int, remuestras: int, semilla: int, nivel: float) -> tuple[float, float]:
    """Bootstrap paramétrico: unos*_q ~ Binomial(shots, p̂_q); percentiles simétricos de la media por qubit de |p̂*_q − ½|."""
    rng = np.random.default_rng(semilla)
    sim = np.abs(rng.binomial(shots, p_unos, size=(remuestras, p_unos.size)) / shots - 0.5).mean(axis=1)
    cola = 100.0 * (1.0 - nivel) / 2.0
    lo, hi = np.percentile(sim, [cola, 100.0 - cola])
    return float(lo), float(hi)


class EjecutorE2:
    """Implementa el puerto `Ejecutor` para E2."""

    def __init__(self, laboratorio: LaboratorioDeLectura, bitacora: Bitacora | None = None) -> None:
        self._lab = laboratorio
        self._bit = bitacora

    # ------------------------------------------------------------------ API

    def ejecutar(self, decl: Declaracion, semilla: int) -> Medicion:
        if decl.eureka != "E2":
            raise EntradaInvalida(f"EjecutorE2 mide E2, no {decl.eureka}")
        celdas: list[ExperimentoE2] = []
        controles: dict[str, bool] = {}
        niveles = self._niveles(decl)
        crudas: dict[str, Muestra] = {}
        for ruido in niveles:
            crudas[ruido.nombre] = self._par_ninguna_twirling(decl, ruido, semilla, celdas)
        controles["C1"] = self._c1(decl, celdas, niveles)
        controles["C2"] = self._control_twirling(decl, RuidoDeLectura("sin_ruido"), semilla, celdas)
        c3: tuple[float, ...] = tuple(decl.tabla("controles")["c3_canal_simetrico"])  # type: ignore[arg-type]
        controles["C3"] = self._control_twirling(decl, RuidoDeLectura("simetrico", (float(c3[0]), float(c3[1]))), semilla, celdas)
        controles["C4"] = self._c4(decl, crudas[NIVEL_C4], semilla, celdas)
        self._c5(decl, niveles, semilla, celdas, controles)
        return Medicion(e2=tuple(celdas), controles=controles)

    # ------------------------------------------------------------------ niveles

    def _niveles(self, decl: Declaracion) -> list[RuidoDeLectura]:
        tabla = decl.tabla("ruido_lectura")  # manda P.E0, no las constantes de adaptadores/aer/ruido.py
        niveles = []
        for n in decl.lista("niveles", "sinteticos"):
            par = tabla.get(n)
            if not isinstance(par, list) or len(par) != 2:
                raise EntradaInvalida(f"[ruido_lectura].{n} de E2 debe ser (p(1|0), p(0|1)), no {par!r}")
            niveles.append(RuidoDeLectura(n, (float(par[0]), float(par[1]))))
        if decl.tabla("niveles").get("realista"):
            niveles.append(RuidoDeLectura("realista", realista=True))
        return niveles

    # ------------------------------------------------------------------ celdas

    def _estadisticos(self, decl: Declaracion, muestra: Muestra, semilla: int) -> tuple[float, tuple[float, float], float]:
        p = frecuencias_de_unos(muestra.bits, muestra.qubits)
        ic = _intervalo(p, muestra.shots, int(decl.numero("intervalo", "remuestras")), semilla + 1, decl.numero("intervalo", "nivel"))
        return sesgo_medio(p), ic, sesgo_maximo(p)

    def _par_ninguna_twirling(self, decl: Declaracion, ruido: RuidoDeLectura, semilla: int, celdas: list[ExperimentoE2]) -> Muestra:
        crudo = self._lab.fuente(ruido, semilla).generar(decl.qubits, decl.shots)
        s_crudo, ic_crudo, max_crudo = self._estadisticos(decl, crudo, semilla)
        celdas.append(
            ExperimentoE2(
                decl.nodo_corrida, semilla, ruido.nombre, NINGUNA, decl.shots, s_crudo, s_crudo, ic_crudo, sesgo_maximo_por_qubit=max_crudo
            )
        )
        self._celda_twirling(decl, ruido, semilla, crudo, s_crudo, celdas)
        return crudo

    def _celda_twirling(
        self, decl: Declaracion, ruido: RuidoDeLectura, semilla: int, crudo: Muestra, s_crudo: float, celdas: list[ExperimentoE2]
    ) -> ExperimentoE2:
        bloque = int(decl.numero("tecnicas", "twirling_bloque"))
        mitigada = self._lab.twirling(ruido, semilla, bloque).mitigar(crudo)
        s, ic, mx = self._estadisticos(decl, mitigada, semilla)
        celda = ExperimentoE2(decl.nodo_corrida, semilla, ruido.nombre, TWIRLING, decl.shots, s_crudo, s, ic, sesgo_maximo_por_qubit=mx)
        celdas.append(celda)
        return celda

    # ------------------------------------------------------------------ controles

    def _c1(self, decl: Declaracion, celdas: list[ExperimentoE2], niveles: list[RuidoDeLectura]) -> bool:
        tol = decl.numero("controles", "c1_tolerancia_crudo_vs_analitico")
        ok = True
        for ruido in niveles:
            if ruido.nombre in NIVELES_C1:
                (c,) = [c for c in celdas if c.nivel == ruido.nombre and c.tecnica == NINGUNA]
                ok &= abs(c.sesgo_crudo - ruido.sesgo_analitico()) <= tol
        return bool(ok)

    def _control_twirling(self, decl: Declaracion, ruido: RuidoDeLectura, semilla: int, celdas: list[ExperimentoE2]) -> bool:
        """C2 (sin NoiseModel) y C3 (canal simétrico): el twirling no inventa sesgo; residuo ≤ el máximo del control."""
        crudo = self._lab.fuente(ruido, semilla).generar(decl.qubits, decl.shots)
        s_crudo = sesgo_medio(frecuencias_de_unos(crudo.bits, crudo.qubits))
        celda = self._celda_twirling(decl, ruido, semilla, crudo, s_crudo, celdas)
        clave = "c2_residuo_sin_ruido_maximo" if ruido.nombre == "sin_ruido" else "k3_residuo_maximo"  # C3: «residuo ≤ k3» (P.E2)
        tabla = "controles" if ruido.nombre == "sin_ruido" else "criterios_twirling"
        return celda.sesgo_residual <= decl.numero(tabla, clave)

    def _c4(self, decl: Declaracion, crudo: Muestra, semilla: int, celdas: list[ExperimentoE2]) -> bool:
        """Puerta de ZNE/PEC en el nivel medio: ¿mueven ⟨Z⟩ más del c4 relativo? «Sin efecto» es un veredicto válido."""
        rel = decl.numero("controles", "c4_sin_efecto_relativo")
        ruido = next(r for r in self._niveles(decl) if r.nombre == NIVEL_C4)
        z_antes = 1.0 - 2.0 * crudo.bits.proporcion_de_unos()
        sin_efecto = True
        for tecnica, estimador in ((ZNE, self._lab.zne(ruido, semilla)), (PEC, self._lab.pec(ruido, semilla))):
            z_despues = estimador.estimar(crudo)
            sin_efecto &= abs(z_despues - z_antes) < rel * abs(z_antes)
            antes, despues = abs(z_antes) / 2, abs(z_despues) / 2
            celdas.append(ExperimentoE2(decl.nodo_corrida, semilla, NIVEL_C4, tecnica, decl.shots, antes, despues, (despues, despues)))
        return bool(sin_efecto)

    def _c5(
        self, decl: Declaracion, niveles: list[RuidoDeLectura], semilla: int, celdas: list[ExperimentoE2], controles: dict[str, bool]
    ) -> None:
        """mthree como contraste: se reporta, no decide. Si no corre, se declara «no medido» (bitácora) y no hay celda."""
        medidos = 0
        for ruido in niveles:
            try:
                antes, despues = self._lab.sesgo_mthree(ruido, decl.qubits, decl.shots, semilla)
            except FuenteNoDisponible as exc:
                if self._bit is not None:
                    self._bit.registrar("c5_no_medido", nivel=ruido.nombre, semilla=semilla, motivo=str(exc))
                continue
            celdas.append(ExperimentoE2(decl.nodo_corrida, semilla, ruido.nombre, MTHREE, decl.shots, antes, despues, (despues, despues)))
            medidos += 1
        if medidos == len(niveles):
            controles["C5"] = True
