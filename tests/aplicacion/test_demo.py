"""F7.07: la demo. REAL: pipeline, validador estadístico, AES-GCM, Aer (extra «cuantico»), presentación. Sin red ni credenciales."""

from __future__ import annotations

import json

import pytest

from qrecauda.adaptadores.estadistica import ValidadorEstadistico
from qrecauda.adaptadores.prng import FuentePeriodica, FuentePrng
from qrecauda.aplicacion.demo import ROTULO_REAL, ROTULO_SIMULADO, RamaSolicitada, correr_demo
from qrecauda.aplicacion.pipeline import ParametrosPipeline
from qrecauda.composicion import demo_de, servicio_de
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.presentacion import json_de_demo, tabla_de_demo
from qrecauda.transversal.configuracion import Configuracion


class _Reloj:
    t = 0

    def ahora_ns(self) -> int:
        _Reloj.t += 1_000_000
        return _Reloj.t


P = ParametrosPipeline(8, 40_000)


def _correr(ramas):
    cfg = Configuracion()
    return correr_demo(ramas, ValidadorEstadistico(), _Reloj(), P, lambda r: servicio_de(cfg, r), fuente="aer", rapido=True)


def test_sin_ramas_es_entrada_invalida():
    with pytest.raises(EntradaInvalida):
        _correr([])


def test_una_rama_que_aprueba_cifra_peaje_y_metro_y_descifra():
    d = _correr([RamaSolicitada("prng", FuentePrng(1))])
    assert d.ramas[0].aprobada and d.ramas[0].m1_mitigada is None and d.ramas[0].bits_clave > 0
    assert [t.nombre for t in d.transacciones] == ["peaje", "metro"]
    assert all(t.descifrado_ok and t.bytes_cifrados > 0 for t in d.transacciones)
    assert d.rotulo == ROTULO_SIMULADO == "simulado: Aer es pseudoaleatorio, sin origen cuántico"


def test_si_ninguna_clave_aprueba_no_se_cifra_nada_y_la_tabla_lo_dice():
    d = _correr([RamaSolicitada("periodica", FuentePeriodica("001011"))])
    assert not d.ramas[0].aprobada and d.transacciones == ()
    assert "no se cifra nada" in tabla_de_demo(d)


def test_demo_aer_rapido_es_determinista_con_tres_ramas_y_rotulo():
    cfg = Configuracion(semilla=20261007)
    a, b = demo_de(cfg, rapido=True), demo_de(cfg, rapido=True)
    assert json_de_demo(a) == json_de_demo(b)
    assert len(a.ramas) == 3 and a.ramas[2].m1_mitigada is not None
    assert all(t.descifrado_ok for t in a.transacciones) and len(a.transacciones) == 2
    t = tabla_de_demo(a)
    assert ROTULO_SIMULADO in t and "p mono" in t and "p runs" in t and "p chi2" in t and "AES-256-GCM" in t


def test_json_de_la_demo_trae_rama_origen_y_rotulo():
    d = demo_de(Configuracion(semilla=7), rapido=True)
    j = json.loads(json_de_demo(d))
    assert j["rotulo"] == ROTULO_SIMULADO and j["rapido"] is True
    assert [r["origen"] for r in j["ramas"]][0] == "prng_clasico"
    assert {"m1_cruda", "min_entropia", "p_monobit", "p_runs", "p_chi2", "bits_clave"} <= set(j["ramas"][0])


def test_fuente_ibm_sin_token_se_niega_y_ensayo_sin_ibm_tambien():
    with pytest.raises(FuenteNoDisponible, match="token"):
        demo_de(Configuracion(), rapido=True, fuente="ibm")
    with pytest.raises(EntradaInvalida, match="ensayo"):
        demo_de(Configuracion(), rapido=True, ensayo=True)
    with pytest.raises(EntradaInvalida):
        demo_de(Configuracion(), rapido=True, fuente="otra")


def test_demo_ibm_en_ensayo_anade_dos_ramas_y_dice_que_es_un_ensayo():
    d = demo_de(Configuracion(semilla=20261007), rapido=True, fuente="ibm", ensayo=True)
    assert len(d.ramas) == 5 and d.fuente == "ensayo"
    assert any("ensayo" in a for a in d.avisos)
    assert d.rotulo == ROTULO_SIMULADO  # los bits del ensayo los pone Aer
    assert ROTULO_REAL != ROTULO_SIMULADO


# ------------------------------------------------------------------ R.02: dimensionado, nombres y tope


class _Noventa:
    def __init__(self) -> None:
        self.vistos: list[int] = []

    def estimar(self, bits):  # noqa: ANN001, ANN201
        self.vistos.append(len(bits))
        return 0.9


def test_la_demo_usa_nombres_de_lugares_de_lima():
    from qrecauda.aplicacion.demo import METRO, PEAJE

    assert (PEAJE.estacion, METRO.estacion) == ("Peaje Villa", "Metro Gamarra")


def test_dimensionado_por_omision_es_mcv_y_la_demo_no_cambia():
    assert Configuracion().dimensionado == "mcv"
    cfg = Configuracion(semilla=3)
    assert json_de_demo(demo_de(cfg, rapido=True)) == json_de_demo(demo_de(Configuracion(semilla=3, dimensionado="mcv"), rapido=True))


def test_conservador_con_pocos_bits_lo_dice_y_sugiere_mas_disparos():
    with pytest.raises(EntradaInvalida) as e:
        demo_de(Configuracion(dimensionado="conservador"), rapido=True)  # 8 × 40 000 = 320 000 bits < 1 Mbit
    msg = str(e.value)
    assert "1000000" in msg and "--shots 125000" in msg and "mcv" in msg


def test_conservador_cablea_el_90b_en_el_pipeline_de_la_demo(monkeypatch):
    from qrecauda.adaptadores import min_entropia

    monkeypatch.setattr(min_entropia, "MUESTRAS_MIN", 1000)  # el 90B real exige 1 Mbit; el doble acepta cualquier prefijo
    n90 = _Noventa()
    d = demo_de(Configuracion(semilla=5, dimensionado="conservador"), rapido=True, shots=2000, estimador_90b=n90)
    assert len(d.ramas) == 3 and n90.vistos  # el 90B se consultó (pool, fuente por vistas)
    assert max(n90.vistos) <= 8 * 2000 and 1000 in n90.vistos  # prefijo qubit-mayor (y no la muestra entera) en al menos una vista


@pytest.mark.parametrize("malo", [float("nan"), float("inf"), 1e12, 0.0, -3.0])
def test_la_demo_rechaza_un_tope_de_qpu_que_no_es_finito_positivo_y_razonable(malo):
    with pytest.raises(EntradaInvalida, match="tope"):
        demo_de(Configuracion(), rapido=True, max_segundos_qpu=malo)
