"""F3.04: FuenteIbm sobre SamplerV2 con Batch/Session. SIN red, SIN credencial real y SIN IBM: todo con dobles.

La corrida real contra hardware es F3.06. Aquí se fija el CONTRATO: origen y procedencia con job_id, orden de bits igual
al de FuenteAer, el secreto jamás visible, y los fallos como FuenteNoDisponible accionable."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit_aer.primitives import SamplerV2 as AerSamplerV2

from qrecauda.adaptadores.aer import FuenteAer
from qrecauda.adaptadores.ibm_runtime import Fabricas, FuenteIbm
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.dominio.muestra import Origen
from qrecauda.puertos import FuenteDeBits
from qrecauda.transversal.seguridad import Secreto

TOKEN = "tok-SECRETO-9f8e7d6c5b4a39281706"


# ------------------------------------------------------------------ dobles


class _Backend:
    def __init__(self, name: str = "ibm_doble", num_qubits: int = 127) -> None:
        self.name, self.num_qubits = name, num_qubits


class _Servicio:
    def __init__(self, backend: _Backend | None = None) -> None:
        self.backend_ = backend or _Backend()
        self.llamadas: list[tuple[str, Any]] = []

    def backend(self, nombre: str) -> _Backend:
        self.llamadas.append(("backend", nombre))
        return self.backend_

    def least_busy(self, **kw: Any) -> _Backend:
        self.llamadas.append(("least_busy", kw))
        return self.backend_


class _Datos:
    def __init__(self, cadenas: list[str]) -> None:
        self._cadenas = cadenas

    def get_bitstrings(self) -> list[str]:
        return self._cadenas


class _Pub:
    def __init__(self, nombre: str, cadenas: list[str]) -> None:
        self.data = {nombre: _Datos(cadenas)}


class _Trabajo:
    def __init__(self, job_id: str, resultado: Callable[[], Any]) -> None:
        self._id, self._resultado = job_id, resultado

    def job_id(self) -> str:
        return self._id

    def result(self) -> Any:
        return self._resultado()


class _Modo:
    """Doble de Batch/Session: contexto que recuerda su tipo, su backend y si se cerró."""

    creados: list[_Modo] = []

    def __init__(self, tipo: str, backend: Any) -> None:
        self.tipo, self.backend, self.cerrado = tipo, backend, False
        _Modo.creados.append(self)

    def __enter__(self) -> _Modo:
        return self

    def __exit__(self, *a: object) -> None:
        self.cerrado = True


class _Sampler:
    """Doble de SamplerV2: contesta con `cadenas` fijas (big-endian, como Qiskit) y apunta los PUBs recibidos."""

    pubs: list[Any] = []
    cadenas: list[str] = []
    job_id = "job-real-001"
    falla_en_result: BaseException | None = None

    def __init__(self, mode: Any) -> None:
        self.modo = mode

    def run(self, pubs: list[Any]) -> _Trabajo:
        type(self).pubs = list(pubs)
        nombre = pubs[0][0].cregs[0].name

        def resultado() -> Any:
            if (e := type(self).falla_en_result) is not None:
                raise e
            return [_Pub(nombre, type(self).cadenas)]

        return _Trabajo(type(self).job_id, resultado)


@pytest.fixture(autouse=True)
def _limpio() -> None:
    _Modo.creados.clear()
    _Sampler.pubs, _Sampler.cadenas, _Sampler.job_id, _Sampler.falla_en_result = [], [], "job-real-001", None


def _fabricas(sampler: type = _Sampler) -> Fabricas:
    return Fabricas(
        batch=lambda backend: _Modo("batch", backend), session=lambda backend: _Modo("session", backend), sampler=sampler, version="9.9.9"
    )


def _identidad(circuito: QuantumCircuit, backend: Any) -> QuantumCircuit:
    return circuito


def _fuente(tmp_path: Any, servicio: _Servicio | None = None, **kw: Any) -> tuple[FuenteIbm, _Servicio]:
    srv = servicio or _Servicio()
    ruta = tmp_path / "token.txt"
    ruta.write_text(TOKEN + "\n")
    kw.setdefault("transpilar", _identidad)
    kw.setdefault("conectar", lambda secreto: srv)
    kw.setdefault("fabricas", _fabricas())
    return FuenteIbm.desde_ruta(ruta, **kw), srv


# ------------------------------------------------------------------ contrato de origen y procedencia


def test_implementa_el_puerto_y_declara_hardware_con_el_job_id_real(tmp_path: Any) -> None:
    _Sampler.cadenas = ["00"] * 8
    fuente, _ = _fuente(tmp_path, servicio=_Servicio(_Backend("ibm_sherbrooke")))
    puerto: FuenteDeBits = fuente
    m = puerto.generar(2, 8)
    assert m.origen is Origen.HARDWARE_IBM and m.reclama_origen_cuantico and not m.mitigada
    assert (m.qubits, m.shots, len(m.bits)) == (2, 8, 16)
    assert m.procedencia.job_id == "job-real-001"
    assert m.procedencia.backend == "ibm_sherbrooke"
    assert m.procedencia.version == "9.9.9"


def test_un_trabajo_sin_job_id_no_pasa_por_hardware(tmp_path: Any) -> None:
    """El doble NO puede devolver HARDWARE_IBM sin job_id: lo impide Muestra, y el adaptador lo dice antes con un error accionable."""
    _Sampler.cadenas = ["0"] * 4
    _Sampler.job_id = ""
    fuente, _ = _fuente(tmp_path)
    with pytest.raises(FuenteNoDisponible, match="job_id"):
        fuente.generar(1, 4)


# ------------------------------------------------------------------ orden de bits


def test_orden_qubit_mayor_con_cadenas_fijas(tmp_path: Any) -> None:
    """Cadenas big-endian: el carácter 0 es el clbit n-1. Todas «001» ⇒ sólo el qubit 0 vale 1: bloque del qubit 0 son unos."""
    _Sampler.cadenas = ["001"] * 3
    fuente, _ = _fuente(tmp_path)
    bits = fuente.generar(3, 3).bits.datos
    assert np.array_equal(bits, np.array([1, 1, 1, 0, 0, 0, 0, 0, 0], dtype=np.uint8))


def test_los_bits_coinciden_con_los_de_fuente_aer(tmp_path: Any) -> None:
    """Mismo circuito, mismo muestreador (Aer) detrás del doble y misma semilla ⇒ MISMOS bits que FuenteAer."""

    class _SamplerAer:
        def __init__(self, mode: Any) -> None:
            self._aer = AerSamplerV2(default_shots=256, seed=11)

        def run(self, pubs: list[Any]) -> Any:
            circuito, _, shots = pubs[0]
            resultado = self._aer.run([(circuito, None, shots)]).result()
            return _Trabajo("job-aer", lambda: resultado)

    fuente, _ = _fuente(tmp_path, fabricas=_fabricas(_SamplerAer))
    esperado = FuenteAer(semilla=11).generar(4, 256).bits
    assert fuente.generar(4, 256).bits == esperado


# ------------------------------------------------------------------ PUBs, Batch/Session y transpilación


def test_el_pub_lleva_el_circuito_transpilado_y_los_shots(tmp_path: Any) -> None:
    _Sampler.cadenas = ["00"] * 5
    vistos: list[tuple[QuantumCircuit, Any]] = []
    marcado = QuantumCircuit(2, 2, name="isa")
    marcado.measure([0, 1], [0, 1])

    def transpilar(circuito: QuantumCircuit, backend: Any) -> QuantumCircuit:
        vistos.append((circuito, backend))
        return marcado

    fuente, srv = _fuente(tmp_path, transpilar=transpilar)
    fuente.generar(2, 5)
    ((circuito, backend),) = vistos
    assert backend is srv.backend_ and circuito.num_qubits == 2 and "h" in circuito.count_ops()
    (pub,) = _Sampler.pubs
    assert pub[0] is marcado and tuple(pub[1:]) == (None, 5)


def test_por_defecto_batch_y_se_cierra(tmp_path: Any) -> None:
    _Sampler.cadenas = ["0"] * 3
    fuente, srv = _fuente(tmp_path)
    fuente.generar(1, 3)
    (modo,) = _Modo.creados
    assert modo.tipo == "batch" and modo.backend is srv.backend_ and modo.cerrado


def test_session_si_se_pide_y_se_cierra_aunque_falle(tmp_path: Any) -> None:
    _Sampler.cadenas = ["0"] * 3
    _Sampler.falla_en_result = TimeoutError("cola agotada")
    fuente, _ = _fuente(tmp_path, modo="session")
    with pytest.raises(FuenteNoDisponible):
        fuente.generar(1, 3)
    (modo,) = _Modo.creados
    assert modo.tipo == "session" and modo.cerrado


def test_backend_con_nombre_o_el_menos_ocupado(tmp_path: Any) -> None:
    _Sampler.cadenas = ["0"] * 2
    fuente, srv = _fuente(tmp_path, backend="ibm_torino")
    fuente.generar(1, 2)
    assert srv.llamadas == [("backend", "ibm_torino")]
    _Sampler.cadenas = ["000"] * 2
    fuente2, srv2 = _fuente(tmp_path)
    fuente2.generar(3, 2)
    ((nombre, kw),) = srv2.llamadas
    assert nombre == "least_busy" and kw["min_num_qubits"] == 3 and kw["simulator"] is False and kw["operational"] is True


def test_conecta_una_sola_vez(tmp_path: Any) -> None:
    _Sampler.cadenas = ["0"] * 2
    n = []
    srv = _Servicio()
    fuente, _ = _fuente(tmp_path, conectar=lambda s: (n.append(1), srv)[1])
    assert not n  # construir no toca la red
    fuente.generar(1, 2)
    fuente.generar(1, 2)
    assert len(n) == 1


# ------------------------------------------------------------------ entradas y fallos accionables


@pytest.mark.parametrize(("q", "s"), [(0, 10), (2, 0), (-1, 5)])
def test_entradas_invalidas(tmp_path: Any, q: int, s: int) -> None:
    fuente, _ = _fuente(tmp_path)
    with pytest.raises(EntradaInvalida):
        fuente.generar(q, s)


def test_modo_desconocido_aborta(tmp_path: Any) -> None:
    with pytest.raises(EntradaInvalida, match="modo"):
        _fuente(tmp_path, modo="job")


def test_el_backend_debe_tener_qubits_suficientes(tmp_path: Any) -> None:
    fuente, _ = _fuente(tmp_path, servicio=_Servicio(_Backend("ibm_pequeno", num_qubits=5)))
    with pytest.raises(FuenteNoDisponible, match="ibm_pequeno"):
        fuente.generar(8, 10)


def test_sin_fichero_de_credencial_es_fuente_no_disponible_accionable(tmp_path: Any) -> None:
    ruta = tmp_path / "no_existe.txt"
    with pytest.raises(FuenteNoDisponible) as e:
        FuenteIbm.desde_ruta(ruta, transpilar=_identidad)
    msg = str(e.value)
    assert str(ruta) in msg and "ibm_token_ruta" in msg and "QRECAUDA_IBM_TOKEN_FILE" in msg


def test_credencial_vacia_es_fuente_no_disponible(tmp_path: Any) -> None:
    ruta = tmp_path / "vacio.txt"
    ruta.write_text("  \n")
    with pytest.raises(FuenteNoDisponible, match="vacío"):
        FuenteIbm.desde_ruta(ruta, transpilar=_identidad)


def test_sin_red_es_fuente_no_disponible_accionable(tmp_path: Any) -> None:
    def sin_red(secreto: Secreto) -> Any:
        raise OSError(f"Name resolution failed (token={secreto.revelar()})")

    fuente, _ = _fuente(tmp_path, conectar=sin_red)
    with pytest.raises(FuenteNoDisponible) as e:
        fuente.generar(1, 4)
    assert "red" in str(e.value) and "F3.06" not in str(e.value) and TOKEN not in str(e.value)


def test_fallo_del_trabajo_cita_el_job_id(tmp_path: Any) -> None:
    _Sampler.falla_en_result = RuntimeError("el trabajo falló")
    fuente, _ = _fuente(tmp_path)
    with pytest.raises(FuenteNoDisponible, match="job-real-001"):
        fuente.generar(1, 4)


def test_resultado_con_forma_inesperada_es_fuente_no_disponible(tmp_path: Any) -> None:
    _Sampler.cadenas = []
    fuente, _ = _fuente(tmp_path)
    with pytest.raises(FuenteNoDisponible, match="job-real-001"):
        fuente.generar(1, 4)


def test_cadenas_de_anchura_equivocada_son_fuente_no_disponible(tmp_path: Any) -> None:
    _Sampler.cadenas = ["00"] * 4
    fuente, _ = _fuente(tmp_path)
    with pytest.raises(FuenteNoDisponible, match="anchura"):
        fuente.generar(3, 4)


# ------------------------------------------------------------------ el secreto no se ve en ningún sitio


def test_el_token_no_aparece_en_repr_str_excepciones_ni_logs(tmp_path: Any, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    _Sampler.cadenas = ["0"] * 4
    fuente, _ = _fuente(tmp_path)
    fuente.generar(1, 4)
    for texto in (repr(fuente), str(fuente), repr(vars(fuente)) if hasattr(fuente, "__dict__") else ""):
        assert TOKEN not in texto

    def con_fuga(secreto: Secreto) -> Any:
        raise RuntimeError(f"401 Unauthorized, token inválido: {secreto.revelar()}")

    mala, _ = _fuente(tmp_path, conectar=con_fuga)
    with pytest.raises(FuenteNoDisponible) as e:
        mala.generar(1, 4)
    volcado = "".join([str(e.value), repr(e.value), repr(e.value.__cause__), repr(e.value.__context__)])
    assert TOKEN not in volcado
    assert TOKEN not in caplog.text
    assert "job-real-001" in caplog.text  # lo que sí se registra: backend y job_id


def test_el_servicio_recibe_el_secreto_envuelto_no_como_cadena(tmp_path: Any) -> None:
    recibido: list[object] = []
    _Sampler.cadenas = ["0"] * 2
    srv = _Servicio()
    fuente, _ = _fuente(tmp_path, conectar=lambda s: (recibido.append(s), srv)[1])
    fuente.generar(1, 2)
    (s,) = recibido
    assert isinstance(s, Secreto) and TOKEN not in repr(s)


# ------------------------------------------------------------------ composición


def test_la_composicion_compone_ibm_si_hay_ruta_sin_tocar_la_red(tmp_path: Any) -> None:
    from qrecauda import composicion
    from qrecauda.transversal.configuracion import Configuracion

    ruta = tmp_path / "t.txt"
    ruta.write_text(TOKEN)
    cfg = Configuracion(backend="ibm", ibm_token_ruta=str(ruta), ibm_backend="ibm_torino", ibm_modo="session")
    fuente = composicion.fuente_de(cfg)  # no conecta: la red se toca en `generar`
    assert type(fuente).__name__ == "FuenteIbm" and TOKEN not in repr(fuente)


def test_la_composicion_sin_ruta_legible_lanza_fuente_no_disponible(tmp_path: Any) -> None:
    from qrecauda import composicion
    from qrecauda.transversal.configuracion import Configuracion

    with pytest.raises(FuenteNoDisponible, match="ibm_token_ruta"):
        composicion.fuente_de(Configuracion(backend="ibm", ibm_token_ruta=str(tmp_path / "falta.txt")))


def test_la_composicion_inyecta_la_transpilacion_real_y_el_job_id_llega(tmp_path: Any) -> None:
    """De punta a punta con un backend local (GenericBackendV2) y el sampler doble: la transpilación ISA es la de F3.03."""
    from qrecauda import composicion
    from qrecauda.transversal.configuracion import Configuracion

    ruta = tmp_path / "t.txt"
    ruta.write_text(TOKEN)
    local = GenericBackendV2(num_qubits=6, seed=3)
    local_nombre = local.name
    srv = _Servicio()
    srv.backend_ = local  # type: ignore[assignment]
    _Sampler.cadenas = ["000"] * 6
    cfg = Configuracion(backend="ibm", ibm_token_ruta=str(ruta), qubits=3, shots=6)
    fuente = composicion.fuente_ibm_de(cfg, conectar=lambda s: srv, fabricas=_fabricas())
    m = fuente.generar(3, 6)
    assert m.origen is Origen.HARDWARE_IBM and m.procedencia.job_id == "job-real-001" and m.procedencia.backend == local_nombre
    ops = set(_Sampler.pubs[0][0].count_ops())
    assert ops <= set(local.operation_names) | {"measure", "barrier", "delay"}  # ya es ISA del backend, no el H crudo
