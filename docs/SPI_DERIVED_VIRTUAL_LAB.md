# SPI Derived Virtual Lab v1

Status: software-only development/reference experiment. No Astra and no physical hardware.

This tranche exists to exercise Hardware Splicer's engineering-verification loop at scale while
manufacturer simulation files and bench evidence remain unavailable. It is deliberately a lower
evidence tier than the vendor-model campaign.

## Evidence boundary

Every result is stamped:

```text
evidence_class=derived_surrogate_only
eligible_for_vendor_model_campaign_credit=false
measured_evidence_present=false
physical_correctness=UNPROVEN
physical_authority_granted=false
authority_effect=none
```

The surrogate may reject candidates and test workflow behavior. It cannot validate a real part,
replace an IBIS/Verilog manufacturer model, establish fabrication readiness, or authorize power-on.
Cross-model calibration records use `evidence_class=cross_model_comparison_only` and remain explicitly
ineligible for vendor-model campaign credit.

## Surrogate inputs

The v1 model mixes frozen document-grounded terms with explicit development assumptions:

- host logic: 3.3 V;
- DUT target rail: 1.8 V, allowed 1.7–1.95 V;
- DUT pin absolute maximum: VCC + 0.4 V;
- TXU A→B max propagation term: 19 ns;
- TXU B→A max propagation term: 15 ns;
- DUT clock-low-to-output-valid term: 6 ns;
- development-only assumptions: 8 ns host launch, 8 ns host setup, 4 ns skew, and a simple load-delay term.

Assumption-bearing terms are explicitly marked `surrogate_assumption` in the model.

## Generated benchmark

`hardware_splicer.spi_virtual_lab_benchmark` generates 576 cases as the Cartesian product of:

- 1, 5, and 25 MHz SPI;
- translated vs direct 3.3-V drive;
- correct vs reversed MISO direction;
- fixed 3+1 translator vs grouped 2+2 topology;
- OE disabled/enabled;
- DUT rail absent/present;
- DUT rail 1.65, 1.8, or 1.98 V; and
- 10 or 40 pF surrogate load.

Expected labels are preregistered from explicit rules, not copied from verifier output. Under the
frozen v1 timing assumptions, 25 MHz is labeled unsafe because the bounded timing terms exceed the
20-ns half-cycle.

Run:

```bash
python scripts/run_spi_derived_virtual_lab.py
```

The canonical runner emits the benchmark, repair control, sensitivity sweep, protocol oracle, and
an aggregate report containing SHA-256 identities for the deterministic benchmark, repair,
sensitivity, and protocol outputs. Use `--full` to retain per-case rows in the component outputs.

## Sensitivity sweep

`hardware_splicer.spi_surrogate_sensitivity` executes 1,920 derived cases as the exact Cartesian
product of:

- 1, 5, 10, 15, 20, and 25 MHz SPI;
- 5, 10, 20, 40, and 80 pF surrogate load;
- 0, 2, 4, and 8 ns clock skew;
- 2, 4, 8, and 12 ns host setup; and
- 2, 4, 8, and 12 ns host launch.

That is `6 × 5 × 4 × 4 × 4 = 1,920` cases. The sweep exposes dependence on development assumptions;
it does not convert those assumptions into evidence or promote physical authority.

## Repair control

Six injected faults have deterministic repairs:

1. direct 3.3-V drive;
2. reversed MISO;
3. grouped-direction translator misuse;
4. OE enabled while DUT rail is absent;
5. 25-MHz overclock under the frozen surrogate budget; and
6. DUT rail at 1.65 V.

The scripted repair benchmark is a plumbing/control result only. It is not evidence of AI
engineering competence.

## Behavioral oracle

`spi_behavioral_oracle.py` and `examples/spi_virtual_lab/w25q_readonly_oracle.v` provide a bounded
read-only SPI oracle for the `0x9F` JEDEC-ID path. The Verilog fixture is intentionally marked as a
Hardware-Splicer derived surrogate, **not** a Winbond model.

Expected response in this development oracle is `EF 60 18`, with no write/erase side effect.

Where `iverilog` and `vvp` are installed, the canonical runner can also execute the derived Verilog
oracle with:

```bash
python scripts/run_spi_derived_virtual_lab.py --run-verilog
```

A passing Icarus result remains a derived control result only and grants no manufacturer-model or
physical credit.

## What comes after v1

1. CI-confirm the exact frozen v1 head and keep the deterministic corpus unchanged.
2. When manufacturer-model results from the PR #93 lane are available, use the calibration contract
   to record agreement or disagreement without retroactively rewriting the surrogate experiment.
3. Treat additional jitter/source-confidence strata or broader sensitivity work as a later v2, not
   as a reason to expand this frozen tranche.
4. Only after the deterministic controls and higher-evidence manufacturer-model lane are frozen,
   replace the scripted repair mutation with one bounded Astra experiment.
