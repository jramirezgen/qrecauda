"""Puertos: lo que el núcleo necesita del mundo, como `Protocol`. Cada adaptador implementa UNO (contrato C2)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from qrecauda.datos import ClaveEntregada, Declaracion, InformeDelProductor, Medicion, RuidoDeLectura
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.metricas import Medida
from qrecauda.dominio.muestra import Muestra


class FuenteDeBits(Protocol):
    """Hadamard + medición (o su sustituto). Devuelve bits crudos con su origen declarado."""

    def generar(self, qubits: int, shots: int) -> Muestra: ...


class Mitigador(Protocol):
    """Reduce el sesgo de lectura de una muestra. No inventa bits: devuelve otra `Muestra` marcada `mitigada`."""

    def mitigar(self, muestra: Muestra) -> Muestra: ...


class Validador(Protocol):
    """Mide M1–M5 sobre bits ya extraídos. Las métricas de tiempo (M6, M7) las pone la aplicación con el `Reloj`."""

    def evaluar(self, bits: Bits) -> tuple[Medida, ...]: ...


class EstimadorDeEntropia(Protocol):
    """Cota inferior de min-entropía por bit de una secuencia. El pipeline dimensiona la clave con ella, así que NO puede
    ser la misma función que luego la «certifica»: el adaptador 90B (S.04) es el contraste independiente."""

    def estimar(self, bits: Bits) -> float: ...


class EstimadorDeSesgo(Protocol):
    """⟨Z⟩ de una fuente con y sin mitigar. ZNE/PEC viven aquí, no en `Mitigador`: devuelven una estimación, no bits."""

    def estimar(self, muestra: Muestra) -> float: ...


class FuenteDeSemilla(Protocol):
    """Bits uniformes independientes para la semilla de Toeplitz (D-004), por un camino que no sea el del pool de datos."""

    def semilla(self, longitud: int) -> Bits: ...


class Cifrador(Protocol):
    """Cifrado autenticado con una clave QRNG (caso de uso del peaje/Metro)."""

    def cifrar(self, clave: Bits, nonce: Bits, texto: bytes, asociado: bytes) -> bytes: ...

    def descifrar(self, clave: Bits, nonce: Bits, cifrado: bytes, asociado: bytes) -> bytes: ...


class ReservaDeClaves(Protocol):
    """Reparte una clave certificada en pares (clave, nonce) que salen una sola vez; sin bits suficientes, `EntropiaInsuficiente`."""

    @property
    def restantes(self) -> int: ...

    def siguiente(self) -> tuple[Bits, Bits]: ...


class GeneradorDeClaves(Protocol):
    """Produce, una tras otra, claves aprobadas por M1–M5 con la cadena completa (F6.03). Corre dentro del proceso productor."""

    def generar(self, indice: int) -> ClaveEntregada: ...


class ProductorDeClaves(Protocol):
    """Un productor de claves que corre aparte del consumidor (F6.03). Las claves llegan por una cola acotada, en orden y una sola vez.

    `tomar(0)` no espera; `tomar(None)` espera sin límite; si el productor falla, lanza `CorridaInvalida` con la causa.
    """

    def iniciar(self) -> None: ...

    def tomar(self, espera_s: float | None) -> ClaveEntregada | None: ...  # None: no hubo clave en `espera_s`

    def listas(self) -> int: ...  # claves esperando en la cola (aproximado)

    def detener(self) -> InformeDelProductor: ...


class Temporizador(Protocol):
    """Espera hasta un instante del reloj monotónico (E3b: llegadas programadas de la demanda)."""

    def esperar_hasta_ns(self, instante_ns: int) -> None: ...


class LaboratorioDeLectura(Protocol):
    """Fabrica, para un ruido de lectura dado, las piezas con que E2 mide el sesgo. La semilla es la de la celda."""

    def fuente(self, ruido: RuidoDeLectura, semilla: int) -> FuenteDeBits: ...

    def twirling(self, ruido: RuidoDeLectura, semilla: int, bloque: int) -> Mitigador: ...

    def zne(self, ruido: RuidoDeLectura, semilla: int) -> EstimadorDeSesgo: ...

    def pec(self, ruido: RuidoDeLectura, semilla: int) -> EstimadorDeSesgo: ...

    def sesgo_mthree(self, ruido: RuidoDeLectura, qubits: int, shots: int, semilla: int) -> tuple[float, float]:
        """CONTRASTE (D-009): sesgo medio por qubit antes y después de mthree. `FuenteNoDisponible` si el extra no está."""
        ...


class SondaDeMaquina(Protocol):
    """Lo que E3 necesita saber de la máquina en que mide: carga, tiempo de CPU y quién es."""

    def carga_previa(self) -> float: ...  # carga media de 1 minuto

    def esperar_reposo(self, maximo: float, tope_s: float) -> None: ...  # espera (con tope) a que la carga baje de `maximo`

    def cpu_proceso_ns(self) -> int: ...  # `time.process_time_ns`: CPU de todos los hilos del proceso

    def cpu_con_hijos_ns(self) -> int: ...  # lo anterior más los hijos ya esperados (p. ej. el binario del 90B)

    def maquina(self) -> Mapping[str, str]: ...


class Almacen(Protocol):
    """Persistencia de artefactos canónicos. Append-only: guardar un nombre que ya existe es un error."""

    def guardar(self, nombre: str, artefacto: Mapping[str, object]) -> str: ...  # devuelve el sha256 del contenido

    def leer(self, nombre: str) -> dict[str, object]: ...


class Reloj(Protocol):
    def ahora_ns(self) -> int: ...


class Bitacora(Protocol):
    def registrar(self, evento: str, **campos: object) -> None: ...


class Ejecutor(Protocol):
    """Mide UNA semilla de una eureka según su declaración: artefactos tipados y resultado de los controles. No decide nada."""

    def ejecutar(self, declaracion: Declaracion, semilla: int) -> Medicion: ...


class Historial(Protocol):
    """El historial git como testigo de que la preinscripción va ANTES de la corrida."""

    def commit_actual(self) -> str: ...

    def ultimo_commit(self, rutas: tuple[str, ...]) -> str: ...  # el último commit que tocó alguna de esas rutas

    def modificado(self, rutas: tuple[str, ...]) -> bool: ...  # cambios sin commit en esas rutas

    def precede(self, antes: str, despues: str) -> bool: ...  # `git merge-base --is-ancestor antes despues`


class LibroDeVeredictos(Protocol):
    """Registro append-only de veredictos (registro/veredictos.jsonl): una línea por veredicto, nunca se reescribe."""

    def anadir(self, linea: Mapping[str, object]) -> None: ...
