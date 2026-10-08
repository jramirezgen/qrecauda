"""EjecutorE5: mide UNA semilla de E5 exactamente como la fija docs/preinscripciones/E5.md. No decide nada: decide el juez (`juez_e5`),
con los mismos criterios (`criterios_e5`).

Por semilla corre, para cada fuente (buena, Markov, Markov fuerte, periódica) y cada dimensionado (mcv, min_mcv_90b,
conservador), el pipeline
REAL de punta a punta y DESDE CERO: Aer, twirling, defecto, Peres, Toeplitz, validación M1–M5 y 90B. Misma semilla ⇒ misma
muestra (control P5,
que compara el sha256 de la muestra que entró a Peres). Un rechazo del pipeline (`EntropiaInsuficiente`) es un resultado, no una avería.

Convenciones que la preinscripción deja a la implementación (⚠️ declaradas):
- El 90B de control D5 va sobre los primeros `prefijo_90b` bits de la muestra que entra a Peres (la mitigada, con el defecto).
- La tasa es bits de clave / segundos de pared de la cadena entera (la definición de M6); en `conservador` incluye los dos 90B.
- Antes de cada semilla se espera el reposo de la máquina (`[maquina].carga_previa_maxima`); si no baja, la semilla no se mide (INVÁLIDA).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence

from qrecauda.aplicacion import criterios_e5 as c
from qrecauda.aplicacion.dimensionado import estimadores_conservadores
from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado
from qrecauda.aplicacion.pipeline import ejecutar as ejecutar_pipeline
from qrecauda.datos import Declaracion, ExperimentoE5, Medicion
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import EstimadorMinimo
from qrecauda.dominio.errores import CorridaInvalida, EntradaInvalida, EntropiaInsuficiente
from qrecauda.dominio.muestra import Muestra
from qrecauda.puertos import Bitacora, EstimadorDeEntropia, FuenteDeBits, Mitigador, Reloj, SondaDeMaquina, Validador

# (declaración, nombre de la fuente, semilla) → una fuente y un mitigador NUEVOS, con el defecto de esa fuente ya puesto
FabricaDeFuentes = Callable[[Declaracion, str, int], tuple[FuenteDeBits, Mitigador]]
DIMENSIONADOS = ("mcv", "min_mcv_90b", "conservador")


class _Cotas:
    """Envuelve un `EstimadorMinimo` y recuerda las cotas por separado (MCV del pool, 90B del pool) para el informe."""

    def __init__(self, interior: EstimadorMinimo) -> None:
        self._interior = interior
        self.ultimas: tuple[float, ...] | None = None

    def estimar(self, bits: Bits) -> float:
        self.ultimas = self._interior.por_cota(bits)
        return min(self.ultimas)


class _MitigadorQueRecuerda:
    """Guarda la muestra que sale del mitigador (con el defecto): es la que entra a Peres, aunque el pipeline luego aborte."""

    def __init__(self, interior: Mitigador) -> None:
        self._interior = interior
        self.ultima: Muestra | None = None

    def mitigar(self, muestra: Muestra) -> Muestra:
        self.ultima = self._interior.mitigar(muestra)
        return self.ultima


def _huella(bits: Bits) -> str:
    return hashlib.sha256(bits.datos.tobytes()).hexdigest()


class EjecutorE5:
    """Implementa el puerto `Ejecutor` para E5."""

    def __init__(
        self,
        fabrica: FabricaDeFuentes,
        validador: Validador,
        estimador_90b: EstimadorDeEntropia,
        reloj: Reloj,
        sonda: SondaDeMaquina,
        bitacora: Bitacora | None = None,
    ) -> None:
        self._fabrica, self._val, self._est90, self._reloj, self._sonda, self._bit = (
            fabrica,
            validador,
            estimador_90b,
            reloj,
            sonda,
            bitacora,
        )

    # ------------------------------------------------------------------ API

    def ejecutar(self, decl: Declaracion, semilla: int) -> Medicion:
        if decl.eureka != "E5":
            raise EntradaInvalida(f"EjecutorE5 mide E5, no {decl.eureka}")
        dimensionados = decl.lista("dimensionados", "ids")
        if tuple(dimensionados) != DIMENSIONADOS:
            raise EntradaInvalida(f"[dimensionados].ids de E5 debe ser {DIMENSIONADOS}, trae {dimensionados}")
        maximo = decl.numero("maquina", "carga_previa_maxima")
        self._sonda.esperar_reposo(maximo, decl.numero("maquina", "reposo_maximo_s"))
        carga = self._sonda.carga_previa()
        if not carga < maximo:
            raise CorridaInvalida(f"carga previa {carga:.2f} ≥ {maximo}: la máquina no está libre; semilla {semilla} no se mide (P.E5)")
        p = ParametrosPipeline(
            decl.qubits,
            decl.shots,
            epsilon=2.0 ** int(decl.numero("cadena", "epsilon_log2")),
            profundidad_peres=int(decl.numero("cadena", "profundidad_peres")),
        )
        prefijo = int(decl.numero("dimensionados", "prefijo_90b"))
        fuentes = decl.lista("fuentes", "ids")
        exps = tuple(self._fuente(decl, nombre, semilla, p, prefijo) for nombre in fuentes)
        defectuosas = decl.lista("fuentes", "defectuosas")
        crit = decl.tabla("controles")
        controles = {
            "D5": c.d5_cumple(exps, float(crit["d5_techo_90b_defectuosa"]), float(crit["d5_piso_90b_buena"]), defectuosas),  # type: ignore[arg-type]
            "P5": c.p5_cumple(exps),
        }
        if self._bit is not None:
            self._bit.registrar("semilla_e5", semilla=semilla, controles=controles)
        return Medicion(e5=exps, controles=controles)

    # ------------------------------------------------------------------ piezas

    def _fuente(self, decl: Declaracion, nombre: str, semilla: int, p: ParametrosPipeline, prefijo: int) -> ExperimentoE5:
        resultados: list[Mapping[str, object]] = []
        entrada: Muestra | None = None  # la muestra que entró a Peres (idéntica en los tres dimensionados: lo comprueba P5)
        for dim in DIMENSIONADOS:
            r, entrada = self._dimensionado(decl, nombre, dim, semilla, p, prefijo)
            resultados.append(r)
        assert entrada is not None
        return ExperimentoE5(
            corrida=decl.nodo_corrida,
            semilla=semilla,
            fuente=nombre,
            bits_crudos=len(entrada.bits),
            h_90b_fuente=self._est90.estimar(entrada.bits[:prefijo]),
            parametros=self._parametros(decl, nombre, prefijo),
            resultados=tuple(resultados),
        )

    @staticmethod
    def _parametros(decl: Declaracion, nombre: str, prefijo: int) -> Mapping[str, object]:
        base: dict[str, object] = {"prefijo_90b": prefijo, "p_fresca_max": decl.numero("defectos", "p_fresca_max")}
        if nombre == "buena":
            return {**base, "tipo": "ninguno"}
        d = decl.tabla("defectos")[nombre]
        if not isinstance(d, Mapping):
            raise EntradaInvalida(f"[defectos.{nombre}] debe ser una tabla")
        return {**base, **{k: v for k, v in d.items() if isinstance(v, str | int | float)}}

    def _dimensionado(
        self, decl: Declaracion, nombre: str, dim: str, semilla: int, p: ParametrosPipeline, prefijo: int
    ) -> tuple[Mapping[str, object], Muestra]:
        fuente, mitigador = self._fabrica(decl, nombre, semilla)
        mit = _MitigadorQueRecuerda(mitigador)
        cotas: _Cotas | None = None
        kw: dict[str, EstimadorDeEntropia] = {}
        if dim != "mcv":  # «mcv» es el pipeline de 0.1.0, sin un solo argumento nuevo
            est = estimadores_conservadores(self._est90, prefijo)  # sin `qubits`: exactamente lo preinscrito
            cotas = _Cotas(est.minimo)
            kw = {"estimador": cotas, "estimador_de_salida": est.de_salida}
            if dim == "conservador":
                kw["estimador_de_fuente"] = est.de_fuente
        try:
            r = ejecutar_pipeline(fuente, self._val, self._reloj, p, mitigador=mit, **kw)
        except EntropiaInsuficiente as e:
            assert mit.ultima is not None  # la muestra se produjo antes de dimensionar
            return self._rechazo(dim, mit.ultima, str(e)), mit.ultima
        assert mit.ultima is not None
        return self._entrega(dim, r, mit.ultima, cotas), mit.ultima

    @staticmethod
    def _rechazo(dim: str, entrada: Muestra, motivo: str) -> Mapping[str, object]:
        return {
            "dimensionado": dim, "estado": "rechazada", "motivo": motivo, "sha256_muestra": _huella(entrada.bits),
            "bits_pool": None, "h_mcv_pool": None, "h_90b_pool": None, "h_90b_fuente": None, "h_efectiva": None,
            "bits_clave": 0, "medidas": [], "segundos": None, "tasa_bps": None,
        }  # fmt: skip

    @staticmethod
    def _entrega(dim: str, r: Resultado, entrada: Muestra, cotas: _Cotas | None) -> Mapping[str, object]:
        mcv, b90 = (r.h_min, None) if cotas is None or cotas.ultimas is None else cotas.ultimas
        return {
            "dimensionado": dim, "estado": "entregada", "motivo": "", "sha256_muestra": _huella(entrada.bits),
            "bits_pool": r.bits_extraidos, "h_mcv_pool": mcv, "h_90b_pool": b90, "h_90b_fuente": r.h_fuente, "h_efectiva": r.h_min,
            "bits_clave": len(r.clave),
            "medidas": [[m.metrica.value, m.valor, m.umbral, m.cumple] for m in r.veredicto.medidas],
            "segundos": r.segundos, "tasa_bps": len(r.clave) / r.segundos if r.segundos > 0 else None,
        }  # fmt: skip


def nombres_de(exps: Sequence[ExperimentoE5]) -> tuple[str, ...]:
    return tuple(e.fuente for e in exps)
