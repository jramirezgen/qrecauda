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
from collections.abc import Callable

from qrecauda.aplicacion.ejecutor_e3 import MAX_INTENTOS, SALTO_REINTENTO
from qrecauda.aplicacion.pipeline import ParametrosPipeline
from qrecauda.aplicacion.pipeline import ejecutar as ejecutar_pipeline
from qrecauda.aplicacion.transaccion import ROTULO_CUANTICO, ROTULO_VALIDACION, Transaccion, TransaccionCifrada
from qrecauda.datos import ClaveEntregada, MetaClave, RuidoDeLectura
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.errores import CorridaInvalida, EntropiaInsuficiente
from qrecauda.dominio.metricas import METRICAS_DE_CLAVE
from qrecauda.dominio.muestra import Muestra
from qrecauda.puertos import Cifrador, EstimadorDeEntropia, LaboratorioDeLectura, ProductorDeClaves, Reloj, ReservaDeClaves, Validador

BITS_POR_TRANSACCION = 352  # clave 256 + nonce 96
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
    ) -> None:
        self._lab, self._validador, self._est90, self._reloj = laboratorio, validador, estimador_90b, reloj
        self._ruido, self._p, self._bloque, self._muestras90b, self._semilla = ruido, parametros, bloque_twirling, muestras_90b, semilla

    def generar(self, indice: int) -> ClaveEntregada:
        semilla_i = self._semilla * 100 + indice  # la regla de E3: «semilla * 100 + i»
        t0 = self._reloj.ahora_ns()  # incluye armar la fuente y el mitigador: lo paga quien produce
        malas: list[str] = []
        for intento in range(MAX_INTENTOS):
            semilla_k = semilla_i + intento * SALTO_REINTENTO
            fuente = _FuenteQueRecuerda(self._lab.fuente(self._ruido, semilla_k))
            mit = self._lab.twirling(self._ruido, semilla_k, self._bloque)
            r = ejecutar_pipeline(fuente, self._validador, self._reloj, self._p, mitigador=mit)
            assert fuente.ultima is not None  # el pipeline llamó a la fuente
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

    def __init__(self, reserva: ReservaAsincrona, cifrador: Cifrador) -> None:
        self._reserva, self._cifrador = reserva, cifrador
        self._pares: set[bytes] = set()
        self._nonces: set[bytes] = set()
        self.pares_repetidos = 0
        self.nonces_repetidos = 0
        self.realizadas = 0
        self.ida_y_vuelta = True

    def ciclo(self, tx: Transaccion) -> TransaccionCifrada:
        """Una transacción completa: cifra con un trozo nuevo, descifra y comprueba que vuelve igual."""
        clave, nonce = self._reserva.siguiente()
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
        rotulo = ROTULO_VALIDACION if self._reserva.rotulos <= {ROTULO_VALIDACION} else ROTULO_CUANTICO
        return TransaccionCifrada(cifrado, nonce, asociado, rotulo)
