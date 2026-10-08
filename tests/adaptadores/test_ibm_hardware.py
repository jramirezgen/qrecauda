"""F3.07: camino a hardware de FuenteIbm — twirling con PUBs, registro del trabajo, presupuesto de QPU y ensayo contra un backend falso.

SIN red y SIN credencial: dobles del servicio y, para el ensayo, el servicio LOCAL de qiskit-ibm-runtime con FakeSherbrooke."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from qiskit import QuantumCircuit

from qrecauda.adaptadores.aer.transpilacion import a_isa
from qrecauda.adaptadores.ibm_runtime import Fabricas, FuenteIbm, _con_mascara, _qubits_fisicos
from qrecauda.datos.hardware import RegistroIbm
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible, PresupuestoQpuExcedido
from qrecauda.dominio.muestra import Origen
from qrecauda.transversal.seguridad import Secreto

TOKEN = "tok-SECRETO-0a1b2c3d4e5f60718293"


class _Datos:
    def __init__(self, cadenas: list[str]) -> None:
        self._c = cadenas

    def get_bitstrings(self) -> list[str]:
        return self._c


class _Pub:
    def __init__(self, nombre: str, cadenas: list[str]) -> None:
        self.data = {nombre: _Datos(cadenas)}


class _Trabajo:
    def __init__(self, job_id: str, resultado: Any, metricas: dict[str, Any] | None = None, uso: float = 0.0) -> None:
        self._id, self._r, self._m, self._uso = job_id, resultado, metricas, uso
        self.timeout_visto: Any = "no llamado"

    def job_id(self) -> str:
        return self._id

    def result(self, timeout: float | None = None) -> Any:
        self.timeout_visto = timeout
        if isinstance(self._r, BaseException):
            raise self._r
        return self._r

    def metrics(self) -> dict[str, Any]:
        if self._m is None:
            raise AttributeError("sin metrics")
        return self._m

    def usage(self) -> float:
        return self._uso


class _Backend:
    name = "ibm_doble"
    num_qubits = 127


class _Servicio:
    def __init__(self, restante: float | None = None) -> None:
        self.backend_, self.restante = _Backend(), restante

    def backend(self, nombre: str) -> _Backend:
        return self.backend_

    def least_busy(self, **kw: Any) -> _Backend:
        return self.backend_

    def usage(self) -> dict[str, Any]:
        if self.restante is None:
            raise AttributeError
        return {"usage_remaining_seconds": self.restante}


class _Samplers:
    """Fábrica de SamplerV2 falsos: cada PUB devuelve `relleno` por disparo (todo «0»: el dispositivo lee siempre cero)."""

    def __init__(self, relleno: str = "0", metricas: dict[str, Any] | None = None, uso: float = 0.0, resultado: Any = None) -> None:
        self.relleno, self.metricas, self.uso, self.resultado = relleno, metricas, uso, resultado
        self.pubs: list[Any] = []
        self.modos: list[Any] = []
        self.trabajos: list[_Trabajo] = []

    def __call__(self, mode: Any) -> Any:
        self.modos.append(mode)
        yo = self

        class _S:
            def run(self, pubs: list[Any]) -> _Trabajo:
                yo.pubs.append(list(pubs))
                n = pubs[0][0].num_clbits
                res = yo.resultado or [_Pub(p[0].cregs[0].name, [yo.relleno * n] * p[2]) for p in pubs]
                t = _Trabajo(f"job-{len(yo.trabajos):03d}", res, yo.metricas, yo.uso)
                yo.trabajos.append(t)
                return t

        return _S()


class _Contexto:
    def __init__(self, tipo: str, registro: list[str]) -> None:
        self.tipo, self.reg = tipo, registro

    def __enter__(self) -> _Contexto:
        self.reg.append(self.tipo)
        return self

    def __exit__(self, *a: object) -> None:
        return None


def _fuente(tmp_path: Path, samplers: _Samplers, servicio: _Servicio | None = None, **kw: Any) -> tuple[FuenteIbm, list[str]]:
    ruta = tmp_path / "token.txt"
    ruta.write_text(TOKEN)
    srv, creados = servicio or _Servicio(), []
    fab = Fabricas(lambda b: _Contexto("batch", creados), lambda b: _Contexto("session", creados), samplers, "9.9.9")
    kw.setdefault("transpilar", lambda qc, backend: qc)
    f = FuenteIbm.desde_ruta(ruta, conectar=lambda s: srv, fabricas=fab, **kw)
    return f, creados


def _h(n: int) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    qc.h(range(n))
    qc.measure_all()
    return qc


# ------------------------------------------------------------------ máscaras puras


def test_la_mascara_inserta_una_x_justo_antes_de_medir_solo_donde_vale_uno() -> None:
    base = _h(3)
    con = _con_mascara(base, np.array([1, 0, 1], dtype=np.uint8))
    nombres = [i.operation.name for i in con.data]
    assert nombres.count("x") == 2 and base.count_ops().get("x", 0) == 0
    for k, inst in enumerate(con.data):
        if inst.operation.name == "x":
            assert con.data[k + 1].operation.name == "measure" and con.data[k + 1].qubits == inst.qubits
    assert con.num_qubits == 3 and con.cregs == base.cregs


def test_una_mascara_de_ceros_deja_el_circuito_igual() -> None:
    base = _h(2)
    assert _con_mascara(base, np.zeros(2, dtype=np.uint8)) == base


def test_los_qubits_fisicos_salen_de_las_mediciones() -> None:
    qc = QuantumCircuit(5, 3)
    qc.measure([4, 0, 2], [0, 1, 2])
    assert _qubits_fisicos(qc, 3) == (4, 0, 2)


def test_un_circuito_que_no_mide_todos_los_qubits_logicos_es_fuente_no_disponible() -> None:
    qc = QuantumCircuit(3, 3)
    qc.measure([0], [0])
    with pytest.raises(FuenteNoDisponible, match="mide"):
        _qubits_fisicos(qc, 3)


# ------------------------------------------------------------------ twirling con PUBs


def test_sin_twirling_hay_un_solo_pub_con_todos_los_shots(tmp_path: Path) -> None:
    s = _Samplers()
    f, _ = _fuente(tmp_path, s)
    f.generar(2, 40)
    (pubs,) = s.pubs
    assert len(pubs) == 1 and pubs[0][2] == 40


def test_con_twirling_hay_una_cruda_y_k_mascaras_con_los_mismos_shots(tmp_path: Path) -> None:
    s = _Samplers()
    f, _ = _fuente(tmp_path, s, mascaras=3, semilla=5)
    f.generar(2, 40)
    (pubs,) = s.pubs
    assert [p[2] for p in pubs] == [10, 10, 10, 10]  # IBM deprecó mezclar shots entre PUBs
    assert pubs[0][0].count_ops().get("x", 0) == 0


def test_el_twirling_se_deshace_por_xor_con_la_mascara_de_cada_pub(tmp_path: Path) -> None:
    """El dispositivo falso lee SIEMPRE cero: la cruda es toda ceros y la del twirling reproduce, deshecha, las máscaras sorteadas."""
    s = _Samplers("0")
    f, _ = _fuente(tmp_path, s, mascaras=4, semilla=7)
    cruda, twirl = f.generar_contraste(3, 50)
    assert cruda.shots == 10 and twirl.shots == 40 and not cruda.mitigada and twirl.mitigada
    assert cruda.bits.datos.sum() == 0
    esperado = np.random.default_rng(7).integers(0, 2, size=(4, 3), dtype=np.uint8)
    tiros = twirl.bits.datos.reshape(3, 40).T  # (disparos, qubit)
    assert np.array_equal(tiros, np.repeat(esperado, 10, axis=0))
    assert cruda.procedencia == twirl.procedencia and cruda.procedencia.job_id == "job-000"  # UN solo trabajo


def test_el_twirling_cancela_el_sesgo_de_lectura_asimetrico(tmp_path: Path) -> None:
    """Dispositivo con lectura sesgada hacia 0: la cruda sale sesgada y la del twirling casi simétrica (máscaras balanceadas)."""
    rng = np.random.default_rng(1)

    class _Sesgado(_Samplers):
        def __call__(self, mode: Any) -> Any:
            class _S:
                def run(_, pubs: list[Any]) -> _Trabajo:
                    n = pubs[0][0].num_clbits
                    res = []
                    for c, _, shots in pubs:
                        mask = np.zeros(n, dtype=np.uint8)
                        for inst in c.data:
                            if inst.operation.name == "x":
                                mask[c.find_bit(inst.qubits[0]).index] = 1
                        # |+>: la X no cambia el estado; la lectura da 1 con p=0.40 (sesgada hacia 0)
                        bits = (rng.random((shots, n)) < 0.40).astype(np.uint8)
                        res.append(_Pub(c.cregs[0].name, ["".join(map(str, fila[::-1])) for fila in bits]))
                    return _Trabajo("job-s", res)

            return _S()

    f, _ = _fuente(tmp_path, _Sesgado(), mascaras=15, semilla=3)
    cruda, twirl = f.generar_contraste(4, 16 * 4000)
    p_cruda = cruda.bits.datos.mean()
    p_twirl = twirl.bits.datos.mean()
    assert abs(p_cruda - 0.5) > 0.09 and abs(p_twirl - 0.5) < 0.05


def test_generar_con_twirling_devuelve_todo_deshecho_y_marcado_mitigado(tmp_path: Path) -> None:
    f, _ = _fuente(tmp_path, _Samplers(), mascaras=1, semilla=0)
    m = f.generar(2, 20)
    assert m.mitigada and m.shots == 20 and len(m.bits) == 40


def test_generar_contraste_sin_mascaras_aborta(tmp_path: Path) -> None:
    f, _ = _fuente(tmp_path, _Samplers())
    with pytest.raises(EntradaInvalida, match="mascaras"):
        f.generar_contraste(2, 10)


def test_shots_que_no_se_reparten_igual_aborta_antes_de_enviar(tmp_path: Path) -> None:
    s = _Samplers()
    f, _ = _fuente(tmp_path, s, mascaras=3)
    with pytest.raises(EntradaInvalida, match="PUBs iguales"):
        f.generar(2, 10)
    assert not s.pubs


# ------------------------------------------------------------------ modos


def test_el_modo_trabajo_usa_el_backend_como_modo_sin_batch_ni_session(tmp_path: Path) -> None:
    s = _Samplers()
    f, creados = _fuente(tmp_path, s, modo="trabajo")
    f.generar(1, 4)
    assert creados == [] and s.modos == [f._preparados[1].backend]


@pytest.mark.parametrize("modo", ["batch", "session"])
def test_batch_y_session_siguen_abriendo_su_contexto(tmp_path: Path, modo: str) -> None:
    f, creados = _fuente(tmp_path, _Samplers(), modo=modo)
    f.generar(1, 4)
    assert creados == [modo]


# ------------------------------------------------------------------ registro del trabajo


def test_el_registro_lleva_job_backend_tiempos_uso_y_estimacion(tmp_path: Path) -> None:
    t0 = datetime(2026, 10, 9, 12, 0, 0)
    metricas = {"timestamps": {"created": t0.isoformat() + "Z", "running": (t0 + timedelta(seconds=90)).isoformat() + "Z",
                               "finished": (t0 + timedelta(seconds=97)).isoformat() + "Z"}}  # fmt: skip
    f, _ = _fuente(tmp_path, _Samplers(metricas=metricas, uso=4.5), modo="trabajo")
    f.generar(2, 8)
    r = f.ultimo_registro
    assert r is not None
    assert (r.job_id, r.backend, r.modo, r.shots, r.pubs, r.ensayo) == ("job-000", "ibm_doble", "trabajo", 8, 1, False)
    assert r.cola_s == pytest.approx(90.0) and r.ejecucion_s == pytest.approx(7.0) and r.uso_qpu_s == 4.5
    assert r.estimado_qpu_s > 0 and r.version_sdk == "9.9.9" and r.qubits_fisicos == (0, 1)
    assert r.via_transpilacion == "local"
    assert RegistroIbm.desde_mapa(r.a_mapa()) == r  # ida y vuelta exacta


def test_sin_metricas_los_tiempos_son_none_y_no_se_inventan(tmp_path: Path) -> None:
    f, _ = _fuente(tmp_path, _Samplers())
    f.generar(1, 4)
    r = f.ultimo_registro
    assert r is not None and (r.cola_s, r.ejecucion_s, r.uso_qpu_s) == (None, None, None) and r.creado == ""


def test_el_registro_no_contiene_el_token(tmp_path: Path) -> None:
    f, _ = _fuente(tmp_path, _Samplers())
    f.generar(1, 4)
    assert TOKEN not in json.dumps([r.a_mapa() for r in f.registros]) and TOKEN not in repr(f)


def test_la_via_de_transpilacion_se_registra_si_el_transpilador_la_declara(tmp_path: Path) -> None:
    class _T:
        def __init__(self, qc: QuantumCircuit) -> None:
            self.circuito, self.via, self.motivo = qc, "ia", "AIRouting"

    f, _ = _fuente(tmp_path, _Samplers(), transpilar=lambda qc, b: _T(qc))
    f.generar(1, 4)
    r = f.ultimo_registro
    assert r is not None and (r.via_transpilacion, r.motivo_transpilacion) == ("ia", "AIRouting")


def test_el_timeout_de_espera_llega_al_trabajo_y_el_error_cita_como_recuperarlo(tmp_path: Path) -> None:
    s = _Samplers(resultado=TimeoutError("agotado"))
    f, _ = _fuente(tmp_path, s, espera_max_s=120.0)
    with pytest.raises(FuenteNoDisponible, match=r"QiskitRuntimeService\.job\('job-000'\)"):
        f.generar(1, 4)
    assert s.trabajos[0].timeout_visto == 120.0


# ------------------------------------------------------------------ presupuesto de QPU


def test_el_tope_aborta_antes_de_enviar(tmp_path: Path) -> None:
    s = _Samplers()
    f, _ = _fuente(tmp_path, s, max_segundos_qpu=1.0)  # la sobrecarga fija ya pasa de 1 s
    with pytest.raises(PresupuestoQpuExcedido, match="tope"):
        f.generar(2, 1000)
    assert not s.pubs and f.registros == ()


def test_la_cuota_restante_del_servicio_aborta_antes_de_enviar(tmp_path: Path) -> None:
    s = _Samplers()
    f, _ = _fuente(tmp_path, s, servicio=_Servicio(restante=1.0))
    with pytest.raises(PresupuestoQpuExcedido, match="cuota"):
        f.generar(2, 1000)
    assert not s.pubs


def test_el_gasto_se_acumula_entre_trabajos_y_el_segundo_aborta(tmp_path: Path) -> None:
    s = _Samplers()
    f, _ = _fuente(tmp_path, s)
    un_trabajo = f.estimar_qpu(2, 100).segundos
    f2, _ = _fuente(tmp_path, s, max_segundos_qpu=un_trabajo * 1.5)
    f2.generar(2, 100)
    with pytest.raises(PresupuestoQpuExcedido):
        f2.generar(2, 100)
    assert len(s.pubs) == 1 and f2.gastado_estimado_s == pytest.approx(un_trabajo)


def test_el_uso_real_sustituye_a_la_estimacion_en_la_cuenta(tmp_path: Path) -> None:
    f, _ = _fuente(tmp_path, _Samplers(uso=0.7))
    f.generar(1, 10)
    assert f.gastado_estimado_s == pytest.approx(0.7)


def test_estimar_no_envia_nada(tmp_path: Path) -> None:
    s = _Samplers()
    f, _ = _fuente(tmp_path, s, mascaras=3)
    e = f.estimar_qpu(4, 400)
    assert e.shots_totales == 400 and e.circuitos == 4 and not s.pubs


def test_un_tope_no_positivo_aborta_al_construir(tmp_path: Path) -> None:
    with pytest.raises(EntradaInvalida):
        _fuente(tmp_path, _Samplers(), max_segundos_qpu=0.0)


# ------------------------------------------------------------------ ensayo: todo el camino contra un backend falso de IBM


def _transpilar_real(qc: QuantumCircuit, backend: Any) -> Any:
    return a_isa(qc, backend)


@pytest.fixture(scope="module")
def ensayo() -> tuple[FuenteIbm, Any, Any]:
    f = FuenteIbm.para_ensayo(transpilar=_transpilar_real, mascaras=3, semilla=11, max_segundos_qpu=5.0)
    cruda, twirl = f.generar_contraste(8, 2000)
    return f, cruda, twirl


def test_el_ensayo_recorre_seleccion_transpilacion_y_envio_con_un_backend_falso(ensayo: tuple[FuenteIbm, Any, Any]) -> None:
    f, cruda, twirl = ensayo
    r = f.ultimo_registro
    assert r is not None and r.ensayo and r.backend == "fake_sherbrooke" and r.job_id
    assert r.modo == "trabajo" and r.pubs == 4 and r.mascaras == 3 and r.shots == 2000
    assert len(set(r.qubits_fisicos)) == 8 and r.profundidad >= 1
    assert (cruda.shots, twirl.shots) == (500, 1500)
    assert len(cruda.bits) == 8 * 500 and len(twirl.bits) == 8 * 1500


def test_un_ensayo_nunca_reclama_origen_cuantico(ensayo: tuple[FuenteIbm, Any, Any]) -> None:
    _, cruda, twirl = ensayo
    for m in (cruda, twirl):
        assert m.origen is Origen.SIMULADOR_AER and not m.reclama_origen_cuantico and m.procedencia.job_id


def test_el_ensayo_registra_la_calibracion_del_backend_falso(ensayo: tuple[FuenteIbm, Any, Any]) -> None:
    f, _, _ = ensayo
    r = f.ultimo_registro
    assert r is not None and r.calibracion_fecha.startswith("2025-")  # la instantánea congelada de FakeSherbrooke
    assert len(r.calibracion) == 8
    for c in r.calibracion:
        assert c.t1_s and c.t1_s > 0 and c.t2_s and c.t2_s > 0 and c.error_lectura is not None and 0 <= c.error_lectura < 1


def test_el_ensayo_no_gasta_cuota_ni_pide_credencial(ensayo: tuple[FuenteIbm, Any, Any]) -> None:
    f, _, _ = ensayo
    assert f.gastado_estimado_s == 0.0 and "ensayo-sin-credencial" not in repr(f)
    assert isinstance(f._servicio.is_local, bool) and f._servicio.is_local


def test_el_ensayo_tambien_respeta_el_tope_de_qpu() -> None:
    f = FuenteIbm.para_ensayo(transpilar=_transpilar_real, max_segundos_qpu=0.5)
    with pytest.raises(PresupuestoQpuExcedido):
        f.generar(8, 1000)


def test_el_ensayo_sin_backend_pedido_usa_el_de_ensayo_por_omision() -> None:
    f = FuenteIbm.para_ensayo(transpilar=_transpilar_real)
    assert f.estimar_qpu(8, 1000).segundos > 0
    assert f._preparados[8].nombre == "fake_sherbrooke"


def test_los_bits_del_ensayo_son_bits_y_el_sesgo_es_razonable(ensayo: tuple[FuenteIbm, Any, Any]) -> None:
    _, cruda, twirl = ensayo
    for m in (cruda, twirl):
        assert set(np.unique(m.bits.datos)) <= {0, 1}
        assert abs(float(m.bits.datos.mean()) - 0.5) < 0.1


def test_un_backend_no_operativo_se_rechaza(tmp_path: Path) -> None:
    class _Parado(_Backend):
        def status(self) -> Any:
            class _E:
                operational = False

            return _E()

    srv = _Servicio()
    srv.backend_ = _Parado()
    f, _ = _fuente(tmp_path, _Samplers(), servicio=srv)
    with pytest.raises(FuenteNoDisponible, match="operativo"):
        f.generar(1, 4)


_ = (Secreto, Callable)  # los tipos que usan algunas pruebas por anotación
