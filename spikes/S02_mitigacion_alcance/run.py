"""S.02 — alcance de la mitigación: ¿qué técnicas actúan sobre bitstrings por disparo? Escribe resultado.json."""

import json
import warnings
from pathlib import Path

import mthree
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError
from qiskit_ibm_runtime.options import EstimatorOptions, SamplerOptions

warnings.filterwarnings("ignore")
N, SHOTS, SEMILLAS = 8, 100_000, [11, 22, 33]
P10, P01 = 0.02, 0.08  # p(1|0), p(0|1)
AQUI = Path(__file__).parent


def modelo_ruido() -> NoiseModel:
    nm = NoiseModel()
    nm.add_all_qubit_readout_error(ReadoutError([[1 - P10, P10], [P01, 1 - P01]]))
    return nm


def sesgo(bits: np.ndarray) -> dict:
    """bits: (shots, N) con columna q = qubit q. Sesgo |p1-0.5| por qubit, medio y máximo."""
    p1 = bits.mean(axis=0)
    s = np.abs(p1 - 0.5)
    return {"medio": float(s.mean()), "maximo": float(s.max()), "p1_global": float(bits.mean())}


def bits_de_cadenas(cadenas) -> np.ndarray:
    # cadena little-endian de Qiskit: el carácter 0 de la cadena es el qubit N-1
    return np.array([[int(c) for c in reversed(s)] for s in cadenas], dtype=np.uint8)


def circuito_h() -> QuantumCircuit:
    qc = QuantumCircuit(N, N)
    qc.h(range(N))
    qc.measure(range(N), range(N))
    return qc


res: dict = {"semillas": SEMILLAS, "disparos": SHOTS, "n_qubits": N, "ruido_lectura": {"p1_dado_0": P10, "p0_dado_1": P01}}

# ---------- 1. SamplerV2.options ----------
ok_s, err_s = {}, {}
for nombre, kw in {
    "resilience_level": dict(resilience_level=1),
    "resilience": dict(resilience={"measure_mitigation": True}),
    "resilience.zne_mitigation": dict(resilience={"zne_mitigation": True}),
    "twirling": dict(twirling={"enable_measure": True, "enable_gates": True}),
    "dynamical_decoupling": dict(dynamical_decoupling={"enable": True}),
}.items():
    try:
        SamplerOptions(**kw)
        ok_s[nombre] = True
    except Exception as e:  # noqa: BLE001
        ok_s[nombre] = False
        err_s[nombre] = type(e).__name__
campos_s = sorted(k for k in SamplerOptions.__dataclass_fields__ if not k.startswith("_"))
campos_e = sorted(k for k in EstimatorOptions.__dataclass_fields__ if not k.startswith("_"))
res["sampler_options"] = {
    "conserva_bits_por_disparo": True,  # ⚠️ sin verificar: el twirling corre en el servicio, no hay forma local
    "conserva_bits_verificado": False,
    "corre_local_aer": False,
    "observable": "bitstrings por disparo (SamplerV2 devuelve PubResult.data.<reg>.get_bitstrings()); solo twirling y DD",
    "mueve_sesgo_de_lectura": None,  # ⚠️ sin verificar: no medible sin hardware
    "campos_SamplerOptions": campos_s,
    "campos_solo_EstimatorOptions": sorted(set(campos_e) - set(campos_s)),
    "aceptado": ok_s,
    "rechazado_por": err_s,
    "twirling_sampler": "enable_measure existe en SamplerOptions; en Sampler la mitigación de lectura (measure_mitigation) NO existe",
}

