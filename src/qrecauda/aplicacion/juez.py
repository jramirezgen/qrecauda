"""F2.07, «Correr y juzgar»: de la declaración al veredicto, sin que nadie teclee una cifra.

`correr` pide al `Ejecutor` cada semilla DECLARADA y lo escribe por el `Almacen` (append-only) con un manifiesto que cita el
commit de la preinscripción y el de la corrida. `juzgar` relee eso, se niega si la preinscripción no precede a la corrida, si
cambió después o si falta un control, y aplica los criterios de la declaración. Los umbrales de M1…M7 son los de `dominio.metricas`.
Un control que falla no es un «no cumple»: es una corrida inválida, y no hay veredicto (P.E2, P.E3).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping

from qrecauda.datos import (
    Criterio,
    Declaracion,
    ExperimentoE2,
    ExperimentoE3,
    InformeCorrida,
    ManifiestoDeCorrida,
    VeredictoDeEureka,
    serializar,
)
from qrecauda.dominio.errores import CorridaInvalida
from qrecauda.dominio.metricas import Metrica, medir
from qrecauda.puertos import Almacen, Ejecutor, Historial, LibroDeVeredictos

CONTROLES_E2 = ("C1", "C2", "C3")  # C4 (puerta ZNE/PEC) y C5 (contraste) se reportan, no invalidan (P.E2)


def _controles_requeridos(decl: Declaracion) -> tuple[str, ...]:
    if decl.eureka == "E2":
        return CONTROLES_E2
    if decl.eureka == "E3":
        return (*decl.lista("criterios", "t3_controles"), "T4")  # T4: «un hilo» (CPU/pared ≤ 1,10)
    req = decl.tablas.get("controles", {}).get("requeridos", [])
    return tuple(str(x) for x in req) if isinstance(req, list) else ()


class CorrerYJuzgar:
    def __init__(
        self, ejecutor: Ejecutor, almacen: Almacen, historial: Historial, libro: LibroDeVeredictos, entorno: Mapping[str, str]
    ) -> None:
        self._ejecutor, self._almacen, self._historial, self._libro, self._entorno = ejecutor, almacen, historial, libro, entorno

    # ------------------------------------------------------------------ correr

    def correr(self, decl: Declaracion) -> ManifiestoDeCorrida:
        if self._historial.modificado(decl.rutas):
            raise CorridaInvalida(f"la preinscripción de {decl.eureka} tiene cambios sin commit: se fija ANTES de correr")
        pre, commit = self._historial.ultimo_commit(decl.rutas), self._historial.commit_actual()
        artefactos: list[tuple[str, str, str]] = []
        controles: dict[str, bool] = {}
        for semilla in decl.semillas:
            med = self._ejecutor.ejecutar(decl, semilla)
            lotes: tuple[tuple[str, tuple[InformeCorrida | ExperimentoE2 | ExperimentoE3, ...]], ...] = (
                ("informe", med.informes),
                ("e2", med.e2),
                ("e3", med.e3),
            )
            for tipo, lote in lotes:
                for i, a in enumerate(lote):
                    if a.corrida != decl.nodo_corrida and tipo != "informe":
                        raise CorridaInvalida(f"la medición cita la corrida {a.corrida!r}, la declaración es {decl.nodo_corrida!r}")
                    nombre = f"{decl.nodo_corrida}_{semilla}_{tipo}_{i:03d}"
                    artefactos.append((nombre, tipo, self._almacen.guardar(nombre, a.a_mapa())))
            for k, ok in med.controles.items():
                controles[k] = controles.get(k, True) and ok
        if not artefactos:
            raise CorridaInvalida(f"el ejecutor no produjo ningún artefacto para {decl.eureka}")
        manifiesto = ManifiestoDeCorrida(decl.nodo_corrida, decl.eureka, pre, commit, self._entorno, tuple(artefactos), controles)
        self._almacen.guardar(decl.nodo_corrida, manifiesto.a_mapa())  # último: una corrida a medias no deja manifiesto
        return manifiesto

    # ------------------------------------------------------------------ juzgar

    def juzgar(self, decl: Declaracion) -> VeredictoDeEureka:
        try:
            m = ManifiestoDeCorrida.desde_mapa(self._almacen.leer(decl.nodo_corrida))
        except FileNotFoundError as exc:
            raise CorridaInvalida(f"no hay corrida {decl.nodo_corrida!r} que juzgar: primero se corre") from exc
        if m.eureka != decl.eureka:
            raise CorridaInvalida(f"la corrida {m.corrida} es de {m.eureka}, no de {decl.eureka}")
        if not self._historial.precede(m.preinscripcion_sha, m.commit):
            raise CorridaInvalida(f"la preinscripción {m.preinscripcion_sha[:8]} no precede a la corrida {m.commit[:8]} en git")
        if self._historial.ultimo_commit(decl.rutas) != m.preinscripcion_sha:
            raise CorridaInvalida("la preinscripción cambió después de la corrida: no se juzga contra un criterio movido")
        for k in _controles_requeridos(decl):
            if k not in m.controles:
                raise CorridaInvalida(f"falta el control {k}: sin él no hay veredicto")
            if not m.controles[k]:
                raise CorridaInvalida(f"el control {k} falla: corrida inválida, no es un veredicto (incidencia)")
        e2, e3, informes = self._leer(m)
        if decl.eureka == "E2":
            v = _juzgar_e2(decl, m, e2)
        elif decl.eureka == "E3":
            v = _juzgar_e3(decl, m, e3)
        else:
            v = _juzgar_informes(decl, m, informes)
        self._libro.anadir(v.a_mapa())
        return v

    def _leer(self, m: ManifiestoDeCorrida) -> tuple[list[ExperimentoE2], list[ExperimentoE3], list[InformeCorrida]]:
        e2: list[ExperimentoE2] = []
        e3: list[ExperimentoE3] = []
        informes: list[InformeCorrida] = []
        for nombre, tipo, sha in m.artefactos:
            crudo = self._almacen.leer(nombre)
            if hashlib.sha256(serializar(crudo).encode()).hexdigest() != sha:
                raise CorridaInvalida(f"{nombre}: el sha256 no coincide con el del manifiesto: el artefacto cambió")
            if tipo == "e2":
                e2.append(ExperimentoE2.desde_mapa(crudo))
            elif tipo == "e3":
                e3.append(ExperimentoE3.desde_mapa(crudo))
            else:
                informes.append(InformeCorrida.desde_mapa(crudo))
        return e2, e3, informes


# ---------------------------------------------------------------------- criterios


def _veredicto(decl: Declaracion, m: ManifiestoDeCorrida, desenlace: str, resumen: str, cs: list[Criterio]) -> VeredictoDeEureka:
    return VeredictoDeEureka(decl.eureka, m.corrida, desenlace, resumen, tuple(cs), m.preinscripcion_sha, m.commit)


def _juzgar_e3(decl: Declaracion, m: ManifiestoDeCorrida, exps: list[ExperimentoE3]) -> VeredictoDeEureka:
    reps, calent = int(decl.numero("configuracion", "repeticiones")), int(decl.numero("configuracion", "calentamiento"))
    por_semilla = {e.semilla: e for e in exps}
    if set(por_semilla) != set(decl.semillas) or len(exps) != len(decl.semillas):
        raise CorridaInvalida(f"E3 se juzga en las semillas declaradas {decl.semillas}, una vez cada una; hay {sorted(por_semilla)}")
    cs: list[Criterio] = []
    for s in decl.semillas:
        e = por_semilla[s]
        if (e.repeticiones, e.calentamiento) != (reps, calent):
            raise CorridaInvalida(f"semilla {s}: {e.repeticiones}+{e.calentamiento} repeticiones, la declaración pide {reps}+{calent}")
        m6, m7 = medir(Metrica.TASA, e.m6_bits_por_s), medir(Metrica.LATENCIA, e.m7_p95_ms)
        cs.append(Criterio(f"T1/{s}", m6.cumple, f"M6={m6.valor:.6g} bit/s; cociente a umbral {m6.valor / m6.umbral:.2f} (debe ser > 1)"))
        cs.append(Criterio(f"T2/{s}", m7.cumple, f"M7 p95={m7.valor:.6g} ms; cociente a umbral {m7.valor / m7.umbral:.2f} (debe ser < 1)"))
    malos = [c.id for c in cs if not c.cumple]
    if malos:
        return _veredicto(decl, m, "NO_CUMPLE", f"no cumple: {', '.join(malos)}", cs)
    return _veredicto(decl, m, "CUMPLE", "T1–T4 en todas las semillas declaradas", cs)


def _juzgar_e2(decl: Declaracion, m: ManifiestoDeCorrida, celdas: list[ExperimentoE2]) -> VeredictoDeEureka:
    k = {c: decl.numero("criterios_twirling", c) for c in decl.tabla("criterios_twirling")}
    sinteticos = decl.lista("niveles", "sinteticos")
    en_conjuncion = bool(decl.tabla("niveles").get("realista_en_conjuncion", False))
    tecnicas = [t for t in decl.lista("tecnicas", "decide") if t != "ninguna"]
    cs: list[Criterio] = []
    fallos: dict[str, list[ExperimentoE2]] = {}
    nulos, inconclusos = False, False
    for nivel in (*sinteticos, "realista"):
        decide = nivel in sinteticos or en_conjuncion
        propias = {c.semilla: c for c in celdas if c.nivel == nivel and c.tecnica in tecnicas}
        if len(propias) != len([c for c in celdas if c.nivel == nivel and c.tecnica in tecnicas]):
            raise CorridaInvalida(f"nivel {nivel}: más de una celda por semilla")
        if nivel == "realista" and not propias:
            continue  # no medido: se declara, no se inventa
        if nivel in sinteticos and set(propias) != set(decl.semillas):
            raise CorridaInvalida(f"nivel {nivel}: faltan celdas del twirling en las semillas {sorted(set(decl.semillas) - set(propias))}")
        for s in decl.semillas:
            if s not in propias:
                continue
            c = propias[s]
            ok_k1 = medir(Metrica.SESGO, c.sesgo_residual).cumple  # M1 estricto, umbral de dominio.metricas
            lo, hi = c.intervalo_residual
            ok_k2 = hi < k["k2_limite_superior_ic95_menor_que"]
            ok_k3 = c.sesgo_residual <= k["k3_residuo_maximo"]
            hay_que_reducir = c.sesgo_crudo >= k["k4_aplica_desde"]
            factor = math.inf if c.sesgo_residual == 0 else c.sesgo_crudo / c.sesgo_residual
            ok_k4 = (not hay_que_reducir) or factor >= k["k4_factor_minimo"]
            cumple = ok_k1 and ok_k2 and ok_k3 and ok_k4
            detalle = (
                f"residuo={c.sesgo_residual:.6g} IC95=[{lo:.6g}, {hi:.6g}] crudo={c.sesgo_crudo:.6g} "
                f"factor={'∞' if math.isinf(factor) else f'{factor:.3g}'}: K1 {'ok' if ok_k1 else 'FALLA'}, "
                f"K2 {'ok' if ok_k2 else 'FALLA'}, K3 {'ok' if ok_k3 else 'FALLA'}, "
                f"K4 {'ok' if ok_k4 else 'FALLA'}{'' if hay_que_reducir else ' (no aplicable)'}"
            )
            cs.append(Criterio(f"{nivel}/{s}", cumple, detalle, decide))
            if decide and not cumple:
                fallos.setdefault(nivel, []).append(c)
                nulos |= hay_que_reducir and factor < k["nulo_factor_menor_que"]
                inconclusos |= lo < k["k1_sesgo_residual_menor_que"] <= hi
    if nulos:
        return _veredicto(decl, m, "NULO", "resultado negativo: la mitigación de lectura no baja el sesgo en algún nivel", cs)
    if inconclusos:
        return _veredicto(decl, m, "INCONCLUSO", "el IC95 del residuo contiene el umbral M1 en alguna celda", cs)
    if fallos:
        primero = next(n for n in sinteticos if n in fallos) if any(n in fallos for n in sinteticos) else next(iter(fallos))
        return _veredicto(decl, m, "CUMPLE_PARCIAL", f"deja de cumplir en el nivel {primero}", cs)
    return _veredicto(decl, m, "CUMPLE", "K1–K4 en todas las celdas sintéticas", cs)


def _juzgar_informes(decl: Declaracion, m: ManifiestoDeCorrida, informes: list[InformeCorrida]) -> VeredictoDeEureka:
    """Fallback para eurekas sin criterio propio (E1): cada informe, sobre la calidad de la clave (M1–M5), en cada semilla declarada."""
    por_semilla = {i.semilla: i for i in informes}
    if set(por_semilla) != set(decl.semillas):
        raise CorridaInvalida(f"{decl.eureka} se juzga en las semillas declaradas {decl.semillas}; hay {sorted(por_semilla)}")
    cs = []
    for s_ in decl.semillas:
        v = por_semilla[s_].veredicto
        malas = [x.value for x in v.fallos() if x not in (Metrica.TASA, Metrica.LATENCIA)]
        cs.append(Criterio(f"clave/{s_}", v.calidad_de_clave_aprobada, f"fallos de calidad: {malas}"))
    ok = all(c.cumple for c in cs)
    return _veredicto(
        decl, m, "CUMPLE" if ok else "NO_CUMPLE", "M1–M5 en todas las semillas" if ok else "falla M1–M5 en alguna semilla", cs
    )
