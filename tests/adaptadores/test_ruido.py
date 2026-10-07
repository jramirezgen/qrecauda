"""F3.02: canal de lectura como matriz de confusión; el sesgo inyectado coincide con el medido."""

from __future__ import annotations

import math

import numpy as np
import pytest
from qiskit import QuantumCircuit

from qrecauda.adaptadores.aer import FuenteAer
from qrecauda.adaptadores.aer.ruido import (
    NIVELES,
    RUIDO_ALTO,
    RUIDO_BAJO,
    RUIDO_MEDIO,
    CanalLectura,
    modelo_de_ruido,
    modelo_realista,
)
from qrecauda.dominio.errores import EntradaInvalida

SHOTS = 125_000
QUBITS = 4  # 500 000 bits por muestra


def test_matriz_de_confusion_y_sesgo_analitico() -> None:
    c = CanalLectura(p1_dado_0=0.02, p0_dado_1=0.08)
    assert np.allclose(c.matriz(), [[0.98, 0.02], [0.08, 0.92]])
    assert np.allclose(c.matriz().sum(axis=1), 1.0)
    assert c.sesgo_analitico() == pytest.approx(-0.03)  # p(1) = 0.47 sobre H uniforme (S.02: |sesgo| 0.0300)


def test_niveles_ordenados_y_con_nombre() -> None:
    assert NIVELES == {"bajo": RUIDO_BAJO, "medio": RUIDO_MEDIO, "alto": RUIDO_ALTO}
    s = [abs(n.sesgo_analitico()) for n in (RUIDO_BAJO, RUIDO_MEDIO, RUIDO_ALTO)]
    assert s == sorted(s) and len(set(s)) == 3


@pytest.mark.parametrize("p", [(-0.1, 0.0), (0.0, 1.5)])
def test_canal_invalido(p: tuple[float, float]) -> None:
    with pytest.raises(EntradaInvalida):
        CanalLectura(*p)


@pytest.mark.parametrize("nombre", ["bajo", "medio", "alto"])
def test_sesgo_inyectado_coincide_con_el_medido(nombre: str) -> None:
    canal = NIVELES[nombre]
    m = FuenteAer(semilla=2026, noise_model=modelo_de_ruido(canal)).generar(QUBITS, SHOTS)
    n = len(m.bits)
    medido = m.bits.proporcion_de_unos() - 0.5
    esperado = canal.sesgo_analitico()
    sigma = math.sqrt(0.25 / n)
    assert abs(medido - esperado) < 4 * sigma, (nombre, medido, esperado, sigma)
    # el sesgo del nivel alto es detectable (>>σ); el del bajo puede no serlo, así que sólo se exige para alto
    if nombre == "alto":
        assert abs(medido) > 10 * sigma


def test_matriz_medida_sobre_estados_base() -> None:
    """Mide cada fila de la matriz: |0> sin puertas da p(1|0); |1> con X da p(0|1)."""
    canal = RUIDO_ALTO
    nm = modelo_de_ruido(canal)
    fuente = FuenteAer(semilla=5, noise_model=nm)
    cero = QuantumCircuit(1)
    cero.measure_all()
    uno = QuantumCircuit(1)
    uno.x(0)
    uno.measure_all()
    p10 = fuente._muestrear(cero, 200_000).mean()
    p01 = 1.0 - fuente._muestrear(uno, 200_000).mean()
    for medido, real in ((p10, canal.p1_dado_0), (p01, canal.p0_dado_1)):
        assert abs(medido - real) < 4 * math.sqrt(real * (1 - real) / 200_000)


def test_misma_semilla_con_ruido_es_determinista() -> None:
    nm = modelo_de_ruido(RUIDO_MEDIO)
    a = FuenteAer(semilla=9, noise_model=nm).generar(3, 500).bits
    assert a == FuenteAer(semilla=9, noise_model=nm).generar(3, 500).bits


def test_relajacion_opcional_construye_y_corre() -> None:
    nm = modelo_de_ruido(RUIDO_BAJO, t1_us=100.0, t2_us=80.0, tiempo_puerta_ns=50.0)
    assert "h" in nm.noise_instructions
    FuenteAer(semilla=1, noise_model=nm).generar(2, 100)


def test_relajacion_fisicamente_imposible() -> None:
    with pytest.raises(EntradaInvalida):
        modelo_de_ruido(RUIDO_BAJO, t1_us=10.0, t2_us=30.0, tiempo_puerta_ns=50.0)  # T2 > 2·T1


def test_nivel_realista_desde_backend_falso() -> None:
    nm = modelo_realista()
    assert nm.noise_instructions  # hay errores de puerta y de lectura tomados del backend falso
    assert "measure" in nm.noise_instructions
    FuenteAer(semilla=1, noise_model=nm).generar(2, 100)