# ---------- 2. mthree ----------
nm = modelo_ruido()
sim = AerSimulator(noise_model=nm)
qc = circuito_h()
tqc = transpile(qc, sim, optimization_level=0)
mapa = mthree.utils.final_measurement_mapping(tqc)
m3_filas, antes_l, desp_l = [], [], []
for sem in SEMILLAS:
    r = sim.run(tqc, shots=SHOTS, seed_simulator=sem, memory=True).result()
    mem = r.get_memory()
    antes = sesgo(bits_de_cadenas(mem))
    cuentas = r.get_counts()
    mit = mthree.M3Mitigation(sim)
    mit.cals_from_system(list(mapa.keys()) if isinstance(mapa, dict) else mapa, shots=SHOTS, async_cal=False)
    qp = mit.apply_correction(cuentas, list(mapa.keys()) if isinstance(mapa, dict) else mapa)
    # marginales p1 por qubit desde cuasi-probabilidades
    p1 = np.zeros(N)
    for cad, v in dict(qp).items():
        for q, c in enumerate(reversed(cad)):
            if c == "1":
                p1[q] += v
    sd = np.abs(p1 - 0.5)
    despues = {"medio": float(sd.mean()), "maximo": float(sd.max()), "negativas": bool(any(v < 0 for v in dict(qp).values()))}
    m3_filas.append({"semilla": sem, "antes": antes, "despues_cuasiprob": despues, "tipo_devuelto": type(qp).__name__})
    antes_l.append(antes["medio"])
    desp_l.append(despues["medio"])
metodos_publicos = [n for n in dir(mthree.M3Mitigation) if not n.startswith("_")]
res["mthree"] = {
    "conserva_bits_por_disparo": False,
    "corre_local_aer": True,
    "observable": "conteos agregados -> cuasi-probabilidades (QuasiCollection); sin API por disparo",
    "mueve_sesgo_de_lectura": True,
    "version": mthree.__version__,
    "metodos_publicos_M3Mitigation": metodos_publicos,
    "hay_metodo_por_disparo": any("shot" in n or "bitstring" in n or "memory" in n for n in metodos_publicos),
    "bits_sin_PRNG": "no: para obtener bitstrings habría que muestrear la cuasi-distribución con un PRNG (remuestreo), lo que anula el origen cuántico",
    "sesgo_medio_antes": float(np.mean(antes_l)),
    "sesgo_medio_despues": float(np.mean(desp_l)),
    "esperado_analitico_antes": abs((0.5 * P10 + 0.5 * (1 - P01)) - 0.5),
    "por_semilla": m3_filas,
}

# ---------- 3. twirling propio ----------
BLOQUES = 500
POR = SHOTS // BLOQUES
filas, sesg = [], []
for sem in SEMILLAS:
    rng = np.random.default_rng(sem)
    masks = rng.integers(0, 2, size=(BLOQUES, N), dtype=np.uint8)
    circs = []
    for b in range(BLOQUES):
        c = QuantumCircuit(N, N)
        c.h(range(N))
        for q in range(N):
            if masks[b, q]:
                c.x(q)
        c.measure(range(N), range(N))
        circs.append(c)
    t = transpile(circs, sim, optimization_level=0)
    r = sim.run(t, shots=POR, seed_simulator=sem, memory=True).result()
    todos = []
    for b in range(BLOQUES):
        crudo = bits_de_cadenas(r.get_memory(b))
        todos.append(crudo ^ masks[b])  # XOR clásico por disparo
    bits = np.vstack(todos)
    s = sesgo(bits)
    filas.append({"semilla": sem, "disparos": int(bits.shape[0]), "sesgo": s})
    sesg.append(s["medio"])
res["twirling_propio"] = {
    "conserva_bits_por_disparo": True,
    "corre_local_aer": True,
    "observable": "bitstrings por disparo (máscara X por qubit y bloque, XOR clásico tras medir)",
    "mueve_sesgo_de_lectura": True,
    "bloques": BLOQUES,
    "disparos_por_bloque": POR,
    "nota_mascara": "la máscara es aleatoria pero pública para el análisis; con PRNG clásico para la máscara no se añade ni resta entropía a H (el XOR de uniforme con constante es uniforme); ⚠️ sin verificar su efecto sobre estado NO uniforme (ahí el twirling promedia el canal, no lo elimina)",
    "sesgo_medio_sin_twirling": float(np.mean(antes_l)),
    "sesgo_medio_con_twirling": float(np.mean(sesg)),
    "por_semilla": filas,
}

