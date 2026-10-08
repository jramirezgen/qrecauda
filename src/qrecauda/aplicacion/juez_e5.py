"""El criterio de E5 (docs/preinscripciones/E5.md) aplicado a los artefactos releídos.

Por semilla, con el dimensionado que DECIDE (`conservador`):
- D/<fuente>  cada fuente defectuosa es RECHAZADA (sin clave, o clave que no pasa M1–M5) o ACORTADA (aprueba y cumple K1 y K2).
- G1, G2, G3  la fuente buena entrega clave que pasa M1–M5, con ≥ 0,75 de los bits del dimensionado de 0.1.0 y con M6
  estrictamente > umbral.
Conjunción: un solo fallo es NO_CUMPLE. Un control (D5, P5) que se recalcula y falla no es un desenlace: es `CorridaInvalida`.
Se REPORTAN, sin decidir: lo que hace HOY el dimensionado de 0.1.0 (R.00-1 en la cadena completa), `min_mcv_90b` frente al techo K1 y
el efecto de cada dimensionado sobre M6 de la fuente buena.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from qrecauda.aplicacion import criterios_e5 as c
from qrecauda.datos import Criterio, Declaracion, ExperimentoE5, ManifiestoDeCorrida, VeredictoDeEureka
from qrecauda.dominio.errores import CorridaInvalida
from qrecauda.dominio.metricas import Metrica, medir


def _techo(decl: Declaracion, e: ExperimentoE5) -> int:
    d = decl.tabla("defectos")[e.fuente]
    if not isinstance(d, Mapping):
        raise CorridaInvalida(f"[defectos.{e.fuente}] no es una tabla: no hay techo K1")
    return c.techo_k1(e.bits_crudos, float(d["peso"]), decl.numero("defectos", "p_fresca_max"))


def _coherente(decl: Declaracion, e: ExperimentoE5, prefijo: int) -> None:
    """Lo medido se hizo con los parámetros declarados: no se juzga contra un criterio ni un defecto movidos."""
    esperado: dict[str, object] = {"prefijo_90b": prefijo, "p_fresca_max": decl.numero("defectos", "p_fresca_max")}
    if e.fuente == "buena":
        esperado["tipo"] = "ninguno"
    else:
        d = decl.tabla("defectos")[e.fuente]
        if not isinstance(d, Mapping):
            raise CorridaInvalida(f"[defectos.{e.fuente}] no es una tabla")
        esperado.update({k: v for k, v in d.items() if isinstance(v, str | int | float)})
    if dict(e.parametros) != esperado:
        raise CorridaInvalida(f"{e.fuente}/{e.semilla}: parámetros medidos {dict(e.parametros)} ≠ declarados {esperado}")
    if e.bits_crudos != decl.qubits * decl.shots:
        raise CorridaInvalida(f"{e.fuente}/{e.semilla}: {e.bits_crudos} bits crudos ≠ qubits·shots de la declaración")


def juzgar_e5(decl: Declaracion, m: ManifiestoDeCorrida, exps: list[ExperimentoE5]) -> VeredictoDeEureka:
    fuentes, defectuosas = decl.lista("fuentes", "ids"), decl.lista("fuentes", "defectuosas")
    dims, decide = decl.lista("dimensionados", "ids"), str(decl.tabla("dimensionados")["decide"])
    prefijo = int(decl.numero("dimensionados", "prefijo_90b"))
    por = {(e.semilla, e.fuente): e for e in exps}
    esperadas = {(s, f) for s in decl.semillas for f in fuentes}
    if set(por) != esperadas or len(exps) != len(esperadas):
        raise CorridaInvalida(f"E5 se juzga con {list(fuentes)} en cada semilla declarada {decl.semillas}, una vez cada una")
    for e in exps:
        _coherente(decl, e, prefijo)
        if sorted(str(r["dimensionado"]) for r in e.resultados) != sorted(dims):
            raise CorridaInvalida(f"{e.fuente}/{e.semilla}: los dimensionados medidos no son los declarados {list(dims)}")
    crit = decl.tabla("controles")
    if not c.p5_cumple(exps):
        raise CorridaInvalida("P5 falla al recalcularse: los dimensionados no partieron de la misma muestra; corrida inválida")
    if not c.d5_cumple(exps, float(crit["d5_techo_90b_defectuosa"]), float(crit["d5_piso_90b_buena"]), defectuosas):  # type: ignore[arg-type]
        raise CorridaInvalida("D5 falla al recalcularse: el 90B no distingue la muestra defectuosa de la buena; corrida inválida")
    k2_frac = float(decl.tabla("criterios")["defectuosas"]["k2_fraccion_maxima_de_la_buena"])  # type: ignore[index]
    g2_frac = float(decl.tabla("criterios")["buena"]["g2_fraccion_minima_de_mcv"])  # type: ignore[index]
    umbral_m6 = medir(Metrica.TASA, 0.0).umbral

    cs: list[Criterio] = []
    for s in decl.semillas:
        buena = por[(s, "buena")]
        rb, rm = c.resultado_de(buena, decide), c.resultado_de(buena, "mcv")
        if c.entregada(rb):
            seg, tasa = float(rb["segundos"]), c.tasa_bps(rb)  # type: ignore[arg-type]
            if not math.isclose(tasa, float(rb["tasa_bps"]), rel_tol=1e-9):  # type: ignore[arg-type]
                raise CorridaInvalida(f"buena/{s}: la tasa guardada no es bits de clave / segundos")
        else:
            seg, tasa = math.nan, 0.0
        cs.append(
            Criterio(
                f"G1/{s}",
                c.aprobada(rb),
                f"la fuente buena con {decide}: {c.bits_de_clave(rb)} bits de clave; M1–M5 {'pasan' if c.aprobada(rb) else 'NO pasan'}",
            )
        )
        cs.append(
            Criterio(
                f"G2/{s}",
                c.g2(rb, rm, g2_frac),
                f"{c.bits_de_clave(rb)} bits con {decide} frente a {c.bits_de_clave(rm)} con mcv: fracción "
                f"{c.bits_de_clave(rb) / max(c.bits_de_clave(rm), 1):.4f} (mínimo {g2_frac})",
            )
        )
        cs.append(
            Criterio(
                f"G3/{s}",
                c.entregada(rb) and medir(Metrica.TASA, tasa).cumple,
                f"M6 de la cadena entera = {tasa:.6g} bit/s en {seg:.4g} s (umbral {umbral_m6:.6g}, estricto)",
            )
        )
        for f in defectuosas:
            e = por[(s, f)]
            r = c.resultado_de(e, decide)
            techo = _techo(decl, e)
            rech = c.rechazada(r)
            ok = rech or c.acortada(r, techo, c.bits_de_clave(rb), k2_frac)
            cs.append(
                Criterio(
                    f"D/{f}/{s}",
                    ok,
                    f"{f} con {decide}: {'RECHAZADA' if rech else 'entrega'} {c.bits_de_clave(r)} bits (techo K1 {techo}: "
                    f"{'cumple' if c.k1(r, techo) else 'SUPERA'}; K2 ≤ {k2_frac}·{c.bits_de_clave(rb)}: "
                    f"{'cumple' if c.k2(r, c.bits_de_clave(rb), k2_frac) else 'NO cumple'})",
                )
            )
        cs.extend(_informativos(decl, s, por, dims, defectuosas, k2_frac))
    malos = [x.id for x in cs if x.decide and not x.cumple]
    if malos:
        return VeredictoDeEureka(
            decl.eureka, m.corrida, "NO_CUMPLE", f"no cumple: {', '.join(malos)}", tuple(cs), m.preinscripcion_sha, m.commit
        )
    resumen = "D, G1, G2 y G3 en todas las semillas declaradas (D5 y P5 pasaron como controles)"
    return VeredictoDeEureka(decl.eureka, m.corrida, "CUMPLE", resumen, tuple(cs), m.preinscripcion_sha, m.commit)


def _informativos(
    decl: Declaracion,
    s: int,
    por: Mapping[tuple[int, str], ExperimentoE5],
    dims: tuple[str, ...],
    defectuosas: tuple[str, ...],
    k2_frac: float,
) -> list[Criterio]:
    """Lo que se reporta y NO decide (`decide=False`): R.00-1 con cada dimensionado y el efecto sobre M6 de la fuente buena."""
    out: list[Criterio] = []
    for d in dims:
        if d == str(decl.tabla("dimensionados")["decide"]):
            continue
        entrega = [f for f in defectuosas if c.aprobada(c.resultado_de(por[(s, f)], d))]
        sobre = [f for f in defectuosas if not c.k1(c.resultado_de(por[(s, f)], d), _techo(decl, por[(s, f)]))]
        bits = {f: c.bits_de_clave(c.resultado_de(por[(s, f)], d)) for f in defectuosas}
        out.append(
            Criterio(
                f"HOY/{d}/{s}",
                not sobre,
                f"con {d}: claves que pasan M1–M5 {entrega or 'ninguna'}; por encima del techo K1 {sobre or 'ninguna'}; bits {bits}",
                decide=False,
            )
        )
    for d in dims:
        r = c.resultado_de(por[(s, "buena")], d)
        out.append(
            Criterio(
                f"M6/{d}/{s}",
                c.entregada(r),
                f"fuente buena con {d}: {c.bits_de_clave(r)} bits, M6 = {c.tasa_bps(r):.6g} bit/s (M7 no se mide aquí)"
                if c.entregada(r)
                else f"fuente buena con {d}: rechazada",
                decide=False,
            )
        )
    return out
