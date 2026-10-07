# Mensaje fundacional del proyecto (texto del equipo, 2026-10-07)

> Se conserva como fuente. La interpretación vigente, con las discrepancias declaradas, está en `docs/FUNDAMENTO.md`.

**QRecauda: Entropía Cuántica Certificada para la Recaudación del Perú** — Track 4 (Criptoseguridad para Sistemas de
Recaudación mediante QRNG), Hackatón Qiskit IBM Lima.

**Tesis.** «La aleatoriedad clásica se predice. La recaudación del Perú no debería.» Los PRNG son deterministas; la
superposición cuántica es la fuente que se captura, se limpia del ruido NISQ y se certifica con NIST.

**Construir (TRL 4, en una PC de 16 GB, sin colas ni credenciales).** Qiskit + AerSimulator con circuito QRNG de 8–10
qubits (Hadamard + medición) · modelo de ruido personalizado (lectura, decoherencia, cross-talk) · mitigación local con
TREX (`mthree`) y ZNE · extractores von Neumann + Toeplitz · validación NIST SP 800-22 con `nistrng` · demo de cifrado
de una transacción de peaje/Metro con clave QRNG.

**Arquitectura.** `|0⟩ → H⊗n → medición → SamplerV2 → conteos` · `mitigación TREX+ZNE+PEC/PNA` · `von Neumann + Toeplitz` ·
`NIST + min-entropía` · `cifrado de la transacción`. Cada bloque, un módulo independiente; todo en un notebook reproducible.

**Rúbrica.** Modelización algebraica (canal Pauli-Lindblad, `NoiseLearnerV3`) · stack actual (`SamplerV2`, PUBs, `Batch`/`Session`) ·
transpilación guiada por IA (`AIRouting`, `StagedPassManager`) · QEM (TREX, ZNE, PEC/PNA, `Samplomatic`) · reproducibilidad
(GitHub, `requirements.txt`, versiones exactas) · impacto (OSITRAN, MTC, Metro de Lima, peajes).

**Métricas.** sesgo de lectura < 1 % · min-entropía > 0,9 · NIST monobit, runs y χ² con p > 0,01 · tasa > 10 kbps · latencia < 500 ms.

**Plan de 24 h.** 0–2 h circuito + Aer + ruido · 2–6 h SamplerV2 + TREX + ZNE · 6–10 h extracción + NIST · 10–14 h demo cifrado ·
14–18 h documentación + notebook · 18–24 h pitch y ensayo.

**Pitch (10 slides).** problema · solución · tecnología · demo (PRNG vs QRNG sin mitigar vs mitigado) · validación · caso de uso ·
impacto · roadmap (TRL 4 → 5 → piloto → producción) · equipo · cierre.

**No haremos:** vender «Hadamard y listo», forzar IA donde no aporta, depender de hardware real para la demo, ignorar la
mitigación, presentar sin NIST.