# ---------- 4. ZNE / PEC ----------
import importlib.metadata as md

import qiskit_mitigation

zne_pec = {"qiskit_mitigation": md.version("qiskit-mitigation"), "mitiq_instalado": False}
try:
    import mitiq  # noqa: F401

    zne_pec["mitiq_instalado"] = True
except ImportError:
    pass
zne_pec["modulos_qiskit_mitigation"] = sorted(n for n in dir(qiskit_mitigation) if not n.startswith("_"))
zne_pec["EstimatorOptions_resilience"] = {"zne_mitigation": True, "pec_mitigation": True, "solo_en_Estimator": True}

# prueba mínima de ZNE por plegado: con SOLO ruido de lectura el plegado U->U U† U no cambia nada
def z_medio(circuito_h_plegado, sem):
    t = transpile(circuito_h_plegado, sim, optimization_level=0)
    m = sim.run(t, shots=SHOTS, seed_simulator=sem).result().get_counts()
    tot = sum(m.values())
    e = 0.0
    for cad, v in m.items():
        e += v * (1 - 2 * int(cad[-1]))  # <Z> del qubit 0
    return e / tot

zne_filas = []
for sem in SEMILLAS:
    v = {}
    for fac in (1, 3, 5):
        c = QuantumCircuit(1, 1)
        for _ in range(fac):  # H^fac; con fac impar equivale a H, plegado de ruido de puerta
            c.h(0)
            c.barrier()
        c.measure(0, 0)
        v[fac] = z_medio(c, sem)
    ext = float(np.polyval(np.polyfit([1, 3, 5], [v[1], v[3], v[5]], 1), 0))
    zne_filas.append({"semilla": sem, "Z_por_factor": v, "extrapolado_a_0": ext, "ideal": 0.0})
sesgo_zne_antes = float(np.mean([abs(f["Z_por_factor"][1]) for f in zne_filas]))
sesgo_zne_despues = float(np.mean([abs(f["extrapolado_a_0"]) for f in zne_filas]))
cfg_comun = {
    "observable": "valores esperados <O> (EstimatorV2); no devuelve bitstrings",
    "conserva_bits_por_disparo": False,
}
res["zne"] = {
    **cfg_comun,
    "corre_local_aer": False,  # ⚠️ vía Estimator de IBM Runtime: no con Aer; Aer EstimatorV2 no implementa resilience
    "mueve_sesgo_de_lectura": False,
    "prueba_minima": {"descripcion": "<Z> de H con factores de plegado 1,3,5 y solo ruido de lectura; |<Z>|=|1-2p1|; extrapolación lineal a ruido 0", "sesgo_Z_factor1": sesgo_zne_antes, "sesgo_Z_extrapolado": sesgo_zne_despues, "esperado_Z_sesgado": abs(1 - 2 * (0.5 * P10 + 0.5 * (1 - P01))), "por_semilla": zne_filas},
    **zne_pec,
}
res["pec"] = {
    **cfg_comun,
    "corre_local_aer": False,  # ⚠️ sin verificar: qiskit_mitigation.pec es una pieza, pero no se ejecutó extremo a extremo
    "mueve_sesgo_de_lectura": False,  # modela canales de puerta (Pauli-Lindblad); la lectura se trata con TREX/measure_mitigation
    "nota": "PEC pondera muestras con signos para estimar <O>: las muestras individuales no son bitstrings válidos",
    "ejecutado_local": False,
    "modulos": zne_pec["modulos_qiskit_mitigation"],
}

(AQUI / "resultado.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, dict))}) for k, v in res.items() if isinstance(v, dict)}, indent=1, ensure_ascii=False))
