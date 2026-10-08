"""EjecutorE3b: mide UNA semilla de E3b exactamente como la fija docs/preinscripciones/E3b.md. No decide nada: decide el juez.

R1 «arranque» (informativo): pared desde `iniciar()` del productor hasta tener la primera clave aprobada en la reserva (el cebado).
R2 «régimen» (decide): `transacciones` transacciones sintéticas con llegadas PROGRAMADAS a λ tx/s (lazo abierto: la i llega en
`t_ini + i/λ`), cada una cifrada y descifrada con un trozo de 352 bits de la reserva mientras el productor sigue generando. La latencia
de cada una es la pared desde su llegada programada hasta que el descifrado verifica; incluye cualquier espera por reserva vacía y
el cambio de clave. El productor corre en otro proceso y otro núcleo (lo fabrica la composición); este ejecutor sólo lo usa por su puerto.

Convenciones que la preinscripción deja a este código (⚠️ declaradas, no decididas en silencio):
- las latencias se guardan redondeadas a 0,1 µs y p95 se calcula sobre ESOS valores: el juez recalcula lo mismo;
- una reserva agotada (`EntropiaInsuficiente` tras `espera_maxima_s`) detiene R2: es un resultado (T3 falla), no una excepción tragada;
- U4 busca en el informe y en lo registrado en bitácora cualquier hex largo, cualquier racha larga de 0/1 y el prefijo de cada clave vista.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence

import numpy as np

from qrecauda.aplicacion.ejecutor_e3 import ESPERA_MAXIMA_S, ESTACIONES
from qrecauda.aplicacion.reserva_asincrona import BITS_POR_TRANSACCION, ReservaAsincrona, ServicioDeTransaccionesAsincrono
from qrecauda.aplicacion.transaccion import ROTULO_VALIDACION, Transaccion
from qrecauda.datos import Declaracion, ExperimentoE3b, InformeDelProductor, Medicion, MetaClave
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida, EntropiaInsuficiente
from qrecauda.puertos import Bitacora, Cifrador, ProductorDeClaves, Reloj, ReservaDeClaves, SondaDeMaquina, Temporizador

REGLA_SEMILLA_CLAVE = "semilla * 100 + i"
DECIMALES_MS = 4  # 0,1 µs
_HEX_LARGO = re.compile(r"[0-9a-fA-F]{32,}")
_BITS_LARGOS = re.compile(r"[01]{64,}|(?:[01], ?){63}[01]")


def p_latencia(latencias_ms: Sequence[float], p: float) -> float:
    """Percentil `higher` (el mismo que E3): el juez lo recalcula con esta misma función."""
    return float(np.percentile(np.asarray(latencias_ms, dtype=np.float64), p, method="higher")) if len(latencias_ms) else float("inf")


def tasa_neta_bps(claves: Sequence[dict[str, object]]) -> float:
    """Σ bits / Σ t_gen de las claves cuya generación terminó dentro de la ventana de R2 (marcadas `en_ventana`). 0 si no hubo ninguna."""
    dentro = [c for c in claves if c["en_ventana"]]
    t_s = sum(int(c["t_gen_ns"]) for c in dentro) / 1e9  # type: ignore[call-overload]
    return float(sum(int(c["bits"]) for c in dentro) / t_s) if dentro and t_s > 0 else 0.0  # type: ignore[call-overload]


def sin_claves(texto: str, prefijos: Sequence[str]) -> bool:
    """U4: ni un hex largo, ni una racha larga de bits, ni el prefijo de ninguna clave vista aparecen en `texto`."""
    return not (_HEX_LARGO.search(texto) or _BITS_LARGOS.search(texto) or any(p and p in texto for p in prefijos))


class _ReservaQueRecuerdaPrefijos:
    """Envuelve la fábrica de reservas y anota el prefijo (hex y bits) de cada clave que pasa, SÓLO para U4; no sale del ejecutor."""

    def __init__(self, crear: Callable[[Bits], ReservaDeClaves]) -> None:
        self._crear = crear
        self.prefijos: list[str] = []

    def __call__(self, clave: Bits) -> ReservaDeClaves:
        self.prefijos += [clave.a_bytes()[:16].hex() if len(clave) % 8 == 0 else "", "".join(str(int(b)) for b in clave.datos[:48])]
        return self._crear(clave)


class EjecutorE3b:
    """Implementa el puerto `Ejecutor` para E3b."""

    def __init__(
        self,
        productor: Callable[[Declaracion, int], ProductorDeClaves],
        cifrador: Callable[[], Cifrador],
        reserva: Callable[[Bits], ReservaDeClaves],
        reloj: Reloj,
        temporizador: Temporizador,
        sonda: SondaDeMaquina,
        bitacora: Bitacora | None = None,
        afinidad: Callable[[], Sequence[int]] | None = None,
    ) -> None:
        self._crear_productor, self._crear_cifrador, self._crear_reserva = productor, cifrador, reserva
        self._reloj, self._tempo, self._sonda, self._bit, self._afinidad = reloj, temporizador, sonda, bitacora, afinidad or (lambda: ())
        self._eventos: list[str] = []

    # ------------------------------------------------------------------ API

    def ejecutar(self, decl: Declaracion, semilla: int) -> Medicion:
        if decl.eureka != "E3b":
            raise EntradaInvalida(f"EjecutorE3b mide E3b, no {decl.eureka}")
        cfg = decl.tabla("configuracion")
        if cfg.get("semilla_clave") != REGLA_SEMILLA_CLAVE:
            raise EntradaInvalida(f"[configuracion].semilla_clave debe ser {REGLA_SEMILLA_CLAVE!r}, no {cfg.get('semilla_clave')!r}")
        if cfg.get("backend") != "aer_ruidoso" or cfg.get("mitigacion") != "twirling_propio":
            raise EntradaInvalida("E3b mide aer_ruidoso con twirling_propio; la declaración pide otra cosa")
        lam, dur = decl.numero("demanda", "tx_por_s"), decl.numero("demanda", "duracion_s")
        n = int(decl.numero("demanda", "transacciones"))
        bits_tx = int(decl.numero("demanda", "bits_por_transaccion"))
        if lam <= 0 or n != round(lam * dur) or bits_tx != BITS_POR_TRANSACCION:
            raise EntradaInvalida(f"[demanda]: {lam} tx/s × {dur} s ≠ {n} transacciones, o {bits_tx} bits/tx ≠ {BITS_POR_TRANSACCION}")
        consumo = lam * bits_tx
        if decl.numero("demanda", "consumo_bps") != consumo:
            raise EntradaInvalida(f"[demanda].consumo_bps debe ser λ·{bits_tx} = {consumo}")
        maximo = decl.numero("configuracion", "carga_previa_maxima")
        self._sonda.esperar_reposo(maximo, ESPERA_MAXIMA_S)  # la semilla anterior deja su propia carga en el promedio de 1 min
        carga = self._sonda.carga_previa()
        if not carga < maximo:
            raise CorridaInvalida(f"carga previa {carga:.2f} ≥ {maximo}: la máquina no está libre; semilla {semilla} no se mide (P.E3b)")

        grabadora = _ReservaQueRecuerdaPrefijos(self._crear_reserva)
        productor = self._crear_productor(decl, semilla)
        reserva = ReservaAsincrona(productor, grabadora, self._reloj, decl.numero("reserva", "espera_maxima_s"))
        servicio = ServicioDeTransaccionesAsincrono(reserva, self._crear_cifrador())
        txs = self._transacciones(semilla, n)
        self._eventos = []
        try:
            t0 = self._reloj.ahora_ns()  # R1
            productor.iniciar()
            primera = reserva.cebar()
            arranque_ns = self._reloj.ahora_ns() - t0
            self._registrar("arranque_e3b", semilla=semilla, arranque_ms=arranque_ns / 1e6, huella=primera.huella, bits=primera.bits)
            periodo_ns = round(1e9 / lam)  # R2
            cpu0 = self._sonda.cpu_proceso_ns()
            t_ini = self._reloj.ahora_ns()
            lat_ns: list[int] = []
            for i, tx in enumerate(txs):
                llegada = t_ini + i * periodo_ns
                self._tempo.esperar_hasta_ns(llegada)
                try:
                    servicio.ciclo(tx)
                except EntropiaInsuficiente:
                    break  # reserva agotada: `reserva.agotada` lo dice y T3 falla; las que faltan no se inventan
                lat_ns.append(self._reloj.ahora_ns() - llegada)
            t_fin = self._reloj.ahora_ns()
            cpu1 = self._sonda.cpu_proceso_ns()
        finally:
            informe = productor.detener()
        return self._medicion(decl, semilla, lam, dur, consumo, reserva, servicio, grabadora, informe, primera, arranque_ns, lat_ns,
                              t_ini, t_fin, (cpu1 - cpu0) / (t_fin - t_ini))  # fmt: skip

    # ------------------------------------------------------------------ resultado

    def _medicion(
        self, decl: Declaracion, semilla: int, lam: float, dur: float, consumo: float, reserva: ReservaAsincrona,
        servicio: ServicioDeTransaccionesAsincrono, grabadora: _ReservaQueRecuerdaPrefijos, informe: InformeDelProductor,
        primera: MetaClave, arranque_ns: int, lat_ns: list[int], t_ini: int, t_fin: int, cpu_consumidor: float,
    ) -> Medicion:  # fmt: skip
        lat_ms = [round(x / 1e6, DECIMALES_MS) for x in lat_ns]
        metas = informe.claves or tuple(reserva.metas)
        claves = [{**m.a_mapa(), "en_ventana": t_ini <= m.fin_ns <= t_fin} for m in metas]
        tasa = tasa_neta_bps(claves)
        limite = decl.numero("validez_un_hilo", "cpu_sobre_pared_maximo")
        cpu_prod = informe.cpu_sobre_pared if informe.pared_ns > 0 else float("inf")
        dentro = [c for c in claves if c["en_ventana"] and c["entregada"]]
        ventana_s = (t_fin - t_ini) / 1e9
        lat = np.asarray(lat_ms, dtype=np.float64)
        reporte: dict[str, object] = {
            "latencias_ms": lat_ms,
            "ventana_ns": [t_ini, t_fin],
            "periodo_ns": round(1e9 / lam),
            "arranque": primera.a_mapa(),
            "claves": claves,
            "cambios_de_clave": reserva.cambios,
            "esperas": reserva.esperas,
            "espera_ms": reserva.espera_ns / 1e6,
            "reserva_agotada": reserva.agotada,
            "mediana_ms": float(np.median(lat)) if lat.size else None,
            "p99_ms": p_latencia(lat_ms, 99) if lat.size else None,
            "min_ms": float(np.min(lat)) if lat.size else None,
            "max_ms": float(np.max(lat)) if lat.size else None,
            "tasa_entregada_ventana_bps": float(sum(int(c["bits"]) for c in dentro) / ventana_s) if ventana_s > 0 else 0.0,  # type: ignore[call-overload]
            "claves_rechazadas": [m.rechazos for m in metas],
            "bloqueado_por_cola_llena_ms": [m.bloqueado_ns / 1e6 for m in metas],
            "cpu": {
                "productor_con_hijos_sobre_pared": cpu_prod,
                "productor_propia_sobre_pared": informe.cpu_proceso_ns / informe.pared_ns if informe.pared_ns > 0 else None,
                "consumidor_sobre_pared": cpu_consumidor,
            },
            "afinidad": {"consumidor": list(self._afinidad()), "productor": list(informe.nucleos)},
            "productor_forzado": informe.forzado,
            "productor_pared_ms": informe.pared_ns / 1e6,
            "rotulos": sorted(reserva.rotulos),
            "origenes": sorted(reserva.origenes),
            "ida_y_vuelta_realizadas": servicio.realizadas,
        }
        self._registrar("resumen_e3b", semilla=semilla, transacciones=len(lat_ms), esperas=reserva.esperas, tasa_neta_bps=tasa,
                        p95_ms=p_latencia(lat_ms, decl.numero("criterios", "p_latencia")))  # fmt: skip
        texto = json.dumps(reporte, sort_keys=True, default=str) + "".join(self._eventos)
        rotulo = str(decl.tabla("controles_uso")["rotulo_esperado"])
        controles: dict[str, bool] = {
            "U1": servicio.ida_y_vuelta and servicio.realizadas > 0,
            "U2": servicio.nonces_repetidos == 0,
            "U3": servicio.pares_repetidos == 0 and len({c["huella"] for c in claves}) == len(claves),
            "U4": sin_claves(texto, grabadora.prefijos),
            "U5": reserva.rotulos == {rotulo} == {ROTULO_VALIDACION} and reserva.origenes == {"simulador_aer"},
            "T4": cpu_prod <= limite and cpu_consumidor <= limite and not informe.forzado,
        }
        maquina = {str(k): str(v) for k, v in self._sonda.maquina().items()}
        exp = ExperimentoE3b(
            decl.nodo_corrida, semilla, lam, dur, len(lat_ms), arranque_ns / 1e6, tasa, consumo,
            p_latencia(lat_ms, decl.numero("criterios", "p_latencia")), reserva.esperas, cpu_prod, cpu_consumidor,
            maquina, reporte=reporte,
        )  # fmt: skip
        return Medicion(e3b=(exp,), controles=controles)

    # ------------------------------------------------------------------ interno

    def _registrar(self, evento: str, **campos: object) -> None:
        self._eventos.append(json.dumps({"evento": evento, **campos}, sort_keys=True, default=str))
        if self._bit is not None:
            self._bit.registrar(evento, **campos)

    @staticmethod
    def _transacciones(semilla: int, n: int) -> list[Transaccion]:
        """Peaje y metro alternados, contenido sintético por semilla (como el perfil B de E3). Se arma ANTES de medir."""
        rng = np.random.default_rng(semilla)
        out = []
        for k in range(n):
            tipo = "peaje" if k % 2 == 0 else "metro"
            out.append(Transaccion(ESTACIONES[tipo][int(rng.integers(0, 3))], int(rng.integers(50, 2500)), f"T-pseudonimo-{k:05d}"))
        return out


__all__ = ["EjecutorE3b", "p_latencia", "sin_claves", "tasa_neta_bps"]
