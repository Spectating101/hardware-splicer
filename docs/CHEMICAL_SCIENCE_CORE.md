# Hardware Splicer chemistry — standalone scientific core

Practical repair/manufacturing use is the primary new product workflow.
See docs/PRACTICAL_CHEMISTRY_ENGINE.md. Numerical science remains opt-in.

Status: computational prototype. Branch: agent/chemical-engineering-v0.
Scope: chemistry and chemical engineering, independent of CAD or electronics.

## Working scientific domains

| Discipline | Solver/kernel | Current validated envelope |
|---|---|---|
| Molecular and materials formula | RDKit, pymatgen-core | SMILES/solid composition; no material safety proof |
| Reaction stoichiometry | HS deterministic parser | Neutral molecular formulas, nested groups, element conservation, limiting ideal inventories |
| Reference reaction thermodynamics | Cantera GRI30 | Two reference reactions, enthalpy, Gibbs, entropy, K; identity checks |
| Reference chemical kinetics | Cantera GRI30 reactor | Bounded artificial gas mixture, isothermal time response, elemental mass check |
| Thermophysical property models | thermo + chemicals | Chemical properties at declared T/P, applicability uncertain |
| Vapor-liquid phase equilibria | thermo Peng-Robinson | Pure water and methane/ethane/nitrogen reference TP flash with phase closure |
| Specialist fluid property reference | CoolProp HEOS water | Water phase, saturation, density, heat capacity, transport |
| Multi-model discrepancy detection | thermo versus CoolProp | Near-boiling phase disagreement flagged rather than silently reconciled |
| Gas properties | Cantera air.yaml | Bounded air-mixture T/P and TP-equilibrium calculations |
| Process accounting | HS process graph | Mixers, splitters, pass-through, stream identity and species conservation; no outlet solver |
| Electrochemistry | PyBaMM SPM Chen2020 | Reference Li-ion single-cell discharge, no real pack/safety proof |
| Materials evidence | MachineProject source graph | Source-/method-scoped numeric screening, not compatibility proof |

The chemistry core works without a mechanical CAD, circuit diagram or external
agent. Existing HS product API and MCP discovery expose tools; scientific
packages are optional and lazy imported. Missing dependencies return HTTP 503.

## Real numerical validation (2026-10-20, Optiplex)

Runnable benchmark: eval/chemical_science/reference_benchmark_v1.py.
It exercises known physical landmarks, numerical conservation identities,
constructed bad inputs and actual third-party solvers. It is NOT a blinded
or experimental accuracy benchmark.

- CaCO3 -> CaO + CO2: elemental conservation and ideal inventory at an
  assumed fractional conversion. This is not a reaction viability claim.
- Peng-Robinson flash: methane/ethane/nitrogen feed [0.965,0.018,0.017]
  at 110 K and 100 kPa gives ~0.08903 vapor mole fraction and numerical
  species-balance residual near 1e-16.
- CoolProp water boiling point at 101325 Pa: ~373.1243 K.
  At 374 K, Peng-Robinson incorrectly classifies water as liquid relative
  to CoolProp's vapor reference. Cross-model adjudication blocks the result.
- At 300 K, water densities from thermo and CoolProp agree closely;
  this does not constitute independent experimental validation.
- Cantera GRI30 reaction enthalpy, Gibbs energy, entropy and equilibrium
  constants pass thermodynamic identity checks.
- Cantera isothermal kinetic trajectory preserves C/H/O/N mass fractions
  within numerical tolerance.
- A two-operation, water/salt mixer-splitter graph conserves component and
  overall mass from declared flows. It does NOT solve equipment behavior.

## Priorities to become a serious standalone chemical engineering engine

P0: Ionic speciation, acid/base chemistry and charge balance (evaluate
Reaktoro); broad phase equilibrium and thermodynamic model selection;
uncertainty/applicability envelopes; validated reactor enthalpy and transport;
independent measured data and held-out benchmark design.

P1: Actually predictive unit-operation models and flowsheet solving
(evaluate IDAES and BioSTEAM independently); porous media (OpenPNM);
multiphase reactive transport; battery electrochemistry with measured
cell calibration; source-backed materials compatibility and degradation.

P2: Coherent chemistry-first interface and autonomous chemical agent that
selects validated tools, records provenance and uncertainty, and refuses
unsupported designs. A broad capabilities catalog is not a substitute for
accurate and independently assessed engineering predictions.

## Independent external OSS candidates

- Reaktoro: https://github.com/reaktoro/reaktoro
- IDAES: https://idaes.org/
- BioSTEAM: https://github.com/BioSTEAMDevelopmentGroup/biosteam
- CoolProp: https://github.com/CoolProp/CoolProp (now executable)
- OpenPNM: https://github.com/PMEAL/OpenPNM

These are research candidates, not claims of working adapters unless marked
operational in this repo.

## Authority

All results are simulations, correlations or declared arithmetic. They do not
prove source identity, chemical safety, physical compatibility, feasible
synthesis, industrial plant performance, actual yield, safe handling, or
manufacturing/release authority.
