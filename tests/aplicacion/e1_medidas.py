"""Medidas e informes sintéticos de E1 para probar criterios y juez sin correr nada (valores a mano, umbrales de dominio.metricas)."""

from __future__ import annotations

from qrecauda.datos import InformeCorrida, MedidaDeFuente
from qrecauda.dominio.metricas import Metrica, Veredicto, medir
from qrecauda.dominio.muestra import Origen, Procedencia

BUENA = {"m1": 0.001, "m3": 0.5, "m4": 0.5, "m5": 0.5}  # pasa M1, M3, M4, M5
SESGADA = {"m1": 0.03, "m3": 0.0, "m4": 0.0, "m5": 0.0}  # sesgo inyectado de E1: falla todo


def medidas(m1=0.001, m3=0.5, m4=0.5, m5=0.5):
    return (
        medir(Metrica.SESGO, m1),
        medir(Metrica.MONOBIT, m3),
        medir(Metrica.RUNS, m4),
        medir(Metrica.CHI2, m5),
    )


def informe(corrida, semilla, *, cruda, clave=None, mitigada=None, m2=0.99, reporte=None, aer=True):
    etapas = {"cruda": medidas(**cruda)}
    if mitigada is not None:
        etapas["mitigada"] = medidas(**mitigada)
    en_clave = medidas(**(clave or BUENA))
    etapas["clave"] = en_clave
    return InformeCorrida(
        corrida=corrida, eureka="E1", semilla=semilla, origen=Origen.SIMULADOR_AER if aer else Origen.PRNG_CLASICO,
        procedencia=Procedencia("x", "", "1"), qubits=8, shots=1000, mitigada=mitigada is not None, epsilon=2.0**-64,
        profundidad_peres=8, validador="nist", estimador="mcv", h_min_entrada=0.97, h_min_salida=m2, bits_crudos=8000,
        bits_clave=2000, sha256_muestra_cruda="0" * 64, etapas=etapas,
        veredicto=Veredicto((*en_clave, medir(Metrica.MIN_ENTROPIA, m2))), preinscripcion_sha="a" * 40, commit="b" * 40,
        reporte=reporte or {},
    )  # fmt: skip


def fuente(corrida, semilla, nombre, *, cruda, mcv, h90):
    return MedidaDeFuente(corrida, semilla, nombre, 1_000_000, medidas(**cruda), mcv, h90)


def fuentes_ok(semilla, corrida="C.E1d"):
    """Las cuatro fuentes de C.E1d con valores que cumplen P1 (los del precedente S.04 en espíritu)."""
    return (
        fuente(corrida, semilla, "sesgada", cruda=SESGADA, mcv=0.5, h90=0.4),
        fuente(corrida, semilla, "periodica", cruda={**BUENA, "m4": 0.0}, mcv=0.99, h90=0.0),
        fuente(corrida, semilla, "markov", cruda={**BUENA, "m4": 0.0, "m5": 0.0}, mcv=0.99, h90=0.17),
        fuente(corrida, semilla, "ideal", cruda=BUENA, mcv=0.99, h90=0.95),
    )
