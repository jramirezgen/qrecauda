"""F7.07 `qrecauda demo`: la cadena entera en un minuto, con tres (o cuatro) fuentes lado a lado.

Sólo conoce puertos y casos de uso (C1): las fuentes, el validador y el cifrado llegan inyectados. Es una DEMOSTRACIÓN, no una
medición preinscrita: no escribe en `registro/` y no decide ningún criterio. Las cifras son de la corrida que la imprime.

El rótulo es parte del resultado, no un adorno: todo lo que no sea hardware IBM real se rotula «simulado: Aer es pseudoaleatorio,
sin origen cuántico» (D-002); y aun con hardware real la batería NIST NO certifica aleatoriedad cuántica.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado
from qrecauda.aplicacion.pipeline import ejecutar as ejecutar_pipeline
from qrecauda.aplicacion.transaccion import ServicioDeTransacciones, Transaccion
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.metricas import Metrica
from qrecauda.dominio.muestra import Origen
from qrecauda.puertos import EstimadorDeEntropia, FuenteDeBits, Mitigador, Reloj, Validador

ROTULO_SIMULADO = "simulado: Aer es pseudoaleatorio, sin origen cuántico"
ROTULO_REAL = "hardware IBM: origen físico real; la batería NIST no certifica aleatoriedad cuántica"
ROTULO_PRNG = "clásico: PRNG determinista dada la semilla"
_ROTULO_DE = {Origen.PRNG_CLASICO: ROTULO_PRNG, Origen.SIMULADOR_AER: ROTULO_SIMULADO, Origen.HARDWARE_IBM: ROTULO_REAL}

PEAJE = Transaccion("Peaje Villa", 4500, "tarjeta-****-1234")
METRO = Transaccion("Metro Gamarra", 500, "tarjeta-****-5678")


@dataclass(frozen=True, slots=True)
class RamaSolicitada:
    """Una columna de la tabla: nombre, fuente y (opcional) mitigador. El orden importa: la clave que cifra sale de la última aprobada."""

    nombre: str
    fuente: FuenteDeBits
    mitigador: Mitigador | None = None
    shots: int | None = None  # None: los de la demo; el hardware reparte los suyos entre la cara cruda y la del twirling


@dataclass(frozen=True, slots=True)
class RamaDemo:
    nombre: str
    origen: Origen
    rotulo: str
    m1_cruda: float  # |p̂(1) − ½| de la muestra tal como salió de la fuente
    m1_mitigada: float | None  # tras el twirling; None si la rama no mitiga
    m1_clave: float
    min_entropia: float  # M2 de la clave
    p_monobit: float
    p_runs: float
    p_chi2: float
    bits_clave: int
    aprobada: bool  # M1–M5 de la clave
    segundos: float


@dataclass(frozen=True, slots=True)
class TransaccionDemo:
    nombre: str
    rama: str
    claro: str
    bytes_cifrados: int
    nonce_hex: str
    cifrado_hex: str  # sólo el arranque: es una demostración, no un volcado
    descifrado_ok: bool
    rotulo: str


@dataclass(frozen=True, slots=True)
class ResultadoDemo:
    ramas: tuple[RamaDemo, ...]
    transacciones: tuple[TransaccionDemo, ...]
    qubits: int
    shots: int
    fuente: str  # «aer» | «ibm» | «ensayo»
    rapido: bool
    avisos: tuple[str, ...] = ()

    @property
    def rotulo(self) -> str:
        """El rótulo del encabezado: el simulado SIEMPRE, salvo que TODAS las filas sean hardware real."""
        return ROTULO_REAL if self.ramas and all(r.origen is Origen.HARDWARE_IBM for r in self.ramas) else ROTULO_SIMULADO


def _valor(r: Resultado, etapa: str, m: Metrica) -> float:
    for medida in r.medidas_de(etapa):
        if medida.metrica is m:
            return medida.valor
    raise EntradaInvalida(f"el validador no trae {m.value} en la etapa {etapa!r}: la demo necesita M1, M3, M4 y M5")


def _rama(nombre: str, r: Resultado) -> RamaDemo:
    v = r.veredicto
    por_metrica = {m.metrica: m.valor for m in v.medidas}
    return RamaDemo(
        nombre=nombre,
        origen=r.muestra.origen,
        rotulo=_ROTULO_DE[r.muestra.origen],
        m1_cruda=_valor(r, "cruda", Metrica.SESGO),
        m1_mitigada=_valor(r, "mitigada", Metrica.SESGO) if "mitigada" in dict(r.etapas) else None,
        m1_clave=_valor(r, "clave", Metrica.SESGO),
        min_entropia=por_metrica[Metrica.MIN_ENTROPIA],
        p_monobit=_valor(r, "clave", Metrica.MONOBIT),
        p_runs=_valor(r, "clave", Metrica.RUNS),
        p_chi2=_valor(r, "clave", Metrica.CHI2),
        bits_clave=len(r.clave),
        aprobada=v.calidad_de_clave_aprobada,
        segundos=r.segundos,
    )


def _transaccion(nombre: str, rama: str, tx: Transaccion, servicio: ServicioDeTransacciones) -> TransaccionDemo:
    sellada = servicio.cifrar(tx)
    return TransaccionDemo(
        nombre=nombre,
        rama=rama,
        claro=tx.a_bytes().decode(),
        bytes_cifrados=len(sellada.cifrado),
        nonce_hex=sellada.nonce.a_bytes().hex(),
        cifrado_hex=sellada.cifrado[:16].hex() + "…",
        descifrado_ok=servicio.descifrar(sellada) == tx,
        rotulo=sellada.rotulo,
    )


def correr_demo(
    ramas: Sequence[RamaSolicitada],
    validador: Validador,
    reloj: Reloj,
    p: ParametrosPipeline,
    crear_servicio: Callable[[Resultado], ServicioDeTransacciones],
    *,
    fuente: str,
    rapido: bool,
    avisos: Sequence[str] = (),
    estimadores: Mapping[str, EstimadorDeEntropia] | None = None,
) -> ResultadoDemo:
    """Corre el pipeline real una vez por rama y cifra un peaje y un trayecto de Metro con la clave de la última rama aprobada.

    `estimadores` (opcional) son los argumentos `estimador`, `estimador_de_fuente` y `estimador_de_salida` del pipeline, p. ej. los del
    dimensionado conservador; por omisión (None) es el pipeline de 0.1.0, sin un solo argumento nuevo."""
    if not ramas:
        raise EntradaInvalida("la demo necesita al menos una rama")
    resultados = [
        (
            r,
            ejecutar_pipeline(
                r.fuente,
                validador,
                reloj,
                p if r.shots is None else replace(p, shots=r.shots),
                mitigador=r.mitigador,
                **(estimadores or {}),
            ),
        )
        for r in ramas
    ]
    filas = tuple(_rama(r.nombre, res) for r, res in resultados)
    aprobadas = [(r, res) for r, res in resultados if res.veredicto.calidad_de_clave_aprobada]
    txs: tuple[TransaccionDemo, ...] = ()
    if aprobadas:
        elegida, res = aprobadas[-1]
        servicio = crear_servicio(res)
        txs = (
            _transaccion("peaje", elegida.nombre, PEAJE, servicio),
            _transaccion("metro", elegida.nombre, METRO, servicio),
        )
    return ResultadoDemo(filas, txs, p.qubits, p.shots, fuente, rapido, tuple(avisos))
