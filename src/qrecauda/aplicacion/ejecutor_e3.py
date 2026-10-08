"""EjecutorE3: mide UNA semilla de E3 exactamente como la fija docs/preinscripciones/E3.md. No decide nada: decide el juez (F2.07).

Una repetición del perfil A (el que decide) = la cadena COMPLETA de extremo a extremo con un solo reloj monotónico:
fuente → mitigación → extracción (Peres + Toeplitz) → validación (M1–M5 en cruda/mitigada/clave y el 90B) → una transacción cifrada y
descifrada. `semilla·100 + i` siembra la repetición i (i = 0…); las primeras `calentamiento` se guardan y se excluyen de las estadísticas.
M6 = Σ len(clave) / Σ t_rep; M7 = p95 `higher` de t_rep. T4: CPU del proceso / pared ≤ 1,10 en CADA repetición (calentamiento incluido).

El perfil B (complementario, NO decide) y los controles U1–U5 salen de una reserva de claves ya generada: la clave de la ÚLTIMA repetición.

Convenciones que la preinscripción no fija con este detalle (⚠️ declaradas, no decididas en silencio):
- el 90B se corre sobre los primeros `muestras_90b` bits de la muestra CRUDA (antes de mitigar), una vez por repetición, dentro de t_rep;
- las etapas reparten t_rep sin hueco: extracción = pipeline − (fuente + mitigación + validación de M1–M5) y cuenta también el MCV;
- una clave que no pasa M1–M5 se regenera con otra semilla derivada (hasta 5 intentos); su tiempo suma a t_rep y se cuenta en
  `claves_rechazadas`; agotados los intentos, `CorridaInvalida`;
- una reserva corta en el perfil B (`EntropiaInsuficiente`) es resultado: se anota y U1 queda en falso, no se baja n_tx.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace

import numpy as np

from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado
from qrecauda.aplicacion.pipeline import ejecutar as ejecutar_pipeline
from qrecauda.aplicacion.transaccion import ServicioDeTransacciones, Transaccion, TransaccionCifrada
from qrecauda.datos import Declaracion, ExperimentoE3, Medicion, RuidoDeLectura
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import AutenticacionFallida, CorridaInvalida, EntradaInvalida, EntropiaInsuficiente
from qrecauda.dominio.metricas import METRICAS_DE_CLAVE, Medida
from qrecauda.dominio.muestra import Muestra, Origen
from qrecauda.puertos import (
    Bitacora,
    Cifrador,
    EstimadorDeEntropia,
    FuenteDeBits,
    LaboratorioDeLectura,
    Mitigador,
    Reloj,
    ReservaDeClaves,
    SondaDeMaquina,
    Validador,
)

REGLA_SEMILLA = "semilla * 100 + i"
ESPERA_MAXIMA_S = 900.0  # tope de la espera entre semillas a que la carga baje del máximo
MAX_INTENTOS = 5  # claves rechazadas por M1–M5 antes de declarar la corrida inválida
SALTO_REINTENTO = 10**9  # semilla del reintento k = semilla_i + k·SALTO (no choca con semilla·100 + i)
ETAPAS = ("fuente", "mitigacion", "extraccion", "validacion", "cifrado")
TX_A = Transaccion("Peaje de prueba", 1250, "T-pseudonimo-0000")  # sintética: ningún dato personal
ESTACIONES = {
    "peaje": ("Peaje Chillón", "Peaje Pucusana", "Peaje Villa"),
    "metro": ("Metro Villa El Salvador", "Metro Atocongo", "Metro Bayóvar"),
}


class _Cronometrada:
    """Envuelve un puerto y suma lo que tarda por el MISMO reloj de la corrida (nunca otro). Recuerda la última muestra."""

    def __init__(self, interior: object, reloj: Reloj) -> None:
        self.interior, self.reloj, self.ns = interior, reloj, 0
        self.ultima: Muestra | None = None

    def _medir(self, f: Callable[[], object]) -> object:
        t0 = self.reloj.ahora_ns()
        try:
            return f()
        finally:
            self.ns += self.reloj.ahora_ns() - t0


class _FuenteCronometrada(_Cronometrada):
    def generar(self, qubits: int, shots: int) -> Muestra:
        self.ultima = self._medir(lambda: self.interior.generar(qubits, shots))  # type: ignore[attr-defined,assignment]
        return self.ultima  # type: ignore[return-value]


class _MitigadorCronometrado(_Cronometrada):
    def mitigar(self, muestra: Muestra) -> Muestra:
        return self._medir(lambda: self.interior.mitigar(muestra))  # type: ignore[attr-defined,return-value]


class _ValidadorCronometrado(_Cronometrada):
    def evaluar(self, bits: Bits) -> tuple[Medida, ...]:
        return self._medir(lambda: self.interior.evaluar(bits))  # type: ignore[attr-defined,return-value]


class _ReservaGrabadora:
    """Anota cada (clave, nonce) que sale de la reserva: de ahí leen U3 y U4."""

    def __init__(self, interior: ReservaDeClaves) -> None:
        self._interior = interior
        self.pares: list[tuple[Bits, Bits]] = []

    @property
    def restantes(self) -> int:
        return self._interior.restantes

    def siguiente(self) -> tuple[Bits, Bits]:
        par = self._interior.siguiente()
        self.pares.append(par)
        return par


def _medidas(ms: Sequence[Medida]) -> list[list[object]]:
    return [[m.metrica.value, m.valor, m.cumple] for m in ms]


class EjecutorE3:
    """Implementa el puerto `Ejecutor` para E3."""

    def __init__(
        self,
        laboratorio: LaboratorioDeLectura,
        validador: Validador,
        estimador_90b: EstimadorDeEntropia,
        cifrador: Callable[[], Cifrador],
        reserva: Callable[[Bits], ReservaDeClaves],
        reloj: Reloj,
        sonda: SondaDeMaquina,
        bitacora: Bitacora | None = None,
    ) -> None:
        self._lab, self._validador, self._est90 = laboratorio, validador, estimador_90b
        self._crear_cifrador, self._crear_reserva = cifrador, reserva
        self._reloj, self._sonda, self._bit = reloj, sonda, bitacora

    # ------------------------------------------------------------------ API

    def ejecutar(self, decl: Declaracion, semilla: int) -> Medicion:
        if decl.eureka != "E3":
            raise EntradaInvalida(f"EjecutorE3 mide E3, no {decl.eureka}")
        cfg = decl.tabla("configuracion")
        if cfg.get("semilla_repeticion") != REGLA_SEMILLA:
            raise EntradaInvalida(f"[configuracion].semilla_repeticion debe ser {REGLA_SEMILLA!r}, no {cfg.get('semilla_repeticion')!r}")
        if cfg.get("backend") != "aer_ruidoso" or cfg.get("mitigacion") != "twirling_propio":
            raise EntradaInvalida("E3 mide aer_ruidoso con twirling_propio; la declaración pide otra cosa")
        maximo = decl.numero("configuracion", "carga_previa_maxima")
        self._sonda.esperar_reposo(maximo, ESPERA_MAXIMA_S)  # la semilla anterior deja su propia carga en el promedio de 1 min
        carga = self._sonda.carga_previa()
        if not carga < maximo:
            raise CorridaInvalida(f"carga previa {carga:.2f} ≥ {maximo}: la máquina no está libre; semilla {semilla} no se mide (P.E3)")
        n, calent = int(decl.numero("configuracion", "repeticiones")), int(decl.numero("configuracion", "calentamiento"))
        nivel = str(cfg["nivel_ruido"])
        par = decl.tabla("ruido_lectura")[nivel]
        ruido = RuidoDeLectura(nivel, (float(par[0]), float(par[1])))  # type: ignore[index]
        p = ParametrosPipeline(
            decl.qubits,
            decl.shots,
            epsilon=2.0 ** int(decl.numero("cadena", "epsilon_log2")),
            profundidad_peres=int(decl.numero("cadena", "profundidad_peres")),
        )
        reps = [self._repeticion(decl, ruido, p, semilla * 100 + i, i) for i in range(calent + n)]
        medidas = reps[calent:]
        exp, t4 = self._experimento(decl, semilla, n, calent, reps, medidas)
        controles = self._controles_de_uso(decl, semilla, reps[-1])
        controles["T4"] = t4
        perfil_b = controles.pop("_perfil_b")
        exp = replace(exp, reporte={**exp.reporte, "perfil_b": perfil_b})
        return Medicion(e3=(exp,), controles=controles)  # type: ignore[arg-type]

    # ------------------------------------------------------------------ una repetición del perfil A

    def _repeticion(self, decl: Declaracion, ruido: RuidoDeLectura, p: ParametrosPipeline, semilla_i: int, i: int) -> _Rep:
        """Una clave rechazada por M1–M5 se regenera con una semilla derivada; el intento perdido cuenta en t_rep."""
        bloque = int(decl.numero("configuracion", "twirling_bloque"))
        muestras_90b = int(decl.numero("validacion", "muestras_90b"))
        perdido_ns = 0
        cpu0, hijos0 = self._sonda.cpu_proceso_ns(), self._sonda.cpu_con_hijos_ns()  # la ventana de CPU cabe dentro de la de pared
        malas: list[str] = []
        for intento in range(MAX_INTENTOS):
            semilla_k = semilla_i + intento * SALTO_REINTENTO
            fuente = _FuenteCronometrada(self._lab.fuente(ruido, semilla_k), self._reloj)
            mit = _MitigadorCronometrado(self._lab.twirling(ruido, semilla_k, bloque), self._reloj)
            val = _ValidadorCronometrado(self._validador, self._reloj)
            t0 = self._reloj.ahora_ns()
            r = ejecutar_pipeline(fuente, val, self._reloj, p, mitigador=mit)
            t_pipe = self._reloj.ahora_ns()
            assert fuente.ultima is not None  # el pipeline llamó a la fuente
            h90 = self._est90.estimar(fuente.ultima.bits[:muestras_90b])
            t_90 = self._reloj.ahora_ns()
            if r.veredicto.calidad_de_clave_aprobada:
                break
            perdido_ns += t_90 - t0
            malas = [f"{m.metrica.name}={m.valor:.4g}" for m in r.veredicto.medidas if not m.cumple and m.metrica in METRICAS_DE_CLAVE]
        else:
            raise CorridaInvalida(
                f"repetición {i}: la clave no pasa M1–M5 en {MAX_INTENTOS} intentos ({', '.join(malas)}): no hay ciclo de cifrado que medir"
            )
        rechazos = intento
        cifrador = self._crear_cifrador()
        servicio = ServicioDeTransacciones(r, cifrador, self._crear_reserva)
        tc = servicio.cifrar(TX_A)
        servicio.descifrar(tc)
        cpu1, hijos1 = self._sonda.cpu_proceso_ns(), self._sonda.cpu_con_hijos_ns()
        t1 = self._reloj.ahora_ns()
        pared = (t1 - t0) + perdido_ns
        validacion_pipe = val.ns
        etapas = {
            "fuente": fuente.ns,
            "mitigacion": mit.ns,
            "extraccion": (t_pipe - t0) - fuente.ns - mit.ns - validacion_pipe,
            "validacion": validacion_pipe + (t_90 - t_pipe) + perdido_ns,  # incluye los intentos rechazados
            "cifrado": t1 - t_90,
        }
        if self._bit is not None:
            self._bit.registrar("repeticion_e3", i=i, semilla=semilla_i, t_rep_ms=pared / 1e6, longitud_bits=len(r.clave), h90b=h90)
        return _Rep(
            r, pared, etapas, (cpu1 - cpu0) / pared if pared else float("inf"), (hijos1 - hijos0) / pared if pared else float("inf"),
            h90, tc.rotulo, rechazos,
        )  # fmt: skip

    # ------------------------------------------------------------------ estadísticas

    def _experimento(
        self, decl: Declaracion, semilla: int, n: int, calent: int, todas: list[_Rep], medidas: list[_Rep]
    ) -> tuple[ExperimentoE3, bool]:
        t_ms = np.array([r.pared_ns / 1e6 for r in medidas])
        bits = np.array([len(r.resultado.clave) for r in medidas], dtype=np.float64)
        m6 = float(bits.sum() / (t_ms.sum() / 1e3))
        m7 = float(np.percentile(t_ms, 95, method="higher"))
        cv = float(t_ms.std(ddof=1) / t_ms.mean()) if len(t_ms) > 1 and t_ms.mean() > 0 else 0.0
        limite = decl.numero("validez_un_hilo", "cpu_sobre_pared_maximo")
        t4 = all(r.cpu_pared <= limite for r in todas)
        gen_s = np.array([r.resultado.segundos for r in medidas])
        reporte: dict[str, object] = {
            "t_rep_ms": t_ms.tolist(),
            "calentamiento_t_rep_ms": [r.pared_ns / 1e6 for r in todas[:calent]],
            "bits_clave": [int(b) for b in bits],
            "mediana_ms": float(np.median(t_ms)),
            "min_ms": float(t_ms.min()),
            "p5_tasa_bps": float(np.percentile(bits / (t_ms / 1e3), 5)),
            "cv_t_rep": cv,
            "inestable": cv > decl.numero("criterios", "cv_t_rep_aviso"),
            "etapas_ms": {e: [r.etapas[e] / 1e6 for r in medidas] for e in ETAPAS},
            "m6_solo_generacion_bps": float(bits.sum() / gen_s.sum()) if gen_s.sum() > 0 else float("inf"),
            "cpu_sobre_pared": [r.cpu_pared for r in todas],
            "cpu_con_hijos_sobre_pared": [r.cpu_hijos_pared for r in todas],
            "h_min_90b": [r.h90 for r in medidas],
            "claves_rechazadas": [r.rechazos for r in todas],
            "validacion": [{k: _medidas(v) for k, v in r.resultado.etapas} for r in medidas],
        }
        maquina = {str(k): str(v) for k, v in self._sonda.maquina().items()}
        return ExperimentoE3(decl.nodo_corrida, semilla, n, calent, m6, m7, float(t_ms.max()), maquina, reporte=reporte), t4

    # ------------------------------------------------------------------ perfil B y controles de uso

    def _controles_de_uso(self, decl: Declaracion, semilla: int, ultima: _Rep) -> dict[str, object]:
        b = decl.tabla("perfil_b")
        peaje, metro, total = (
            int(decl.numero("perfil_b", "peaje")),
            int(decl.numero("perfil_b", "metro")),
            int(decl.numero("perfil_b", "transacciones")),
        )
        if peaje != metro or peaje + metro != total:
            raise EntradaInvalida(f"perfil B: {peaje} peaje + {metro} metro no son las {total} transacciones alternadas declaradas")
        rng = np.random.default_rng(semilla)
        cifrador = self._crear_cifrador()
        grabadora: list[_ReservaGrabadora] = []

        def reserva(clave: Bits) -> ReservaDeClaves:
            grabadora.append(_ReservaGrabadora(self._crear_reserva(clave)))
            return grabadora[0]

        servicio = ServicioDeTransacciones(ultima.resultado, cifrador, reserva)
        originales: list[Transaccion] = []
        cifradas: list[TransaccionCifrada] = []
        ciclos_ns: list[int] = []
        ida_y_vuelta = True
        insuficiente = False
        for k in range(total):
            tipo = "peaje" if k % 2 == 0 else "metro"
            tx = Transaccion(ESTACIONES[tipo][int(rng.integers(0, 3))], int(rng.integers(50, 2500)), f"T-pseudonimo-{k:04d}")
            t0 = self._reloj.ahora_ns()
            try:
                tc = servicio.cifrar(tx)
            except EntropiaInsuficiente:
                insuficiente = True
                break
            vuelta = servicio.descifrar(tc)
            ciclos_ns.append(self._reloj.ahora_ns() - t0)
            ida_y_vuelta &= vuelta == tx
            originales.append(tx)
            cifradas.append(tc)
        hechas = len(cifradas)
        pares = grabadora[0].pares if grabadora else []
        u2_n, u3_n = int(decl.numero("controles_uso", "u2_casos")), int(decl.numero("controles_uso", "u3_casos"))
        controles: dict[str, object] = {
            "U1": ida_y_vuelta and hechas == total and not insuficiente,
            "U2": self._u2(servicio, cifradas, rng, u2_n),
            "U3": self._u3(cifrador, cifradas, pares, rng, u3_n),
            "U4": len({(c.a_bytes(), n.a_bytes()) for c, n in pares}) == len(pares),
            "U5": self._u5(decl, ultima, cifradas),
        }
        ciclos = np.array(ciclos_ns, dtype=np.float64) / 1e3
        controles["_perfil_b"] = {
            "decide": bool(b.get("decide", False)),
            "transacciones": hechas,
            "peaje": sum(1 for k in range(hechas) if k % 2 == 0),
            "metro": sum(1 for k in range(hechas) if k % 2 == 1),
            "entropia_insuficiente": insuficiente,
            "ciclo_us": {
                "mediana": float(np.median(ciclos)),
                "p95": float(np.percentile(ciclos, 95, method="higher")),
                "max": float(np.max(ciclos)),
            }
            if hechas
            else {"mediana": 0.0, "p95": 0.0, "max": 0.0},
            "tx_por_s": float(hechas / (ciclos.sum() / 1e6)) if hechas and ciclos.sum() > 0 else 0.0,
        }
        return controles

    @staticmethod
    def _falla(servicio: ServicioDeTransacciones, t: TransaccionCifrada) -> bool:
        try:
            servicio.descifrar(t)
        except AutenticacionFallida:
            return True
        return False

    def _u2(self, servicio: ServicioDeTransacciones, cifradas: list[TransaccionCifrada], rng: np.random.Generator, casos: int) -> bool:
        """Alterar 1 bit del cifrado, y por separado el dato asociado, en `casos` transacciones (por semilla): 100 % rechazadas."""
        if not cifradas:
            return False
        ok = True
        for idx in rng.choice(len(cifradas), size=min(casos, len(cifradas)), replace=False):
            t = cifradas[int(idx)]
            roto = bytearray(t.cifrado)
            bit = int(rng.integers(0, 8 * len(roto)))
            roto[bit // 8] ^= 1 << (bit % 8)
            ok &= self._falla(servicio, replace(t, cifrado=bytes(roto)))
            ok &= self._falla(servicio, replace(t, asociado=t.asociado + b"*"))
        return bool(ok)

    @staticmethod
    def _u3(
        cifrador: Cifrador, cifradas: list[TransaccionCifrada], pares: list[tuple[Bits, Bits]], rng: np.random.Generator, casos: int
    ) -> bool:
        """Descifrar con la clave de OTRA transacción falla en el 100 % de los casos."""
        n = min(len(cifradas), len(pares))
        if n < 2:
            return False
        ok = True
        for idx in rng.choice(n, size=min(casos, n), replace=False):
            i = int(idx)
            j = (i + 1 + int(rng.integers(0, n - 1))) % n  # siempre distinta de i
            try:
                cifrador.descifrar(pares[j][0], cifradas[i].nonce, cifradas[i].cifrado, cifradas[i].asociado)
                ok = False
            except AutenticacionFallida:
                pass
        return bool(ok)

    @staticmethod
    def _u5(decl: Declaracion, ultima: _Rep, cifradas: list[TransaccionCifrada]) -> bool:
        esperado = str(decl.tabla("controles_uso")["rotulo_esperado"])
        m = ultima.resultado.muestra
        rotulos = {ultima.rotulo, *(t.rotulo for t in cifradas)}
        return rotulos == {esperado} and m.origen is Origen.SIMULADOR_AER and not m.reclama_origen_cuantico


class _Rep:
    """Una repetición del perfil A ya medida."""

    __slots__ = ("cpu_hijos_pared", "cpu_pared", "etapas", "h90", "pared_ns", "rechazos", "resultado", "rotulo")

    def __init__(
        self,
        resultado: Resultado,
        pared_ns: int,
        etapas: dict[str, int],
        cpu_pared: float,
        cpu_hijos_pared: float,
        h90: float,
        rotulo: str,
        rechazos: int = 0,
    ) -> None:
        self.resultado, self.pared_ns, self.etapas = resultado, pared_ns, etapas
        self.cpu_pared, self.cpu_hijos_pared, self.h90, self.rotulo, self.rechazos = cpu_pared, cpu_hijos_pared, h90, rotulo, rechazos


__all__ = ["EjecutorE3", "FuenteDeBits", "Mitigador"]
