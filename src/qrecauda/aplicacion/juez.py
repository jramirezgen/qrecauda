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

from qrecauda.aplicacion import criterios_e1 as e1
from qrecauda.datos import (
    Criterio,
    Declaracion,
    ExperimentoE2,
    ExperimentoE3,
    InformeCorrida,
    ManifiestoDeCorrida,
    MedidaDeFuente,
    VeredictoDeEureka,
    serializar,
)
from qrecauda.dominio.errores import CorridaInvalida
from qrecauda.dominio.metricas import Medida, Metrica, medir
from qrecauda.puertos import Almacen, Ejecutor, Historial, LibroDeVeredictos

CONTROLES_E2 = ("C1", "C2", "C3")  # C4 (puerta ZNE/PEC) y C5 (contraste) se reportan, no invalidan (P.E2)


Artefacto = InformeCorrida | ExperimentoE2 | ExperimentoE3 | MedidaDeFuente


def _corridas_hijas(decl: Declaracion) -> tuple[str, ...]:
    """Las corridas que una declaración reparte bajo su `nodo_corrida` único (E1: C.E1a…C.E1d); () si no declara ninguna."""
    ids = decl.tablas.get("corridas", {}).get("ids")
    return tuple(str(x) for x in ids) if isinstance(ids, list) else ()


def _cita_bien(tipo: str, corrida: str, decl: Declaracion, hijas: tuple[str, ...]) -> bool:
    if corrida == decl.nodo_corrida:
        return True
    if hijas:
        return tipo in ("informe", "fuente") and corrida in hijas
    return tipo == "informe"  # sin corridas declaradas, el informe del respaldo genérico no se valida (comportamiento previo)


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
        por_corrida: dict[str, list[tuple[str, str, str]]] = {}  # la corrida que cita cada artefacto → sus artefactos
        hijas = _corridas_hijas(decl)
        controles: dict[str, bool] = {}
        for semilla in decl.semillas:
            med = self._ejecutor.ejecutar(decl, semilla)
            lotes: tuple[tuple[str, tuple[Artefacto, ...]], ...] = (
                ("informe", med.informes),
                ("e2", med.e2),
                ("e3", med.e3),
                ("fuente", med.fuentes),
            )
            for tipo, lote in lotes:
                for i, a in enumerate(lote):
                    if not _cita_bien(tipo, a.corrida, decl, hijas):
                        raise CorridaInvalida(f"la medición cita la corrida {a.corrida!r}, la declaración es {decl.nodo_corrida!r}")
                    nombre = f"{decl.nodo_corrida}_{semilla}_{tipo}_{i:03d}"
                    entrada = (nombre, tipo, self._almacen.guardar(nombre, a.a_mapa()))
                    artefactos.append(entrada)
                    por_corrida.setdefault(a.corrida, []).append(entrada)
            for k, ok in med.controles.items():
                controles[k] = controles.get(k, True) and ok
        if not artefactos:
            raise CorridaInvalida(f"el ejecutor no produjo ningún artefacto para {decl.eureka}")
        vacias = [c for c in hijas if not por_corrida.get(c)]
        if vacias:
            raise CorridaInvalida(f"la corrida {vacias[0]} declarada no produjo ningún artefacto: el plan exige su ruta propia")
        for hija in hijas:  # las rutas del plan (registro/corridas/E1a.json…): un manifiesto por corrida declarada, ANTES del único
            sub = ManifiestoDeCorrida(hija, decl.eureka, pre, commit, self._entorno, tuple(por_corrida[hija]), controles)
            self._almacen.guardar(hija.removeprefix("C."), sub.a_mapa())
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
        e2, e3, informes, fuentes = self._leer(m)
        if decl.eureka == "E1":
            v = _juzgar_e1(decl, m, informes, fuentes)
        elif decl.eureka == "E2":
            v = _juzgar_e2(decl, m, e2)
        elif decl.eureka == "E3":
            v = _juzgar_e3(decl, m, e3)
        else:
            v = _juzgar_informes(decl, m, informes)
        self._libro.anadir(v.a_mapa())
        return v

    def _leer(self, m: ManifiestoDeCorrida) -> tuple[list[ExperimentoE2], list[ExperimentoE3], list[InformeCorrida], list[MedidaDeFuente]]:
        e2: list[ExperimentoE2] = []
        e3: list[ExperimentoE3] = []
        informes: list[InformeCorrida] = []
        fuentes: list[MedidaDeFuente] = []
        for nombre, tipo, sha in m.artefactos:
            crudo = self._almacen.leer(nombre)
            if hashlib.sha256(serializar(crudo).encode()).hexdigest() != sha:
                raise CorridaInvalida(f"{nombre}: el sha256 no coincide con el del manifiesto: el artefacto cambió")
            if tipo == "e2":
                e2.append(ExperimentoE2.desde_mapa(crudo))
            elif tipo == "e3":
                e3.append(ExperimentoE3.desde_mapa(crudo))
            elif tipo == "fuente":
                fuentes.append(MedidaDeFuente.desde_mapa(crudo))
            else:
                informes.append(InformeCorrida.desde_mapa(crudo))
        return e2, e3, informes, fuentes


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


