"""EjecutorE4: mide UNA semilla de E4 como la fija docs/preinscripciones/E4.md. No decide nada: decide el juez (`_juzgar_e4`).

Por semilla (= un trabajo en el hardware) produce las cinco corridas que el plan separa, todas con el pipeline REAL salvo la fuente:
- C.E4a  PRNG clásico (control negativo N1).
- C.E4b  el GEMELO en Aer, sin mitigar: los mismos circuitos ISA, los mismos qubits físicos y las mismas máscaras que el hardware, con el
         ruido que el backend elegido declara en su calibración (la PUB cruda).
- C.E4c  el gemelo con twirling (las PUBs enmascaradas, deshechas por XOR).
- C.E4d  hardware, muestra CRUDA (la PUB sin máscara).
- C.E4e  hardware, muestra con TWIRLING (las PUBs enmascaradas, deshechas por XOR).

El hardware gasta un solo trabajo por semilla (`FuenteDeContraste`): la cruda y la del twirling salen de los MISMOS disparos enviados.
El trabajo se envía ANTES de arrancar el reloj de cada cadena (`cruda()` es ansiosa), así M6 y M7 miden sólo la cadena local y la
cola y la ejecución del dispositivo van aparte, en `reporte.trabajo`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from qrecauda.aplicacion import criterios_e4 as c
from qrecauda.aplicacion.con_m1 import ConM1
from qrecauda.aplicacion.pipeline import ParametrosPipeline, Resultado
from qrecauda.aplicacion.pipeline import ejecutar as ejecutar_pipeline
from qrecauda.aplicacion.registradora import Registradora, huella
from qrecauda.datos import Declaracion, InformeCorrida, Medicion
from qrecauda.dominio.errores import EntradaInvalida
from qrecauda.dominio.muestra import Muestra
from qrecauda.puertos import Bitacora, FuenteDeBits, FuenteDeContraste, Historial, Reloj, Validador

Contraste = Callable[[Declaracion, int], FuenteDeContraste]


def mascaras_de(decl: Declaracion) -> int:
    """K del twirling del hardware: PUBs enmascaradas por trabajo (la cruda es una más, sin máscara)."""
    k = int(decl.numero("hardware", "mascaras"))
    if k < 1 or decl.shots % (k + 1) != 0:
        raise EntradaInvalida(f"[hardware].mascaras={k}: los {decl.shots} disparos deben repartirse en {k + 1} PUBs iguales")
    return k


class EjecutorE4:
    """Implementa el puerto `Ejecutor` para E4."""

    def __init__(
        self,
        prng: Callable[[int], FuenteDeBits],
        contraste: Contraste,
        validador: Validador,
        reloj: Reloj,
        historial: Historial,
        entorno: Callable[[], Mapping[str, str]],
        bitacora: Bitacora | None = None,
    ) -> None:
        self._prng, self._contraste = prng, contraste
        self._val, self._reloj = ConM1(validador), reloj
        self._historial, self._entorno, self._bit = historial, entorno, bitacora
        self._validador_nombre = type(validador).__name__

    def ejecutar(self, decl: Declaracion, semilla: int) -> Medicion:
        if decl.eureka != "E4":
            raise EntradaInvalida(f"EjecutorE4 mide E4, no {decl.eureka}")
        ids = decl.lista("corridas", "ids")
        if ids != c.CORRIDAS:
            raise EntradaInvalida(f"[corridas].ids de E4 debe ser {list(c.CORRIDAS)}, trae {list(ids)}")
        k = mascaras_de(decl)
        por_pub = decl.shots // (k + 1)
        cadena = dict(
            epsilon=2.0 ** int(decl.numero("cadena", "epsilon_log2")), profundidad_peres=int(decl.numero("cadena", "profundidad_peres"))
        )
        p_cruda = ParametrosPipeline(decl.qubits, por_pub, **cadena)  # type: ignore[arg-type]
        p_twirl = ParametrosPipeline(decl.qubits, por_pub * k, **cadena)  # type: ignore[arg-type]
        p_prng = ParametrosPipeline(decl.qubits, decl.shots, **cadena)  # type: ignore[arg-type]

        # El trabajo del hardware y su gemelo van primero: ni la cola ni la simulación pueden colarse en ningún reloj de cadena.
        contraste = self._contraste(decl, semilla)
        hw_cruda_fuente, hw_twirl_fuente = Registradora(contraste.cruda()), Registradora(contraste.con_twirling())
        trabajo = dict(contraste.registro())

        fa = Registradora(self._prng(semilla))
        ra = ejecutar_pipeline(fa, self._val, self._reloj, p_prng)
        fb = Registradora(contraste.gemelo_cruda())
        rb = ejecutar_pipeline(fb, self._val, self._reloj, p_cruda)
        fc = Registradora(contraste.gemelo_con_twirling())
        rc = ejecutar_pipeline(fc, self._val, self._reloj, p_twirl)
        rd = ejecutar_pipeline(hw_cruda_fuente, self._val, self._reloj, p_cruda)
        re_ = ejecutar_pipeline(hw_twirl_fuente, self._val, self._reloj, p_twirl)

        informes = tuple(
            self._informe(decl, corrida, semilla, r, f.cruda, trabajo if corrida in (c.HW_CRUDA, c.HW_TWIRL) else None)
            for corrida, r, f in (
                (c.PRNG, ra, fa),
                (c.AER_CRUDA, rb, fb),
                (c.AER_TWIRL, rc, fc),
                (c.HW_CRUDA, rd, hw_cruda_fuente),
                (c.HW_TWIRL, re_, hw_twirl_fuente),
            )
        )
        por_id = {i.corrida: i for i in informes}
        controles = {
            "N1": c.n1_cumple(por_id[c.PRNG]),
            "S1": c.s1_cumple(por_id[c.AER_CRUDA], por_id[c.AER_TWIRL], por_id[c.HW_CRUDA], por_id[c.HW_TWIRL]),
            "V1": c.v1_cumple([por_id[c.HW_CRUDA], por_id[c.HW_TWIRL]], 1),  # el juez exige además >= n trabajos distintos
        }
        if self._bit is not None:
            self._bit.registrar("semilla_e4", semilla=semilla, controles=controles, job_id=trabajo.get("job_id"))
        return Medicion(informes=informes, controles=controles)

    def _informe(
        self, decl: Declaracion, corrida: str, semilla: int, r: Resultado, cruda: Muestra, trabajo: Mapping[str, object] | None
    ) -> InformeCorrida:
        m = r.muestra
        sesgos = c.sesgos_por_qubit(cruda)
        reporte: dict[str, object] = {"sesgos_por_qubit": sesgos, "sesgo_medio_por_qubit": c.sesgo_medio_por_qubit(sesgos)}
        if trabajo is not None:
            reporte["trabajo"] = dict(trabajo)
        return InformeCorrida(
            corrida=corrida, eureka=decl.eureka, semilla=semilla, origen=m.origen, procedencia=m.procedencia,
            qubits=decl.qubits, shots=m.shots, mitigada=m.mitigada, epsilon=2.0 ** int(decl.numero("cadena", "epsilon_log2")),
            profundidad_peres=int(decl.numero("cadena", "profundidad_peres")), validador=self._validador_nombre, estimador="mcv",
            h_min_entrada=r.h_min, h_min_salida=r.h_min_salida, bits_crudos=r.bits_crudos, bits_clave=len(r.clave),
            sha256_muestra_cruda=huella(cruda.bits), etapas=dict(r.etapas), veredicto=r.veredicto,
            preinscripcion_sha=self._historial.ultimo_commit(decl.rutas), commit=self._historial.commit_actual(),
            entorno=self._entorno(), reporte=reporte,
        )  # fmt: skip
