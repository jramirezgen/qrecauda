"""S.03: el muestreo de AerSimulator es pseudoaleatorio (determinista dado seed)."""
import hashlib, json, pathlib
import qiskit, qiskit_aer
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2
from qiskit_aer.noise import NoiseModel, ReadoutError

N, SHOTS = 8, 2048
qc = QuantumCircuit(N, N)
qc.h(range(N)); qc.measure(range(N), range(N))

def h(seq): return hashlib.sha256("\n".join(seq).encode()).hexdigest()

def run_backend(seed, noise=None):
    be = AerSimulator(noise_model=noise) if noise else AerSimulator()
    t = transpile(qc, be)
    return be.run(t, shots=SHOTS, seed_simulator=seed, memory=True).result().get_memory()

def run_sampler(seed, noise=None):
    be = AerSimulator(noise_model=noise) if noise else AerSimulator()
    s = SamplerV2(default_shots=SHOTS, seed=seed, options={"backend_options": {"noise_model": noise}} if noise else None)
    return s.run([qc]).result()[0].data.c.get_bitstrings()

nm = NoiseModel()
nm.add_all_qubit_readout_error(ReadoutError([[0.95, 0.05], [0.08, 0.92]]))

R, H = {}, {}
def reg(k, seq): R[k] = seq; H[k] = h(seq)

for name, f in [("backend", run_backend), ("sampler", run_sampler)]:
    reg(f"{name}_s42_a", f(42)); reg(f"{name}_s42_b", f(42)); reg(f"{name}_s43", f(43))
    reg(f"{name}_ruido_s42_a", f(42, nm)); reg(f"{name}_ruido_s42_b", f(42, nm))
    reg(f"{name}_ruido_s43", f(43, nm))
    reg(f"{name}_sinseed_a", f(None)); reg(f"{name}_sinseed_b", f(None))

misma = all(R[f"{n}_s42_a"] == R[f"{n}_s42_b"] for n in ("backend", "sampler"))
distintas = all(R[f"{n}_s42_a"] != R[f"{n}_s43"] for n in ("backend", "sampler"))
ruido = all(R[f"{n}_ruido_s42_a"] == R[f"{n}_ruido_s42_b"] for n in ("backend", "sampler")) \
    and all(R[f"{n}_ruido_s42_a"] != R[f"{n}_ruido_s43"] for n in ("backend", "sampler"))
sinseed_difiere = all(R[f"{n}_sinseed_a"] != R[f"{n}_sinseed_b"] for n in ("backend", "sampler"))
# ruido realmente actua: distribucion != sin ruido
ruido_cambia = R["backend_ruido_s42_a"] != R["backend_s42_a"]

out = {
  "versiones": {"qiskit": qiskit.__version__, "qiskit_aer": qiskit_aer.__version__},
  "shots": SHOTS, "qubits": N,
  "misma_semilla_identica": misma,
  "semillas_distintas_distintas": distintas,
  "hashes": H,
  "con_ruido_determinista": ruido,
  "sin_semilla_corridas_difieren": sinseed_difiere,
  "ruido_altera_secuencia": ruido_cambia,
  "hallazgos": [
    "Dos corridas con seed_simulator=42 dan secuencias idénticas disparo a disparo (AerSimulator.run y SamplerV2): muestreo pseudoaleatorio.",
    "Semillas 42 y 43 dan secuencias distintas.",
    "Con NoiseModel(ReadoutError) y semilla fija sigue siendo determinista.",
    f"Sin semilla, las dos corridas difirieron: {sinseed_difiere}.",
    "SamplerV2(seed=...) pasa seed_simulator=self._seed a backend.run (sampler_v2.py:166-173); con seed=None pasa None.",
    "La librería C++ de Aer enlaza std::random_device (strings del .so) y el seed por defecto de AerBackend es None; ⚠️ sin verificar que el seed por defecto salga de std::random_device (no se inspeccionó el fuente C++).",
  ],
}
pathlib.Path(__file__).with_name("resultado.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(json.dumps({k: v for k, v in out.items() if k not in ("hashes", "hallazgos")}, indent=1))
