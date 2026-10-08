"""EjecutorE3b y la reserva asíncrona (F6.03), con reloj, temporizador y productor FALSOS; el cifrado y el registro de consumo, REALES."""

from __future__ import annotations

import json

import pytest
from e3b_dobles import MS, ROTULO, ProductorFalso, RelojFalso, SondaFalsa, TemporizadorFalso, clave_entregada, declaracion_diminuta

from qrecauda.adaptadores.aes_gcm import CifradorAesGcm, ReservaDeClave
from qrecauda.aplicacion.ejecutor_e3b import EjecutorE3b, p_latencia, sin_claves, tasa_neta_bps
from qrecauda.aplicacion.reserva_asincrona import ReservaAsincrona, ServicioDeTransaccionesAsincrono
from qrecauda.aplicacion.transaccion import Transaccion
from qrecauda.datos import InformeDelProductor
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida, EntropiaInsuficiente


class BitacoraEnMemoria:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, object]]] = []

    def registrar(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))


def _ejecutor(productor, *, paso=MS, factor_cpu=0.5, carga=0.1, bitacora=None, cifrador=CifradorAesGcm):
    reloj = RelojFalso(paso)
    sonda = SondaFalsa(reloj, factor_cpu=factor_cpu, carga=carga)
    ej = EjecutorE3b(lambda d, s: productor, cifrador, ReservaDeClave, reloj, TemporizadorFalso(reloj), sonda, bitacora, lambda: (4,))
    return ej, reloj


def _claves(n=4, **kw):
    return [clave_entregada(i, **kw) for i in range(n)]


# ------------------------------------------------------------------ la reserva


def test_reserva_reparte_trozos_distintos_y_cambia_de_clave_sin_esperar():
    reloj = RelojFalso()
    p = ProductorFalso(_claves(3))
    r = ReservaAsincrona(p, ReservaDeClave, reloj, espera_maxima_s=1.0)
    r.cebar()
    pares = [r.siguiente() for _ in range(25)]  # 10 + 10 + 5: dos cambios de clave
    assert len({(c.a_bytes(), n.a_bytes()) for c, n in pares}) == 25
    assert r.esperas == 0 and len(r.cambios) == 2 and len(r.metas) == 3 and not r.agotada


def test_reserva_cuenta_la_espera_cuando_la_clave_no_esta_lista():
    reloj = RelojFalso()
    p = ProductorFalso(_claves(2), esperan=frozenset({1}))
    r = ReservaAsincrona(p, ReservaDeClave, reloj, espera_maxima_s=1.0)
    r.cebar()
    for _ in range(11):
        r.siguiente()
    assert r.esperas == 1 and r.espera_ns > 0 and r.cambios[0]["espera_ms"] > 0
    assert p.esperas_pedidas[-2:] == [0.0, 1.0]


def test_reserva_agotada_se_declara_no_se_esconde():
    reloj = RelojFalso()
    r = ReservaAsincrona(ProductorFalso(_claves(1)), ReservaDeClave, reloj, espera_maxima_s=0.5)
    r.cebar()
    for _ in range(10):
        r.siguiente()
    with pytest.raises(EntropiaInsuficiente):
        r.siguiente()
    assert r.agotada and r.esperas == 1


def test_servicio_cifra_descifra_y_nunca_repite_pares():
    reloj = RelojFalso()
    r = ReservaAsincrona(ProductorFalso(_claves(2)), ReservaDeClave, reloj, 1.0)
    r.cebar()
    s = ServicioDeTransaccionesAsincrono(r, CifradorAesGcm())
    for k in range(15):
        s.ciclo(Transaccion("Peaje Norte", 100 + k, f"T-{k}"))
    assert s.realizadas == 15 and s.ida_y_vuelta and s.pares_repetidos == 0 and s.nonces_repetidos == 0


# ------------------------------------------------------------------ el ejecutor


def test_ejecutor_sano_mide_latencia_tasa_y_pasa_todos_los_controles():
    decl = declaracion_diminuta()
    ej, _ = _ejecutor(ProductorFalso(_claves(4)))
    med = ej.ejecutar(decl, 20261007)
    (e,) = med.e3b
    assert all(med.controles.values()), med.controles
    assert set(med.controles) == {"U1", "U2", "U3", "U4", "U5", "T4"}
    assert e.transacciones == 20 and e.esperas == 0 and e.consumo_bps == 35200
    assert e.tasa_neta_bps == pytest.approx(35200.0)  # 3520 bits en 100 ms por clave
    assert e.p95_ms == p_latencia(e.reporte["latencias_ms"], 95)
    assert e.reporte["afinidad"]["consumidor"] == [4] and len(e.reporte["latencias_ms"]) == 20


def test_la_latencia_se_mide_desde_la_llegada_programada():
    decl = declaracion_diminuta()
    ej, _ = _ejecutor(ProductorFalso(_claves(4)), paso=MS)
    (e,) = ej.ejecutar(decl, 1).e3b
    lat = e.reporte["latencias_ms"]
    assert min(lat) > 0 and max(lat) < 10  # el reloj sólo avanza por lecturas: nada de los 10 ms entre llegadas


