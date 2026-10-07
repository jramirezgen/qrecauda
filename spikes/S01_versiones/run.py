"""S.01 — ¿conviven qiskit, aer, runtime, mthree y nistrng, y corre un circuito H⊗n? Escribe resultado.json."""

import importlib.metadata as md
import json
import platform
import sys
from pathlib import Path

PAQUETES = ["qiskit", "qiskit-aer", "qiskit-ibm-runtime", "qiskit-ibm-transpiler", "mthree", "nistrng", "cryptography", "numpy", "scipy"]
res: dict = {"python": platform.python_version(), "paquetes": {}, "pruebas": {}}
for p in PAQUETES:
    try:
        res["paquetes"][p] = md.version(p)
    except md.PackageNotFoundError:
        res["paquetes"][p] = None

try:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    from qiskit_aer.primitives import SamplerV2

    n, shots = 8, 1000
    qc = QuantumCircuit(n)
    qc.h(range(n))
    qc.measure_all()
    r = SamplerV2(default_shots=shots).run([qc]).result()
    bits = r[0].data.meas.get_bitstrings()
    res["pruebas"]["aer_sampler_v2"] = {"ok": True, "bitstrings": len(bits), "ancho": len(bits[0])}
except Exception as e:  # noqa: BLE001 — un spike registra el fallo, no lo oculta
    res["pruebas"]["aer_sampler_v2"] = {"ok": False, "error": repr(e)}

for mod in ("mthree", "nistrng", "qiskit_ibm_runtime", "qiskit_ibm_transpiler", "cryptography.hazmat.primitives.ciphers.aead"):
    try:
        importlib = __import__(mod, fromlist=["x"])
        res["pruebas"][f"import_{mod}"] = {"ok": True}
    except Exception as e:  # noqa: BLE001
        res["pruebas"][f"import_{mod}"] = {"ok": False, "error": repr(e)}

try:
    import mthree

    res["pruebas"]["mthree_API"] = {"ok": True, "tiene_M3Mitigation": hasattr(mthree, "M3Mitigation")}
except Exception as e:  # noqa: BLE001
    res["pruebas"]["mthree_API"] = {"ok": False, "error": repr(e)}

Path(__file__).with_name("resultado.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
print(json.dumps(res, indent=1, ensure_ascii=False))
sys.exit(0 if res["pruebas"]["aer_sampler_v2"]["ok"] else 1)
