"""C.E1 con las piezas REALES (Aer, twirling, NIST, PRNG, fuentes de control) y parámetros DIMINUTOS. El 90B es un doble: el real
exige ≥ 1 M de bits por llamada y cuesta minutos. NO es la corrida: C.E1 la lanza quien dirige el plan; nada aquí escribe en registro/.
Las cifras de estas pruebas (pocos disparos) no valen como resultado.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from qrecauda import composicion
from qrecauda.adaptadores.declaracion_toml import cargar_declaracion
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import FuenteNoDisponible

RAIZ = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.lento


class HistorialFalso:
    def ultimo_commit(self, rutas):
        return "a" * 40

    def commit_actual(self):
        return "b" * 40


class Estimador90bFalso:
    def estimar(self, bits: Bits) -> float:
        return 0.97 if abs(bits.proporcion_de_unos() - 0.5) < 0.05 else 0.2


def _diminuta():
    d = cargar_declaracion(Path("declaraciones/E1.toml"), RAIZ)
    t = {k: dict(v) for k, v in d.tablas.items()}
    t["criterios"] = {k: dict(v) for k, v in d.tablas["criterios"].items()}  # type: ignore[attr-defined]
    t["criterios"]["c_e1d"]["bits"] = 30_000
    return replace(d, shots=3000, tablas=t)


def test_e1_real_con_parametros_diminutos_mide_las_cuatro_corridas(tmp_path):
    d = _diminuta()
    m = composicion.ejecutor_e1_de(tmp_path, estimador_90b=Estimador90bFalso(), historial=HistorialFalso()).ejecutar(d, d.semillas[0])
    assert [i.corrida for i in m.informes] == ["C.E1a", "C.E1b", "C.E1c"]
    assert [f.fuente for f in m.fuentes] == ["sesgada", "periodica", "markov", "ideal"]
    a, b, c = m.informes
    assert a.origen.value == "prng_clasico" and b.origen.value == "simulador_aer" and c.mitigada and not b.mitigada
    assert b.sha256_muestra_cruda == c.sha256_muestra_cruda  # ⚠️ abierto 3 de E1.md: el Aer es determinista dada la semilla
    assert all(any(x.metrica.value == "M1_sesgo" for x in ms) for i in m.informes for ms in i.etapas.values())  # NIST no trae M1
    m1_b = next(x for x in b.etapas["cruda"] if x.metrica.value == "M1_sesgo")
    assert 0.02 < m1_b.valor < 0.04 and not m1_b.cumple  # el sesgo analítico 0,030 se ve incluso con 24 000 bits
    assert set(m.controles) == {"N1", "D1", "P1"}
    assert not (tmp_path / "registro").exists()  # el ejecutor no escribe: eso lo hace el juez por el almacén


def test_e1_sin_el_binario_del_90b_aborta_antes_de_gastar_una_semilla(tmp_path, monkeypatch):
    monkeypatch.setattr("qrecauda.adaptadores.min_entropia.BINARIO_POR_DEFECTO", tmp_path / "no_existe")
    with pytest.raises(FuenteNoDisponible, match="90B"):
        composicion.ejecutor_e1_de(tmp_path).ejecutar(_diminuta(), 1)


def test_ejecutor_de_elige_el_de_e1(tmp_path):
    d = cargar_declaracion(Path("declaraciones/E1.toml"), RAIZ)
    assert type(composicion.ejecutor_de(tmp_path, d)).__name__ == "_EnMaquina"