def _juzgar_e1(
    decl: Declaracion, m: ManifiestoDeCorrida, informes: list[InformeCorrida], fuentes: list[MedidaDeFuente]
) -> VeredictoDeEureka:
    """E1 (docs/preinscripciones/E1.md, con la enmienda 2026-10-07): las cuatro corridas por semilla, la tabla de desenlaces tal cual.

    Precedencia (⚠️ la tabla la deja implícita; se declara): INVÁLIDA (N1/D1/P1 recalculados de los datos) > NULO (B1 falla en alguna
    semilla) > NO CUMPLE (M-2 falla en alguna) > CUMPLE PARCIAL (M-2 pasa en todas y M-1 falla en alguna) > CUMPLE.
    """
    a_id, b_id, c_id, d_id = decl.lista("corridas", "ids")
    esp = {"C.E1a": a_id, "C.E1b": b_id, "C.E1c": c_id}
    por = {(i.corrida, i.semilla): i for i in informes}
    if len(por) != len(informes) or {(k, s) for k in esp.values() for s in decl.semillas} != set(por):
        faltan = sorted({(k, s) for k in esp.values() for s in decl.semillas} - set(por))
        raise CorridaInvalida(
            f"E1 se juzga con una corrida {list(esp.values())} por cada semilla declarada {decl.semillas}; falta o sobra: {faltan}"
        )
    por_f = {(f.semilla, f.fuente): f for f in fuentes}
    if len(por_f) != len(fuentes) or set(por_f) != {(s, k) for s in decl.semillas for k in e1.FUENTES_E1D}:
        raise CorridaInvalida(f"{d_id} se juzga con las fuentes {e1.FUENTES_E1D} en cada semilla declarada {decl.semillas}")
    analitico = decl.numero("ruido", "sesgo_analitico")
    tolerancia = float(decl.tabla("criterios")["c_e1b"]["sesgo_cruda_vs_analitico_tolerancia"])  # type: ignore[index]
    minimo_nist = decl.numero("informativo", "proporcion_nist_minimo")
    cs: list[Criterio] = []
    b1_mal: list[int] = []
    m1_mal: list[tuple[int, str]] = []
    m2_mal: list[tuple[int, str]] = []
    claves_b_pasan = 0
    for s in decl.semillas:
        a, b, c = por[(a_id, s)], por[(b_id, s)], por[(c_id, s)]
        f = {k: por_f[(s, k)] for k in e1.FUENTES_E1D}
        # controles recalculados de los datos: lo que el ejecutor dijo en el manifiesto no se toma de palabra
        if not e1.n1_cumple(a):
            raise CorridaInvalida(
                f"N1 falla en la semilla {s}: la batería rechaza la fuente ideal ({a_id}); los datos desmienten el manifiesto"
            )
        if not e1.d1_cumple(b, analitico, tolerancia):
            raise CorridaInvalida(f"D1 falla en la semilla {s}: el sesgo medido de la cruda no coincide con el inyectado ({b_id})")
        if not e1.p1_cumple(f):
            raise CorridaInvalida(f"P1 falla en la semilla {s}: {[k for k, ok in e1.p1_detalle(f).items() if not ok]} ({d_id})")
        cruda_b = e1.etapa(b, "cruda")
        cs.append(
            Criterio(f"{a_id}/{s}", True, "la cruda pasa M1, M3, M4, M5 y la clave M1–M5 (esperado: no prueba origen cuántico, D-007)")
        )
        cs.append(
            Criterio(f"D1/{s}", True, f"|M1 cruda − {analitico}| = {abs(e1.medida(cruda_b, e1.M1).valor - analitico):.4g} ≤ {tolerancia}")
        )
        cs.append(Criterio(f"P1/{s}", True, "sesgada, periódica y Markov rechazadas; ideal aceptada; MCV de la Markov ≥ 0,9"))
        b1 = e1.b1_cumple(b)
        if not b1:
            b1_mal.append(s)
        cs.append(
            Criterio(
                f"B1/{s}",
                b1,
                f"cruda de {b_id}: M1={e1.medida(cruda_b, e1.M1).valor:.6g}, "
                f"M3 p={e1.medida(cruda_b, e1.M3).valor:.6g} (debe fallar M1 o M3)",
            )
        )
        mit = e1.etapa(c, "mitigada")
        ok1, ok2 = e1.m1_cumple(c), e1.m2_cumple(c)
        cs.append(
            Criterio(f"M-1/{s}", ok1, f"mitigada de {c_id}: M1={e1.medida(mit, e1.M1).valor:.6g}, M3 p={e1.medida(mit, e1.M3).valor:.6g}")
        )
        cs.append(Criterio(f"M-2/{s}", ok2, f"clave de {c_id}: M1–M5; fallan {e1.fallan(c.veredicto.medidas, e1.CLAVE) or 'ninguna'}"))
        if not ok1:
            m1_mal.append((s, ", ".join(e1.fallan(mit, (e1.M1, e1.M3)))))
        if not ok2:
            m2_mal.append((s, ", ".join(e1.fallan(c.veredicto.medidas, e1.CLAVE))))
        cs.extend(_informativos_e1(s, b, c, mit, cruda_b, minimo_nist, b_id, c_id))
        claves_b_pasan += e1.pasan(b.veredicto.medidas, e1.CLAVE)
    hallazgo = f" Hallazgo R.00-1 (no decide): la clave de {b_id} pasa M1–M5 en {claves_b_pasan}/{len(decl.semillas)} semillas."
    if b1_mal:
        extra = f" Además falla M-2 en {[s for s, _ in m2_mal]}." if m2_mal else ""
        return _veredicto(
            decl,
            m,
            "NULO",
            f"B1 falla en las semillas {b1_mal}: el ruido medio no deteriora la cruda al punto de que M1/M3 lo vean; "
            f"E1 no dice nada sobre la mitigación.{extra}{hallazgo}",
            cs,
        )
    if m2_mal:
        quien = "; ".join(f"semilla {s}: {que}" for s, que in m2_mal)
        return _veredicto(
            decl, m, "NO_CUMPLE", f"M-2 falla en la clave de {c_id} ({quien}). No se repite ni se sustituye la semilla.{hallazgo}", cs
        )
    if m1_mal:
        quien = "; ".join(f"semilla {s}: {que}" for s, que in m1_mal)
        return _veredicto(decl, m, "CUMPLE_PARCIAL", f"la clave pasa M1–M5, la mitigada no ({quien}).{hallazgo}", cs)
    return _veredicto(
        decl,
        m,
        "CUMPLE",
        f"el pipeline entrega claves que pasan M1–M5 con entrada ruidosa; esto no certifica origen cuántico.{hallazgo}",
        cs,
    )


