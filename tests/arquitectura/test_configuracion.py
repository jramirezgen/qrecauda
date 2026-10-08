"""F3.05: la configuración de la demo (Aer ruidoso + mitigación + validador) y su composición de punta a punta."""

import pytest

from qrecauda import composicion
from qrecauda.aplicacion.transaccion import ROTULO_VALIDACION, Transaccion
from qrecauda.dominio.errores import EntradaInvalida, FuenteNoDisponible
from qrecauda.dominio.metricas import Metrica
from qrecauda.dominio.muestra import Origen
from qrecauda.transversal.configuracion import Configuracion
from qrecauda.transversal.observabilidad import BitacoraJsonl
from qrecauda.transversal.reproducibilidad import hilos_blas

DEMO = {"backend": "aer_ruidoso", "mitigacion": "lectura", "nivel_ruido": "medio", "validador": "estadistico", "shots": 20_000}


def test_clave_desconocida_aborta():
    with pytest.raises(EntradaInvalida):
        Configuracion.desde_mapa({"shotz": 10})


def test_ibm_exige_ruta_del_token():
    with pytest.raises(EntradaInvalida):
        Configuracion(backend="ibm")


def test_valores_por_defecto_conservan_la_linea_base():
    c = Configuracion()
    assert (c.backend, c.mitigacion, c.nivel_ruido, c.validador) == ("prng", "ninguna", "medio", "estadistico")


@pytest.mark.parametrize(
    "mapa",
    [
        {"mitigacion": "zne"},
        {"nivel_ruido": "infernal"},
        {"validador": "dieharder"},
        {"backend": "prng", "mitigacion": "lectura"},  # el twirling re-ejecuta un circuito: sólo existe sobre Aer
    ],
)
def test_valores_fuera_de_vocabulario_o_incoherentes_abortan(mapa):
    with pytest.raises(EntradaInvalida):
        Configuracion.desde_mapa(mapa)


def test_la_demo_se_describe_en_el_manifiesto():
    assert Configuracion.desde_mapa(DEMO).como_dict()["mitigacion"] == "lectura"


def test_la_demo_corre_de_punta_a_punta_y_la_mitigacion_baja_el_sesgo():
    r = composicion.ejecutar(Configuracion.desde_mapa(DEMO))
    assert [e for e, _ in r.etapas] == ["cruda", "mitigada", "clave"]
    assert r.muestra.mitigada and r.muestra.origen is Origen.SIMULADOR_AER
    assert not r.muestra.reclama_origen_cuantico
    cruda = {m.metrica: m for m in r.medidas_de("cruda")}
    mitigada = {m.metrica: m for m in r.medidas_de("mitigada")}
    assert not cruda[Metrica.SESGO].cumple  # canal medio: ~0,03 de sesgo
    assert mitigada[Metrica.SESGO].valor < cruda[Metrica.SESGO].valor / 3
    assert len(r.clave) > 0


def test_sin_mitigacion_no_hay_etapa_mitigada():
    r = composicion.ejecutar(Configuracion.desde_mapa({**DEMO, "mitigacion": "ninguna"}))
    assert [e for e, _ in r.etapas] == ["cruda", "clave"] and not r.muestra.mitigada


def test_el_validador_nist_se_elige_por_configuracion():
    r = composicion.ejecutar(Configuracion.desde_mapa({**DEMO, "validador": "nist"}))
    assert {m.metrica for m in r.medidas_de("clave")} == {Metrica.SESGO, Metrica.MONOBIT, Metrica.RUNS, Metrica.CHI2}


def test_el_nivel_de_ruido_cambia_la_fuente():
    a = composicion.ejecutar(Configuracion.desde_mapa({**DEMO, "mitigacion": "ninguna", "nivel_ruido": "bajo"}))
    b = composicion.ejecutar(Configuracion.desde_mapa({**DEMO, "mitigacion": "ninguna", "nivel_ruido": "alto"}))
    sesgo = lambda r: next(m.valor for m in r.medidas_de("cruda") if m.metrica is Metrica.SESGO)  # noqa: E731
    assert sesgo(b) > sesgo(a)


def test_un_hilo_y_entorno_se_aplican_desde_la_composicion(monkeypatch):
    vistos: list[dict[str, int]] = []

    class Espia:
        def __init__(self, interna):
            self._i = interna

        def generar(self, qubits, shots):
            vistos.append(hilos_blas())
            return self._i.generar(qubits, shots)

    original = composicion.fuente_de
    monkeypatch.setattr(composicion, "fuente_de", lambda cfg: Espia(original(cfg)))
    llamadas = []
    monkeypatch.setattr(composicion, "entorno", lambda: llamadas.append(1) or {"python": "x"})
    import io

    salida = io.StringIO()
    composicion.ejecutar(Configuracion(shots=20_000), BitacoraJsonl(salida))
    assert vistos and all(n == 1 for n in vistos[0].values())
    assert llamadas, "entorno() no se consultó desde la composición"
    assert '"evento": "corrida"' in salida.getvalue() and '"python": "x"' in salida.getvalue()


def test_la_composicion_sin_bitacora_no_escribe_nada(capsys):
    composicion.ejecutar(Configuracion(shots=20_000))
    assert capsys.readouterr() == ("", "")


def test_el_servicio_de_transacciones_se_compone_con_la_clave_de_la_demo():
    cfg = Configuracion.desde_mapa({**DEMO, "shots": 100_000, "mitigacion": "ninguna"})
    s = composicion.servicio_de(cfg, composicion.ejecutar(cfg))
    tx = Transaccion("Estacion Central", 250, "T-0001")
    t = s.cifrar(tx)
    assert t.rotulo == ROTULO_VALIDACION and s.descifrar(t) == tx


def test_backend_ibm_sin_credencial_legible_es_fuente_no_disponible(tmp_path):
    token = tmp_path / "t"  # no existe: ningún test toca la red de IBM
    with pytest.raises(FuenteNoDisponible):
        composicion.fuente_de(Configuracion(backend="ibm", ibm_token_ruta=str(token)))
