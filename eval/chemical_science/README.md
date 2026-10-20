# Standalone chemistry reference evaluation

From repo root, with the chemical, chemical-process and chemical-fluids
extras installed, execute:

    PYTHONPATH=src python eval/chemical_science/reference_benchmark_v1.py

This emits per-case inspectable JSON with real phase, kinetic,
thermodynamic, fluid-property, stoichiometric and process-network
observations. It is a hand-authored consistency benchmark, not blinded
experimental validation. A missing solver causes explicit failure;
there are no fabricated fallback numbers.

See docs/CHEMICAL_SCIENCE_CORE.md for capabilities and remaining gaps.
