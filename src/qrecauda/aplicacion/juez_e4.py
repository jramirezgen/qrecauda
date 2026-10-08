"""El criterio de E4 (docs/preinscripciones/E4.md) aplicado a los artefactos releídos. Tabla de desenlaces tal cual:

- CUMPLE          H1 y H2 en TODOS los trabajos.
- CUMPLE_PARCIAL  H2 en todos y H1 falla en alguno (el hardware da una clave válida pero su sesgo crudo no es el del modelo).
- NO_CUMPLE       H2 falla en algún trabajo.
Un control (N1, S1, V1) que se recalcula y falla no es un desenlace: es una corrida inválida (`CorridaInvalida`).
"""

from __future__ import annotations

from collections.abc import Mapping

from qrecauda.aplicacion import criterios_e4 as c
from qrecauda.datos import Criterio, Declaracion, InformeCorrida, ManifiestoDeCorrida, VeredictoDeEureka
from qrecauda.dominio.errores import CorridaInvalida
from qrecauda.dominio.metricas import Metrica


def _trabajo(i: InformeCorrida) -> Mapping[str, object]:
    t = i.reporte.get("trabajo")
    return t if isinstance(t, Mapping) else {}


def _fmt(v: object) -> str:
    return f"{v:.4g}" if isinstance(v, int | float) and not isinstance(v, bool) else "no medido"


def juzgar_e4(decl: Declaracion, m: ManifiestoDeCorrida, informes: list[InformeCorrida]) -> VeredictoDeEureka:
    por = {(i.corrida, i.semilla): i for i in informes}
    esperadas = {(corrida, s) for corrida in c.CORRIDAS for s in decl.semillas}
    if set(por) != esperadas:
        raise CorridaInvalida(f"E4 se juzga con {list(c.CORRIDAS)} en cada semilla declarada {decl.semillas}; falta o sobra algo")
    tol = float(decl.tabla("criterios")["h1"]["tolerancia_sesgo_por_qubit"])  # type: ignore[index]
    hw = [por[(k, s)] for s in decl.semillas for k in (c.HW_CRUDA, c.HW_TWIRL)]
    # Los controles se recalculan de los artefactos: un «ok» del manifiesto que los datos desmienten invalida la corrida.
    if not all(c.n1_cumple(por[(c.PRNG, s)]) for s in decl.semillas):
        raise CorridaInvalida("N1 falla al recalcularse: la batería rechaza al PRNG; corrida inválida, no un veredicto")
    if not all(
        c.s1_cumple(por[(c.AER_CRUDA, s)], por[(c.AER_TWIRL, s)], por[(c.HW_CRUDA, s)], por[(c.HW_TWIRL, s)]) for s in decl.semillas
    ):
        raise CorridaInvalida("S1 falla: el simulador y el hardware no corrieron la misma declaración")
    if not c.v1_cumple(hw, len(decl.semillas)):
        raise CorridaInvalida(
            f"V1 falla: se exigen {len(decl.semillas)} trabajos distintos de hardware_ibm real (no un falso); sin ellos no hay veredicto"
        )
    cs: list[Criterio] = []
    h1_mal: list[int] = []
    h2_mal: list[int] = []
    for s in decl.semillas:
        d, e = por[(c.HW_CRUDA, s)], por[(c.HW_TWIRL, s)]
        b, t = por[(c.AER_CRUDA, s)], por[(c.AER_TWIRL, s)]  # el gemelo en Aer: sin mitigar y con twirling
        ok1, dif, dif_media = c.h1_detalle(d, b, tol)
        ok2 = c.h2_cumple(e)
        cs.append(
            Criterio(
                f"H1/{s}",
                ok1,
                f"sesgo por qubit, hardware vs gemelo en Aer (mismos qubits y circuitos): máx |Δ|={dif:.4g} ≤ {tol} "
                f"(media |Δ|={dif_media:.4g})",
            )
        )
        malas = [x.value for x in e.veredicto.fallos() if x not in (Metrica.TASA, Metrica.LATENCIA)]
        cs.append(Criterio(f"H2/{s}", ok2, f"clave del hardware con twirling ({e.procedencia.job_id}): fallan {malas or 'ninguna'}"))
        h1_mal += [] if ok1 else [s]
        h2_mal += [] if ok2 else [s]
        tr = _trabajo(e)
        cs.append(
            Criterio(
                f"cola_y_ejecucion/{s}",
                True,
                f"{e.procedencia.backend}/{e.procedencia.job_id}: cola {_fmt(tr.get('cola_s'))} s, "
                f"ejecución {_fmt(tr.get('ejecucion_s'))} s, QPU {_fmt(tr.get('uso_qpu_s'))} s (se reportan; no deciden)",
                decide=False,
            )
        )
        for etiqueta, i in (("M6_M7_hw", e), ("M6_M7_aer", t)):
            ms = {x.metrica: x for x in i.veredicto.medidas}
            cs.append(
                Criterio(
                    f"{etiqueta}/{s}",
                    ms[Metrica.TASA].cumple and ms[Metrica.LATENCIA].cumple,
                    f"cadena local de {i.corrida}: M6={ms[Metrica.TASA].valor:.6g} bit/s, M7={ms[Metrica.LATENCIA].valor:.6g} ms "
                    f"(sin cola ni red de IBM; no deciden)",
                    decide=False,
                )
            )
        cs.append(
            Criterio(
                f"twirling_hw/{s}",
                True,
                f"sesgo medio por qubit del hardware: crudo {d.reporte['sesgo_medio_por_qubit']:.4g} → con twirling "
                f"{e.reporte['sesgo_medio_por_qubit']:.4g} (informativo)",
                decide=False,
            )
        )
    if h2_mal:
        return _v(decl, m, "NO_CUMPLE", f"H2 falla en las semillas {h2_mal}: la clave del hardware con twirling no pasa M1–M5.", cs)
    if h1_mal:
        return _v(
            decl,
            m,
            "CUMPLE_PARCIAL",
            f"H2 en todos los trabajos; H1 falla en {h1_mal}: el sesgo crudo del hardware se aparta del que predice su calibración.",
            cs,
        )
    return _v(
        decl,
        m,
        "CUMPLE",
        "H1 y H2 en todos los trabajos. Esto NO certifica aleatoriedad cuántica: la batería NIST no distingue origen.",
        cs,
    )


def _v(decl: Declaracion, m: ManifiestoDeCorrida, desenlace: str, resumen: str, cs: list[Criterio]) -> VeredictoDeEureka:
    return VeredictoDeEureka(decl.eureka, m.corrida, desenlace, resumen, tuple(cs), m.preinscripcion_sha, m.commit)
