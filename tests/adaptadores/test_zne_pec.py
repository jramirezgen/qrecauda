"""F4.02: ZNE y PEC sobre el observable ⟨Z⟩ con Aer ruidoso (D-003, D-009). Sin red ni credenciales.

Convención: ⟨Z⟩ = 1 − 2·p1, promediado sobre qubits. Ideal tras H: 0. Relajación en la puerta H (T1 > 0): ⟨Z⟩ = 1 − e^(−t/T1) > 0.
Los dos ruidos del test son SINTÉTICOS (no medidos en hardware): relajación de puerta (donde ZNE/PEC tienen sentido) y lectura
(donde D-009 dice que no mueven nada).
"""

from __future__ import annotations

import numpy as np
import pytest

from qrecauda.adaptadores.aer import FuenteAer
from qrecauda.adaptadores.aer.ruido import RUIDO_BAJO, RUIDO_MEDIO, CanalLectura, modelo_de_ruido
from qrecauda.adaptadores.zne_pec import (
    Efecto,
    PecSobreZ,
    RelajacionConocida,
    ReporteSesgo,
    Tecnica,
    ZneSobreZ,
    descomposicion_inversa,
)
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Muestra, Origen
from qrecauda.puertos import EstimadorDeSesgo

QUBITS, SHOTS = 4, 20_000
RELAJ = RelajacionConocida(t1_us=10.0, t2_us=10.0, tiempo_puerta_ns=1000.0)  # b = e^-0.1
Z_ANALITICO = 1 - float(np.exp(-0.1))  # ⟨Z⟩ tras una H con relajación, ≈ 0.0952
SIN_LECTURA = CanalLectura(0.0, 0.0)


def _z(m: Muestra) -> float:
    return 1 - 2 * m.bits.proporcion_de_unos()


def _ruido_puerta():
    return modelo_de_ruido(SIN_LECTURA, t1_us=10.0, t2_us=10.0, tiempo_puerta_ns=1000.0)


def _cruda(nm, semilla: int = 5) -> Muestra:
    return FuenteAer(semilla=semilla, noise_model=nm).generar(QUBITS, SHOTS)


def test_implementan_el_puerto() -> None:
    nm = _ruido_puerta()
    zne: EstimadorDeSesgo = ZneSobreZ(nm, semilla=1)
    pec: EstimadorDeSesgo = PecSobreZ(nm, RELAJ, semilla=1)
    cruda = _cruda(nm)
    assert isinstance(zne.estimar(cruda), float)
    assert isinstance(pec.estimar(cruda), float)


def test_descomposicion_inversa_recompone_la_identidad() -> None:
    q = descomposicion_inversa(RELAJ)
    assert sum(q.values()) == pytest.approx(1.0)
    assert sum(abs(v) for v in q.values()) > 1.0  # γ > 1: el coste de PEC
    # PTM sobre (I, X, Y, Z) de cada operación base y del canal de relajación
    e_zi = np.zeros((4, 4))
    e_zi[3, 0] = 1.0
    ptm = {
        "I": np.diag([1, 1, 1, 1.0]),
        "X": np.diag([1, 1, -1, -1.0]),
        "Y": np.diag([1, -1, 1, -1.0]),
        "Z": np.diag([1, -1, -1, 1.0]),
        "R0": np.diag([1, 0, 0, 0.0]) + e_zi,
        "R1": np.diag([1, 0, 0, 0.0]) - e_zi,
    }
    b = float(np.exp(-0.1))
    canal = np.diag([1, b, b, b]) + (1 - b) * e_zi  # T2 = T1
    inversa = sum(q[k] * ptm[k] for k in q)
    assert inversa @ canal == pytest.approx(np.eye(4), abs=1e-12)


def test_zne_reduce_el_sesgo_de_puerta() -> None:
    nm = _ruido_puerta()
    cruda = _cruda(nm)
    assert _z(cruda) > 0.08  # relajación: ≈ 0.095
    rep = ZneSobreZ(nm, semilla=1).reportar(cruda)
    assert isinstance(rep, ReporteSesgo) and rep.tecnica is Tecnica.ZNE
    assert abs(rep.z_mitigado) < 0.02
    assert rep.efecto is Efecto.CORRIGE
    assert [f for f, _ in rep.valores_por_factor] == [1, 3, 5]
    zs = [z for _, z in rep.valores_por_factor]
    assert zs[0] < zs[1] < zs[2]  # más plegado, más ruido