def _informativos_e1(
    s: int,
    b: InformeCorrida,
    c: InformeCorrida,
    mit: tuple[Medida, ...],
    cruda_b: tuple[Medida, ...],
    minimo_nist: float,
    b_id: str,
    c_id: str,
) -> list[Criterio]:
    """Lo que E1 reporta y NO decide (`decide=False`): M4/M5 de la mitigada, 90B, proporción NIST, la clave de E1b, M4/M5 de la cruda."""
    ms = {k: e1.medida(mit, k) for k in (e1.M4, e1.M5)}
    out = [
        Criterio(
            f"inf:M4_M5_mitigada/{s}",
            all(x.cumple for x in ms.values()),
            f"mitigada de {c_id}: M4 p={ms[e1.M4].valor:.6g}, M5 p={ms[e1.M5].valor:.6g} (informativas desde la enmienda 2026-10-07)",
            False,
        ),
        Criterio(
            f"inf:M4_M5_cruda_{b_id.lower().replace('.', '_')}/{s}",
            e1.pasan(cruda_b, (e1.M4, e1.M5)),
            f"cruda de {b_id}: M4 p={e1.medida(cruda_b, e1.M4).valor:.6g}, M5 p={e1.medida(cruda_b, e1.M5).valor:.6g}",
            False,
        ),
        Criterio(
            f"inf:clave_{b_id.lower().replace('.', '_')}/{s}",
            e1.pasan(b.veredicto.medidas, e1.CLAVE),
            f"la clave de {b_id} {'pasa' if e1.pasan(b.veredicto.medidas, e1.CLAVE) else 'falla'} M1–M5 (hallazgo R.00-1)",
            False,
        ),
    ]
    rc, rb = c.reporte, b.reporte
    h_cruda_c, h_mit, h_cruda_b = rc.get("h_90b_cruda"), rc.get("h_90b_mitigada"), rb.get("h_90b_cruda")
    umbral = e1.UMBRAL_90B
    ok90 = all(isinstance(h, int | float) and h > umbral for h in (h_cruda_b, h_cruda_c, h_mit))
    out.append(
        Criterio(
            f"inf:90B/{s}",
            ok90,
            f"90B cruda de {b_id}={h_cruda_b}, cruda de {c_id}={h_cruda_c}, mitigada de {c_id}={h_mit}; "
            f"h_min de entrada={c.h_min_entrada:.6g} (umbral {umbral} sólo decide en C.E1d y vía M2)",
            False,
        )
    )
    prop = rc.get("proporcion_nist")
    if isinstance(prop, dict) and prop:
        partes = [f"{k}: {v['aprobados']}/{v['total']}" for k, v in prop.items()]
        ok = all(v["proporcion"] >= minimo_nist for v in prop.values())
        out.append(
            Criterio(
                f"inf:nist_proporcion/{s}",
                ok,
                f"clave de {c_id}, proporción de secuencias que aprueban ({', '.join(partes)}); mínimo {minimo_nist}",
                False,
            )
        )
    else:
        out.append(Criterio(f"inf:nist_proporcion/{s}", False, f"no medida en {c_id}", False))
    sb, sc = b.sha256_muestra_cruda, c.sha256_muestra_cruda
    out.append(
        Criterio(
            f"inf:cruda_igual/{s}",
            sb == sc,
            f"la cruda de {c_id} {'reproduce' if sb == sc else 'NO reproduce'} la de {b_id} (sha256)",
            False,
        )
    )
    return out


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
