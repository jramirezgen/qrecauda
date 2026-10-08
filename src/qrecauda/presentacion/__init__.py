"""Presentación: formatea resultados (JSON canónico, tabla de texto) y NO orquesta nada."""

from __future__ import annotations

from qrecauda.aplicacion.demo import ROTULO_REAL, ROTULO_SIMULADO, ResultadoDemo
from qrecauda.datos import ManifiestoDeCorrida, VeredictoDeEureka, serializar
from qrecauda.dominio.metricas import Veredicto

__all__ = ["json_canonico", "json_de", "json_de_demo", "resumen_de_corrida", "tabla", "tabla_de_demo", "tabla_de_eureka"]


def tabla(veredicto: Veredicto) -> str:
    filas = [f"{'métrica':<18}{'valor':>14}{'umbral':>12}  cumple"]
    filas += [f"{m.metrica.value:<18}{m.valor:>14.6g}{m.umbral:>12.6g}  {'sí' if m.cumple else 'NO'}" for m in veredicto.medidas]
    filas.append(f"VEREDICTO: {'APROBADO' if veredicto.aprobado else 'RECHAZADO ' + ', '.join(m.value for m in veredicto.fallos())}")
    return "\n".join(filas)


def json_canonico(veredicto: Veredicto) -> str:
    """El veredicto como JSON canónico (mismo contenido ⇒ mismos bytes; la serialización es la de `datos`)."""
    return serializar(
        {
            "aprobado": veredicto.aprobado,
            "fallos": [m.value for m in veredicto.fallos()],
            "medidas": [{"metrica": m.metrica.value, "valor": m.valor, "umbral": m.umbral, "cumple": m.cumple} for m in veredicto.medidas],
        }
    )


def json_de(artefacto: ManifiestoDeCorrida | VeredictoDeEureka) -> str:
    """Manifiesto o veredicto de eureka como JSON canónico (lo mismo que se escribe en el registro)."""
    return serializar(artefacto.a_mapa())


def resumen_de_corrida(m: ManifiestoDeCorrida) -> str:
    controles = ", ".join(f"{k}={'ok' if ok else 'FALLA'}" for k, ok in sorted(m.controles.items())) or "ninguno"
    return "\n".join(
        (
            f"CORRIDA {m.corrida} ({m.eureka}): {len(m.artefactos)} artefactos en registro/corridas/",
            f"preinscripción {m.preinscripcion_sha[:8]}  corrida {m.commit[:8]}  controles: {controles}",
        )
    )


def tabla_de_eureka(v: VeredictoDeEureka) -> str:
    filas = [f"{'criterio':<22}  cumple  detalle"]
    filas += [f"{c.id:<22}  {'sí' if c.cumple else 'NO':<6}  {c.detalle}{'' if c.decide else '  (no decide)'}" for c in v.criterios]
    filas.append(f"VEREDICTO {v.eureka} sobre {v.corrida}: {v.desenlace}. {v.resumen}")
    return "\n".join(filas)


def tabla_de_demo(d: ResultadoDemo) -> str:
    """La demo: una fila por fuente (M1 cruda y de la clave, min-entropía, tres p-valores NIST, bits de clave) y las dos transacciones."""
    cab = (
        f"{'fuente':<32}{'M1 cruda':>10}{'M1 mitig':>10}{'M1 clave':>10}{'min-ent':>9}"
        f"{'p mono':>8}{'p runs':>8}{'p chi2':>8}{'bits':>7}  M1-M5"
    )
    filas = [f"QRECAUDA demo  ({d.qubits} qubits, {d.shots} disparos, fuente {d.fuente}{', rápido' if d.rapido else ''})", "", cab]
    for r in d.ramas:
        mitig = "-" if r.m1_mitigada is None else f"{r.m1_mitigada:.4f}"
        filas.append(
            f"{r.nombre:<32}{r.m1_cruda:>10.4f}{mitig:>10}{r.m1_clave:>10.4f}{r.min_entropia:>9.4f}"
            f"{r.p_monobit:>8.3f}{r.p_runs:>8.3f}{r.p_chi2:>8.3f}{r.bits_clave:>7}  {'APRUEBA' if r.aprobada else 'NO APRUEBA'}"
        )
    filas += ["", "Origen de cada fuente:"] + [f"  {r.nombre}: {r.rotulo}" for r in d.ramas]
    if d.transacciones:
        filas += ["", f"AES-256-GCM con la clave de «{d.transacciones[0].rama}»:"]
        for t in d.transacciones:
            filas.append(
                f"  {t.nombre:<6} {t.bytes_cifrados} B cifrados  nonce {t.nonce_hex}  {t.cifrado_hex}  "
                f"descifrado {'OK' if t.descifrado_ok else 'FALLA'}"
                f"  [{t.rotulo}]"
            )
    else:
        filas += ["", "Ninguna clave aprobó M1-M5: no se cifra nada."]
    filas += ["", "Con alfa = 0,01 una clave buena falla alguna de las tres pruebas ~3 % de las veces; la semilla es fija, no elegida."]
    filas += [f"AVISO: {a}" for a in d.avisos]
    filas.append(d.rotulo if d.rotulo == ROTULO_SIMULADO else ROTULO_REAL)
    if d.rotulo == ROTULO_SIMULADO:
        filas.append("(demostración: no es una medición preinscrita ni decide ningún criterio)")
    return "\n".join(filas)


def json_de_demo(d: ResultadoDemo) -> str:
    """La demo como JSON canónico."""
    return serializar(
        {
            "rotulo": d.rotulo,
            "fuente": d.fuente,
            "qubits": d.qubits,
            "shots": d.shots,
            "rapido": d.rapido,
            "avisos": list(d.avisos),
            "ramas": [
                {
                    "nombre": r.nombre,
                    "origen": r.origen.value,
                    "rotulo": r.rotulo,
                    "m1_cruda": r.m1_cruda,
                    "m1_mitigada": r.m1_mitigada,
                    "m1_clave": r.m1_clave,
                    "min_entropia": r.min_entropia,
                    "p_monobit": r.p_monobit,
                    "p_runs": r.p_runs,
                    "p_chi2": r.p_chi2,
                    "bits_clave": r.bits_clave,
                    "aprobada": r.aprobada,
                }
                for r in d.ramas
            ],
            "transacciones": [
                {
                    "nombre": t.nombre,
                    "rama": t.rama,
                    "bytes_cifrados": t.bytes_cifrados,
                    "descifrado_ok": t.descifrado_ok,
                    "rotulo": t.rotulo,
                }
                for t in d.transacciones
            ],
        }
    )
