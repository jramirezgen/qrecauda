"""F6.03, reserva asíncrona de claves: una clave generada aparte, trozos de 352 bits que no se repiten y una transacción que los consume.

Tres piezas, todas sobre puertos (C1/C3):

- `GeneradorDeClaveAprobada` corre DENTRO del proceso productor: la misma cadena que mide E3 (fuente → mitigación → Peres → Toeplitz →
  validación M1–M5 → 90B), con la misma regla de regeneración (una clave rechazada se rehace con `semilla_i + k·10⁹`, hasta 5 intentos
  seguidos; `CorridaInvalida` si se agotan). El tiempo de TODOS los intentos suma al `t_gen` de esa clave.
- `ReservaAsincrona` es el lado del consumidor: reparte trozos de la clave en uso con el registro de consumo existente (`ReservaDeClaves`:
  nunca el mismo `(clave, nonce)` dos veces) y, al agotarse, toma la siguiente del productor. Cuenta las ESPERAS (clave necesaria y no
  lista) y no esconde un agotamiento: si no llega clave en `espera_maxima_s` lanza `EntropiaInsuficiente`.
- `ServicioDeTransaccionesAsincrono` cifra y descifra una transacción con un trozo de esa reserva; no guarda claves, sólo huellas de pares.

Nada de aquí imprime, escribe ni registra una clave: la bitácora y los informes ven `MetaClave` (huella de 12 hex) y contadores.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping

from qrecauda.aplicacion.ejecutor_e3 import MAX_INTENTOS, SALTO_REINTENTO
from qrecauda.aplicacion.pipeline import ParametrosPipeline
from qrecauda.aplicacion.pipeline import ejecutar as ejecutar_pipeline
from qrecauda.aplicacion.transaccion import (
    CONTEXTO_VALIDACION,
    ROTULO_CUANTICO,
    ROTULO_VALIDACION,
    Transaccion,
    TransaccionCifrada,
    exigir_uso_permitido,
)
from qrecauda.datos import ClaveEntregada, MetaClave, RuidoDeLectura
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida, EntropiaInsuficiente
from qrecauda.dominio.metricas import METRICAS_DE_CLAVE
from qrecauda.dominio.muestra import Muestra
from qrecauda.puertos import Cifrador, EstimadorDeEntropia, LaboratorioDeLectura, ProductorDeClaves, Reloj, ReservaDeClaves, Validador

BITS_POR_TRANSACCION = 352  # clave 256 + nonce 96
PASO_SEMILLA_HEREDADO = 100  # la regla de E3 y de la declaración de E3b: «semilla * 100 + i». Choca: (s, i=100) = (s+1, i=0).
PASO_SEMILLA = 10**6  # por omisión en lo nuevo: semillas consecutivas no comparten ninguna clave mientras haya < 10⁶ claves por semilla
HUELLA_HEX = 12  # lo único de una clave que puede salir del proceso


def huella_de(clave: Bits) -> str:
    """sha256 corto de una clave: sirve para distinguirla, no para reconstruirla."""
    return hashlib.sha256(clave.datos.tobytes()).hexdigest()[:HUELLA_HEX]


class _FuenteQueRecuerda:
    """Envuelve la fuente y guarda la última muestra cruda: el 90B se corre sobre ella (como en E3)."""

    def __init__(self, interior: object) -> None:
        self._interior = interior
        self.ultima: Muestra | None = None

    def generar(self, qubits: int, shots: int) -> Muestra:
        self.ultima = self._interior.generar(qubits, shots)  # type: ignore[attr-defined]
        return self.ultima


class GeneradorDeClaveAprobada:
    """Implementa el puerto `GeneradorDeClaves`: una clave aprobada por M1–M5 cada vez, con la cadena de E3."""

    def __init__(
        self,
        laboratorio: LaboratorioDeLectura,
        validador: Validador,
        estimador_90b: EstimadorDeEntropia,
        reloj: Reloj,
        ruido: RuidoDeLectura,
        parametros: ParametrosPipeline,
        bloque_twirling: int,
        muestras_90b: int,
        semilla: int,
        paso_semilla: int = PASO_SEMILLA,
        estimadores: Mapping[str, EstimadorDeEntropia] | None = None,
    ) -> None:
        """`paso_semilla` es el factor de «semilla · paso + i». Por omisión 10⁶ (semillas consecutivas no colisionan); E3b pasa 100 porque
        así lo declara y así se midió C.E3b (R.02: sus claves no cambian). `estimadores` (opcional) son los argumentos
        `estimador`/`estimador_de_fuente`/`estimador_de_salida` del pipeline, p. ej. los del dimensionado conservador; None = como hoy."""
        if paso_semilla < 1:
            raise EntradaInvalida(f"el paso de semilla debe ser positivo, llegó {paso_semilla}")
        self._lab, self._validador, self._est90, self._reloj = laboratorio, validador, estimador_90b, reloj
        self._ruido, self._p, self._bloque, self._muestras90b, self._semilla = ruido, parametros, bloque_twirling, muestras_90b, semilla
        self._paso, self._estimadores = paso_semilla, dict(estimadores or {})

    def generar(self, indice: int) -> ClaveEntregada:
        if indice < 0 or (indice >= self._paso and self._paso != PASO_SEMILLA_HEREDADO):
            raise EntradaInvalida(
                f"el índice de clave {indice} no cabe en el paso de semilla {self._paso}: reutilizaría la semilla de otra"
            )
        semilla_i = self._semilla * self._paso + indice  # E3 y E3b declaran «semilla * 100 + i» (paso heredado); lo nuevo, 10⁶
        t0 = self._reloj.ahora_ns()  # incluye armar la fuente y el mitigador: lo paga quien produce
        malas: list[str] = []
        for intento in range(MAX_INTENTOS):
            semilla_k = semilla_i + intento * SALTO_REINTENTO
            fuente = _FuenteQueRecuerda(self._lab.fuente(self._ruido, semilla_k))
            mit = self._lab.twirling(self._ruido, semilla_k, self._bloque)
            r = ejecutar_pipeline(fuente, self._validador, self._reloj, self._p, mitigador=mit, **self._estimadores)
            if fuente.ultima is None:  # el pipeline siempre llama a la fuente: si no, hay un bug en el pipeline o en el doble
                raise CorridaInvalida(f"clave {indice}: el pipeline no pidió muestra a la fuente")
            h90 = self._est90.estimar(fuente.ultima.bits[: self._muestras90b])
            if r.veredicto.calidad_de_clave_aprobada:
                fin = self._reloj.ahora_ns()
                rotulo = ROTULO_CUANTICO if r.muestra.reclama_origen_cuantico else ROTULO_VALIDACION
                meta = MetaClave(indice, semilla_i, len(r.clave), intento, fin - t0, h90, fin, huella_de(r.clave))
                return ClaveEntregada(r.clave, meta, rotulo, str(r.muestra.origen))
            malas = [f"{m.metrica.name}={m.valor:.4g}" for m in r.veredicto.medidas if not m.cumple and m.metrica in METRICAS_DE_CLAVE]
        raise CorridaInvalida(
            f"clave {indice}: no pasa M1–M5 en {MAX_INTENTOS} intentos seguidos ({', '.join(malas)}): el productor se detiene"
        )


class ReservaAsincrona:
    """Implementa `ReservaDeClaves` sobre un `ProductorDeClaves`: reparte trozos y pide la clave siguiente cuando hace falta."""

    def __init__(
        self,
        productor: ProductorDeClaves,
        crear_reserva: Callable[[Bits], ReservaDeClaves],
        reloj: Reloj,
        espera_maxima_s: float,
    ) -> None:
        self._productor, self._crear, self._reloj, self._espera_max = productor, crear_reserva, reloj, espera_maxima_s
        self._actual: ReservaDeClaves | None = None
        self.esperas = 0  # veces que hizo falta una clave y no estaba lista
        self.espera_ns = 0
        self.metas: list[MetaClave] = []  # de cada clave tomada, en orden
        self.rotulos: set[str] = set()
        self.origenes: set[str] = set()
        self.cambios: list[dict[str, object]] = []  # un registro por cambio de clave: cuánto costó y cuántas esperaban en la cola
        self.agotada = False

    @property
    def restantes(self) -> int:
        return self._actual.restantes if self._actual is not None else 0

    def cebar(self) -> MetaClave:
        """R1: bloquea hasta tener la primera clave. Es el cebado; no cuenta como espera de la demanda."""
        e = self._productor.tomar(None)
        if e is None:  # tomar(None) espera sin tope: sólo un doble malo devuelve None
            raise CorridaInvalida("el productor no entregó la clave de cebado")
        self._adoptar(e)
        return e.meta

    def siguiente(self) -> tuple[Bits, Bits]:
        recien = False
        while True:
            if self._actual is not None:
                try:
                    return self._actual.siguiente()
                except EntropiaInsuficiente:
                    if recien:
                        raise EntropiaInsuficiente("la clave recibida no alcanza para un solo trozo de 352 bits") from None
            self._avanzar()
            recien = True

    # ------------------------------------------------------------------ interno

    def _adoptar(self, e: ClaveEntregada) -> None:
        self._actual = self._crear(e.clave)
        self.metas.append(e.meta)
        self.rotulos.add(e.rotulo)
        self.origenes.add(e.origen)

    def _avanzar(self) -> None:
        t0 = self._reloj.ahora_ns()
        en_cola = self._productor.listas()
        e = self._productor.tomar(0.0)
        esperada = 0
        if e is None:
            self.esperas += 1
            e = self._productor.tomar(self._espera_max)
            esperada = self._reloj.ahora_ns() - t0
            self.espera_ns += esperada
            if e is None:
                self.agotada = True
                raise EntropiaInsuficiente(f"la reserva no recibió clave en {self._espera_max} s: agotada")
        self._adoptar(e)
        self.cambios.append({"huella": e.meta.huella, "indice": e.meta.indice, "ms": (self._reloj.ahora_ns() - t0) / 1e6,
                             "en_cola_antes": en_cola, "espera_ms": esperada / 1e6})  # fmt: skip


class ServicioDeTransaccionesAsincrono:
    """Cifra y descifra una transacción con el siguiente trozo de la reserva. Guarda huellas de pares, nunca claves."""

    def __init__(self, reserva: ReservaAsincrona, cifrador: Cifrador, *, contexto: str = CONTEXTO_VALIDACION) -> None:
        self._reserva, self._cifrador, self._contexto = reserva, cifrador, contexto
        self._pares: set[bytes] = set()
        self._nonces: set[bytes] = set()
        self.pares_repetidos = 0
        self.nonces_repetidos = 0
        self.realizadas = 0
        self.ida_y_vuelta = True

    def ciclo(self, tx: Transaccion) -> TransaccionCifrada:
        """Una transacción completa: cifra con un trozo nuevo, descifra y comprueba que vuelve igual."""
        clave, nonce = self._reserva.siguiente()
        exigir_uso_permitido(origen_cuantico=self._origen_cuantico(), contexto=self._contexto)  # tras `siguiente`: ya hay clave y rótulos
        k, n = clave.a_bytes(), nonce.a_bytes()
        asociado = tx.estacion.encode()
        cifrado = self._cifrador.cifrar(clave, nonce, tx.a_bytes(), asociado)
        vuelta = Transaccion.desde_bytes(self._cifrador.descifrar(clave, nonce, cifrado, asociado))
        par = hashlib.sha256(k + n).digest()
        self.pares_repetidos += par in self._pares
        self.nonces_repetidos += n in self._nonces
        self._pares.add(par)
        self._nonces.add(n)
        self.realizadas += 1
        self.ida_y_vuelta &= vuelta == tx
        rotulo = ROTULO_CUANTICO if self._origen_cuantico() else ROTULO_VALIDACION
        return TransaccionCifrada(cifrado, nonce, asociado, rotulo)

    def _origen_cuantico(self) -> bool:
        """Sólo si TODAS las claves tomadas lo son: una mezcla con una clave simulada no puede reclamar origen cuántico."""
        rotulos = self._reserva.rotulos
        return bool(rotulos) and rotulos <= {ROTULO_CUANTICO}