def test_una_espera_de_reserva_se_ve_en_esperas_y_en_la_latencia():
    decl = declaracion_diminuta()
    ej, _ = _ejecutor(ProductorFalso(_claves(4), esperan=frozenset({1})))
    (e,) = ej.ejecutar(decl, 1).e3b
    assert e.esperas == 1 and e.reporte["cambios_de_clave"][0]["espera_ms"] > 0


def test_reserva_agotada_corta_r2_y_queda_registrada():
    decl = declaracion_diminuta(ajustes={"reserva": {"espera_maxima_s": 1}})
    ej, _ = _ejecutor(ProductorFalso(_claves(1)))
    (e,) = ej.ejecutar(decl, 1).e3b
    assert e.transacciones == 10 and e.reporte["reserva_agotada"] is True and e.esperas == 1


def test_t4_falla_si_el_consumidor_gasta_mas_cpu_que_pared():
    ej, _ = _ejecutor(ProductorFalso(_claves(4)), factor_cpu=1.5)
    med = ej.ejecutar(declaracion_diminuta(), 1)
    assert med.controles["T4"] is False and med.controles["U1"] is True


def test_t4_falla_si_el_productor_hubo_que_matarlo():
    informe = InformeDelProductor((8,), 10_000 * MS, 4_000 * MS, 4_000 * MS, tuple(c.meta for c in _claves(4)), forzado=True)
    ej, _ = _ejecutor(ProductorFalso(_claves(4), informe=informe))
    assert ej.ejecutar(declaracion_diminuta(), 1).controles["T4"] is False


def test_carga_previa_alta_no_mide():
    ej, _ = _ejecutor(ProductorFalso(_claves(4)), carga=5.0)
    with pytest.raises(CorridaInvalida, match="carga previa"):
        ej.ejecutar(declaracion_diminuta(), 1)


def test_el_productor_siempre_se_detiene_aunque_falle_el_cebado():
    p = ProductorFalso([])
    ej, _ = _ejecutor(p)
    with pytest.raises(CorridaInvalida):
        ej.ejecutar(declaracion_diminuta(), 1)
    assert p.iniciado and p.detenido


def test_rotulo_de_origen_equivocado_hace_fallar_u5():
    ej, _ = _ejecutor(ProductorFalso(_claves(4, rotulo="origen cuántico")))
    assert ej.ejecutar(declaracion_diminuta(), 1).controles["U5"] is False


def test_ninguna_clave_llega_a_la_bitacora_ni_al_reporte():
    bit = BitacoraEnMemoria()
    claves = _claves(4)
    ej, _ = _ejecutor(ProductorFalso(claves), bitacora=bit)
    (e,) = (med := ej.ejecutar(declaracion_diminuta(), 1)).e3b
    assert med.controles["U4"] is True and bit.eventos
    texto = json.dumps(e.reporte) + json.dumps([c for _, c in bit.eventos], default=str)
    for c in claves:
        assert c.clave.a_bytes().hex() not in texto
        assert c.clave.a_bytes().hex()[:32] not in texto
    assert claves[0].meta.huella in texto  # lo único que sí sale: la huella corta


def test_el_detector_de_claves_de_u4():
    assert sin_claves("clave=" + "ab" * 32, []) is False
    assert sin_claves("0" * 64, []) is False
    assert sin_claves("huella 0123456789ab", ["ffee"]) is True
    assert sin_claves("xx ffee yy", ["ffee"]) is False


def test_declaracion_incoherente_se_rechaza():
    ej, _ = _ejecutor(ProductorFalso(_claves(4)))
    with pytest.raises(EntradaInvalida, match="transacciones"):
        ej.ejecutar(declaracion_diminuta(ajustes={"demanda": {"transacciones": 21}}), 1)
    with pytest.raises(EntradaInvalida, match="consumo_bps"):
        ej.ejecutar(declaracion_diminuta(ajustes={"demanda": {"consumo_bps": 1}}), 1)
    with pytest.raises(EntradaInvalida, match="semilla_clave"):
        ej.ejecutar(declaracion_diminuta(ajustes={"configuracion": {"semilla_clave": "otra"}}), 1)


def test_eureka_equivocada():
    from dataclasses import replace

    ej, _ = _ejecutor(ProductorFalso(_claves(4)))
    with pytest.raises(EntradaInvalida, match="mide E3b"):
        ej.ejecutar(replace(declaracion_diminuta(), eureka="E3"), 1)


def test_tasa_neta_cuenta_solo_la_ventana_y_el_tiempo_de_todos_los_intentos():
    claves = [
        {"en_ventana": True, "bits": 3520, "t_gen_ns": 2 * 10**9},
        {"en_ventana": True, "bits": 3520, "t_gen_ns": 6 * 10**9},
        {"en_ventana": False, "bits": 3520, "t_gen_ns": 1},
    ]
    assert tasa_neta_bps(claves) == pytest.approx(7040 / 8)
    assert tasa_neta_bps([]) == 0.0
    assert ROTULO
