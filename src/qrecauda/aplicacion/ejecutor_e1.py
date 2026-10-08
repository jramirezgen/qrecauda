"""EjecutorE1: mide UNA semilla de E1 exactamente como la fija docs/preinscripciones/E1.md (con su enmienda del 2026-10-07). No decide
nada: decide el juez (`_juzgar_e1`), con los mismos criterios (`criterios_e1`).

Por semilla produce las cuatro corridas que el plan separa (C.E1a…C.E1d), todas con el pipeline REAL salvo la fuente:
- C.E1a  PRNG clásico, sin mitigación: control negativo N1 (la batería no distingue origen).
- C.E1b  Aer ruidoso (nivel medio) sin mitigar: B1 y control D1 (el detector ve el sesgo inyectado).
- C.E1c  lo mismo con `twirling_propio` (bloque 200): M-1 (mitigada) y M-2 (clave).
- C.E1d  fuentes sintéticas defectuosas e ideal, de `bits` bits, con M1/M3/M4/M5, la cota MCV y el 90B: control positivo P1.

Convenciones que la preinscripción no fija con ese detalle (⚠️ declaradas, no decididas en silencio):
- M1 se mide en los tres puntos con `dominio.entropia.sesgo`, también si el validador (NIST) sólo trae M3, M4, M5: `_ConM1`.
- El 90B va sobre los primeros `[validacion].muestras_90b` bits de la cruda y de la mitigada (informativo; sólo decide en C.E1d).
  Una muestra con la MISMA huella sha256 reutiliza el 90B ya calculado (cuesta minutos y es función de los bits): la cruda de
  C.E1c es la de C.E1b si el twirling no la toca, y eso se registra (`sha256_muestra_cruda`), no se supone.
- La proporción NIST de la clave (93 × 10 240, α = 0,01) se pide al puerto `proporciones`; sólo se reporta.
- Los controles N1, D1 y P1 salen de `criterios_e1`, los mismos que el juez recalcula de los artefactos.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping

from qrecauda.aplicacion import criterios_e1 as c
from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado
from qrecauda.aplicacion.pipeline import ejecutar as ejecutar_pipeline
from qrecauda.datos import Declaracion, InformeCorrida, Medicion, MedidaDeFuente, RuidoDeLectura
from qrecauda.dominio.bits import Bits
from qrecauda.dominio.entropia import min_entropia_mcv, sesgo
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.metricas import Medida, medir
from qrecauda.dominio.muestra import Muestra
from qrecauda.puertos import Bitacora, EstimadorDeEntropia, FuenteDeBits, Historial, LaboratorioDeLectura, Reloj, Validador

# (bits, secuencias, longitud, alfa) → por prueba {aprobados, total, proporcion, minimo, cumple}; lo da el adaptador NIST
Proporciones = Callable[[Bits, int, int, float], Mapping[str, Mapping[str, object]]]
FuentesDeControl = Callable[[Declaracion, int], Mapping[str, FuenteDeBits]]


class _ConM1:
    """Añade M1 = |p̂(1) − ½| al validador si éste no lo trae: la preinscripción mide M1 en cruda, mitigada y clave (P.E0, regla 4)."""

    def __init__(self, interior: Validador) -> None:
        self._interior = interior

    def evaluar(self, bits: Bits) -> tuple[Medida, ...]:
        ms = self._interior.evaluar(bits)
        return ms if any(m.metrica is c.M1 for m in ms) else (medir(c.M1, sesgo(bits)), *ms)


class _Registradora:
    """Envuelve una fuente y recuerda la última muestra CRUDA: el pipeline sólo devuelve la que entró al extractor (la mitigada)."""

    def __init__(self, interior: FuenteDeBits) -> None:
        self._interior = interior
        self.ultima: Muestra | None = None

    def generar(self, qubits: int, shots: int) -> Muestra:
        self.ultima = self._interior.generar(qubits, shots)
        return self.ultima

    @property
    def cruda(self) -> Muestra:
        assert self.ultima is not None  # el pipeline llamó a la fuente
        return self.ultima


def _huella(bits: Bits) -> str:
    return hashlib.sha256(bits.datos.tobytes()).hexdigest()


class EjecutorE1:
    """Implementa el puerto `Ejecutor` para E1."""

    def __init__(
        self,
        laboratorio: LaboratorioDeLectura,
        prng: Callable[[int], FuenteDeBits],
        fuentes_de_control: FuentesDeControl,
        validador: Validador,
        estimador_90b: EstimadorDeEntropia,
        reloj: Reloj,
        historial: Historial,
        entorno: Callable[[], Mapping[str, str]],
        proporciones: Proporciones,
        bitacora: Bitacora | None = None,
    ) -> None:
        self._lab, self._prng, self._control = laboratorio, prng, fuentes_de_control
        self._val, self._est90, self._reloj = _ConM1(validador), estimador_90b, reloj
        self._historial, self._entorno, self._prop, self._bit = historial, entorno, proporciones, bitacora
        self._validador_nombre = type(validador).__name__

    # ------------------------------------------------------------------ API

    def ejecutar(self, decl: Declaracion, semilla: int) -> Medicion:
        if decl.eureka != "E1":
            raise EntradaInvalida(f"EjecutorE1 mide E1, no {decl.eureka}")
        ids = decl.lista("corridas", "ids")
        if len(ids) != 4:
            raise EntradaInvalida(f"[corridas].ids de E1 debe nombrar C.E1a…C.E1d, trae {ids}")
        a_id, b_id, c_id, d_id = ids
        nivel = str(decl.tabla("ruido")["nivel"])
        par = decl.tabla("ruido_lectura").get(nivel)
        if not isinstance(par, list) or len(par) != 2:
            raise EntradaInvalida(f"el nivel {nivel!r} de [ruido] no está en [ruido_lectura] de PARAMETROS.toml")
        ruido = RuidoDeLectura(nivel, (float(par[0]), float(par[1])))
        p = ParametrosPipeline(
            decl.qubits,
            decl.shots,
            epsilon=2.0 ** int(decl.numero("cadena", "epsilon_log2")),
            profundidad_peres=int(decl.numero("cadena", "profundidad_peres")),
        )
        n90 = int(decl.numero("validacion", "muestras_90b"))
        cache: dict[str, float] = {}  # huella de los bits → su 90B

        def h90(bits: Bits) -> float:
            recorte = bits[:n90]
            huella = _huella(recorte)
            if huella not in cache:
                cache[huella] = self._est90.estimar(recorte)
            return cache[huella]

        # C.E1a: PRNG, sin ruido y sin mitigar
        fa = _Registradora(self._prng(semilla))
        ra = ejecutar_pipeline(fa, self._val, self._reloj, p)
        informe_a = self._informe(decl, a_id, semilla, ra, fa.cruda, {})
        # C.E1b: Aer ruidoso, sin mitigar
        fb = _Registradora(self._lab.fuente(ruido, semilla))
        rb = ejecutar_pipeline(fb, self._val, self._reloj, p)
        informe_b = self._informe(decl, b_id, semilla, rb, fb.cruda, {"h_90b_cruda": h90(fb.cruda.bits)})
        # C.E1c: lo mismo con twirling propio
        fc = _Registradora(self._lab.fuente(ruido, semilla))
        bloque = int(decl.numero("ruido", "twirling_bloque"))
        rc = ejecutar_pipeline(fc, self._val, self._reloj, p, mitigador=self._lab.twirling(ruido, semilla, bloque))
        reporte_c = {
            "h_90b_cruda": h90(fc.cruda.bits),
            "h_90b_mitigada": h90(rc.muestra.bits),
            "sha256_muestra_mitigada": _huella(rc.muestra.bits),
            "proporcion_nist": self._proporciones_de(decl, rc.clave),
        }
        informe_c = self._informe(decl, c_id, semilla, rc, fc.cruda, reporte_c)
        # C.E1d: fuentes sintéticas
        fuentes = self._medir_fuentes(decl, d_id, semilla, h90)
        controles = {
            "N1": c.n1_cumple(informe_a),
            "D1": c.d1_cumple(informe_b, decl.numero("ruido", "sesgo_analitico"), self._tolerancia(decl)),
            "P1": c.p1_cumple({f.fuente: f for f in fuentes}),
        }
        if self._bit is not None:
            self._bit.registrar("semilla_e1", semilla=semilla, controles=controles)
        return Medicion(informes=(informe_a, informe_b, informe_c), fuentes=fuentes, controles=controles)

    # ------------------------------------------------------------------ piezas

    @staticmethod
    def _tolerancia(decl: Declaracion) -> float:
        return float(decl.tabla("criterios")["c_e1b"]["sesgo_cruda_vs_analitico_tolerancia"])  # type: ignore[index]

    def _proporciones_de(self, decl: Declaracion, clave: Bits) -> dict[str, object]:
        n = int(decl.numero("informativo", "proporcion_nist_secuencias"))
        largo = int(decl.numero("informativo", "proporcion_nist_longitud"))
        alfa = decl.numero("validacion", "alfa")
        secuencias = min(n, len(clave) // largo)  # con una clave corta salen menos de las 93 declaradas; sin ninguna, no se mide
        if secuencias < 1:
            return {}
        return {k: dict(v) for k, v in self._prop(clave, secuencias, largo, alfa).items()}

    def _informe(
        self, decl: Declaracion, corrida: str, semilla: int, r: Resultado, cruda: Muestra, reporte: Mapping[str, object]
    ) -> InformeCorrida:
        m = r.muestra  # la que entró al extractor (la mitigada, si la hubo)
        return InformeCorrida(
            corrida=corrida, eureka=decl.eureka, semilla=semilla, origen=m.origen, procedencia=m.procedencia,
            qubits=decl.qubits, shots=decl.shots, mitigada=m.mitigada, epsilon=2.0 ** int(decl.numero("cadena", "epsilon_log2")),
            profundidad_peres=int(decl.numero("cadena", "profundidad_peres")), validador=self._validador_nombre, estimador="mcv",
            h_min_entrada=r.h_min, h_min_salida=r.h_min_salida, bits_crudos=r.bits_crudos, bits_clave=len(r.clave),
            sha256_muestra_cruda=_huella(cruda.bits),  # la CRUDA de verdad, no la mitigada
            etapas=dict(r.etapas), veredicto=r.veredicto,
            preinscripcion_sha=self._historial.ultimo_commit(decl.rutas), commit=self._historial.commit_actual(),
            entorno=self._entorno(), reporte=dict(reporte),
        )  # fmt: skip

    def _medir_fuentes(self, decl: Declaracion, corrida: str, semilla: int, h90: Callable[[Bits], float]) -> tuple[MedidaDeFuente, ...]:
        n = int(decl.tabla("criterios")["c_e1d"]["bits"])  # type: ignore[index]
        fuentes = self._control(decl, semilla)
        if set(fuentes) != set(c.FUENTES_E1D):
            raise EntradaInvalida(f"las fuentes de control deben ser {c.FUENTES_E1D}, llegaron {sorted(fuentes)}")
        salida = []
        for nombre in c.FUENTES_E1D:
            bits = fuentes[nombre].generar(1, n).bits
            ms = self._val.evaluar(bits)
            salida.append(
                MedidaDeFuente(
                    corrida, semilla, nombre, len(bits), tuple(c.medida(ms, k) for k in c.ESTRUCTURA), min_entropia_mcv(bits), h90(bits)
                )
            )
        return tuple(salida)