def test_zne_escala_ingenua_deja_la_mitad() -> None:
    nm = _ruido_puerta()
    cruda = _cruda(nm)
    efectiva = ZneSobreZ(nm, semilla=1).reportar(cruda)
    ingenua = ZneSobreZ(nm, semilla=1, escala="ingenua").reportar(cruda)
    assert abs(efectiva.z_mitigado) < 0.02
    assert ingenua.z_mitigado > 0.04  # extrapolar a λ=0 en vez de s=0: queda ≈ la mitad del sesgo


def test_pec_elimina_el_sesgo_de_puerta() -> None:
    nm = _ruido_puerta()
    cruda = _cruda(nm)
    rep = PecSobreZ(nm, RELAJ, semilla=1).reportar(cruda)
    assert rep.tecnica is Tecnica.PEC and rep.efecto is Efecto.CORRIGE
    assert rep.gamma is not None and rep.gamma > 1.0
    assert abs(rep.z_mitigado) < 4 * rep.error_estandar + 0.01
    assert abs(rep.z_mitigado) < abs(rep.z_crudo) / 3


def test_el_reporte_trae_el_crudo_y_el_mitigado() -> None:
    nm = _ruido_puerta()
    cruda = _cruda(nm)
    rep = ZneSobreZ(nm, semilla=1).reportar(cruda)
    assert rep.z_crudo == pytest.approx(_z(cruda))
    assert rep.error_estandar > 0
    assert ZneSobreZ(nm, semilla=1).estimar(cruda) == rep.z_mitigado


def test_puerta_zne_y_pec_sin_efecto_contra_ruido_de_lectura() -> None:
    """Corrida de puerta (D-009): con ruido SOLO de lectura, ni el plegado de puertas ni el perfil de puerta lo tocan."""
    nm = modelo_de_ruido(RUIDO_MEDIO)  # sesgo analítico de lectura: ⟨Z⟩ = +0.06 (p(1|0) < p(0|1))
    cruda = _cruda(nm)
    assert _z(cruda) > 0.045
    zne = ZneSobreZ(nm, semilla=1).reportar(cruda)
    assert zne.efecto is Efecto.SIN_EFECTO_ESPERADO
    assert zne.z_mitigado == pytest.approx(zne.z_crudo, abs=0.015)  # el sesgo sigue ahí
    assert zne.z_mitigado > 0.04
    pec = PecSobreZ(nm, None, semilla=1).reportar(cruda)
    assert pec.efecto is Efecto.SIN_EFECTO_ESPERADO and pec.gamma == 1.0
    assert pec.z_mitigado == pytest.approx(pec.z_crudo, abs=0.015)
    assert pec.z_mitigado > 0.04


def test_sin_ruido_apreciable_no_inventa_efecto() -> None:
    nm = modelo_de_ruido(RUIDO_BAJO)
    rep = ZneSobreZ(nm, semilla=1).reportar(_cruda(nm))
    assert rep.efecto is Efecto.SIN_EFECTO_ESPERADO


def test_determinista_por_semilla() -> None:
    nm = _ruido_puerta()
    cruda = _cruda(nm)
    assert ZneSobreZ(nm, semilla=3).reportar(cruda) == ZneSobreZ(nm, semilla=3).reportar(cruda)
    assert PecSobreZ(nm, RELAJ, semilla=3).reportar(cruda) == PecSobreZ(nm, RELAJ, semilla=3).reportar(cruda)


def test_entradas_invalidas() -> None:
    nm = _ruido_puerta()
    cruda = _cruda(nm)
    for malos in ((1, 2), (), (1, 1), (0, 3), (-1, 3)):
        with pytest.raises(EntradaInvalida):
            ZneSobreZ(nm, factores=malos)
    with pytest.raises(EntradaInvalida):
        ZneSobreZ(nm, extrapolacion="cubica")  # type: ignore[arg-type]
    with pytest.raises(EntradaInvalida):
        ZneSobreZ(nm, escala="rara")  # type: ignore[arg-type]
    with pytest.raises(EntradaInvalida):
        PecSobreZ(nm, RELAJ, circuitos=0)
    with pytest.raises(EntradaInvalida):
        RelajacionConocida(t1_us=10.0, t2_us=30.0, tiempo_puerta_ns=100.0)  # T2 > 2·T1
    mitigada = cruda.mitigada_con(cruda.bits, conserva_bits_por_disparo=True)
    prng = Muestra(Bits(np.zeros(8, dtype=np.uint8)), Origen.PRNG_CLASICO, 1, 8)
    for est in (ZneSobreZ(nm), PecSobreZ(nm, RELAJ)):
        with pytest.raises(EntradaInvalida):
            est.reportar(mitigada)
        with pytest.raises(EntradaInvalida):
            est.reportar(prng)
