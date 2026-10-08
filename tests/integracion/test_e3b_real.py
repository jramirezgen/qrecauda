"""C.E3b con las piezas REALES (proceso productor `spawn`, Aer, twirling, Peres, Toeplitz, M1–M5, 90B, AES-GCM) y demanda DIMINUTA.

No es la corrida: C.E3b la lanza quien dirige el plan, con la máquina quieta. Esto prueba el cableado de punta a punta; las cifras
de aquí no valen como resultado (20 transacciones, núcleos elegidos entre los permitidos, sin exigir carga previa).
"""

import os
from dataclasses import replace
from pathlib import Path

import pytest

from qrecauda import composicion
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.dominio.errores import CorridaInvalida

RAIZ = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.lento


def _diminuta_e3b(**config):
    d = cargar_declaracion(Path("declaraciones/E3b.toml"), RAIZ)
    t = {k: dict(v) for k, v in d.tablas.items()}
    libres = sorted(os.sched_getaffinity(0))
    if len(libres) < 2:
        pytest.skip("E3b necesita dos núcleos permitidos")
    t["configuracion"].update({"carga_previa_maxima": 1e9, "nucleo_consumidor": libres[0], "nucleo_productor": libres[-1]} | config)
    t["demanda"].update(tx_por_s=100, duracion_s=0.2, transacciones=20, consumo_bps=35200)
    return replace(d, shots=125_000, tablas=t)  # 8 × 125 000 = 1 M de bits: el mínimo del 90B


def test_e3b_exige_omp_num_threads_1_antes_de_medir(tmp_path, monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "8")
    d = _diminuta_e3b()
    with pytest.raises(CorridaInvalida, match="OMP_NUM_THREADS"):
        composicion.ejecutor_e3b_de(tmp_path).ejecutar(d, d.semillas[0])


def test_e3b_exige_dos_nucleos_distintos(tmp_path, monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    libres = sorted(os.sched_getaffinity(0))
    d = _diminuta_e3b(nucleo_consumidor=libres[0], nucleo_productor=libres[0])
    with pytest.raises(CorridaInvalida, match="dos núcleos distintos"):
        composicion.ejecutor_e3b_de(tmp_path).ejecutar(d, d.semillas[0])


def test_e3b_exige_nucleos_permitidos(tmp_path, monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    d = _diminuta_e3b(nucleo_productor=10_000)
    with pytest.raises(CorridaInvalida, match="no están entre los permitidos"):
        composicion.ejecutor_e3b_de(tmp_path).ejecutar(d, d.semillas[0])


def test_e3b_real_con_demanda_diminuta_recorre_la_cadena_con_el_productor_aparte(tmp_path, monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    d = _diminuta_e3b()
    m = composicion.ejecutor_e3b_de(tmp_path).ejecutar(d, d.semillas[0])
    (e,) = m.e3b
    assert (e.corrida, e.transacciones) == ("C.E3b", 20)
    assert set(m.controles) == {"U1", "U2", "U3", "U4", "U5", "T4"}
    assert all(m.controles[k] for k in ("U1", "U2", "U3", "U4", "U5")), m.controles
    r = e.reporte
    assert r["afinidad"]["consumidor"] == [d.numero("configuracion", "nucleo_consumidor")]
    assert r["afinidad"]["productor"] == [d.numero("configuracion", "nucleo_productor")] or r["afinidad"]["productor"] == [
        int(d.numero("configuracion", "nucleo_productor"))
    ]
    assert r["arranque"]["bits"] >= 352 and e.arranque_ms > 0 and r["rotulos"] == ["validación del pipeline"]
    assert (tmp_path / "salidas" / "candado_maquina.lock").exists()


def test_ejecutor_de_elige_el_de_e3b(tmp_path):
    d = cargar_declaracion(Path("declaraciones/E3b.toml"), RAIZ)
    assert type(composicion.ejecutor_de(tmp_path, d)).__name__ == "_EnMaquina"
