# SPI Derived Virtual Lab v1

Status: zero-Astra software experiment stacked on PR #93.

This layer exists so Hardware Splicer can run a large engineering benchmark without waiting
for lab access or manufacturer model downloads.  It is intentionally lower-authority than the
vendor-model campaign.

## Evidence class

Every case and result is stamped:

```text
evidence_class=derived_surrogate_only
vendor_model_campaign_credit_eligible=false
measured_evidence_present=false
physical_correctness=UNPROVEN
fabrication_ready=false
power_on_ready=false
physical_authority_granted=false
authority_effect=none
```

Passing this benchmark means the encoded source-derived analytical rules and scripted controls
behaved as preregistered.  It does not mean the circuit, vendor models, or physical hardware
were validated.

## Frozen corpus

`hardware_splicer.spi_derived_virtual_lab` generates exactly 512 cases from the Cartesian
product of:

- 8 fault profiles;
- 4 SPI clock points: 1, 5, 20, and 100 MHz;
- 4 derived current-load points: 20, 100, 300, and 550 mA;
- 4 DUT-rail points: 1.773, 1.800, 1.827, and 1.900 V.

The fault profiles are:

1. clean reference;
2. direct 3.3-V drive;
3. reversed MISO direction;
4. grouped-direction translator misuse;
5. OE enabled while the DUT rail is absent;
6. missing absolute-maximum provenance;
7. translator output above the derived DUT pin limit;
8. DUT supply outside the declared operating range.

High clock and over-current corners can make a nominally clean case unsafe. Missing provenance
blocks promotion rather than inventing an electrical failure.

## Deterministic checks

Each case is evaluated for:

- critical source identity completeness;
- DUT operating-rail range;
- direct-drive absolute-maximum safety;
- SPI 3-forward/1-reverse direction contract;
- translator topology;
- translator-output absolute-maximum compatibility;
- OE behavior when the DUT domain is unpowered;
- source-derived half-cycle timing margin;
- regulator current capacity; and
- a bounded read-only JEDEC-ID protocol oracle.

The timing surrogate uses the currently source-bound known terms from PR #93. It deliberately
keeps the model simple and auditable; it is not IBIS and cannot earn IBIS campaign credit.

## Read-only protocol oracle

The reference oracle accepts only JEDEC-ID command `0x9F`, returning the frozen reference ID
`EF 60 18`. Mutating commands such as WREN, status writes, page program, and erase operations
are rejected and never mutate oracle state.

This oracle is a development/reference model. It is not the Winbond Verilog model.

## Scripted repair control

For injected structural faults, the benchmark applies only the minimal known correction:

- restore the fixed 3+1 translator;
- restore MISO direction;
- disable OE while the DUT rail is absent;
- restore the missing source binding;
- restore a bounded DUT-side output level; or
- restore the nominal 1.8-V rail.

The control does not silently fix high-clock or over-current background constraints. Those
remain unsafe after the injected fault is repaired.

Scripted repair success is not evidence of AI competence.

## Run

```bash
python scripts/run_spi_derived_virtual_lab.py
```

Optional durable outputs:

```bash
python scripts/run_spi_derived_virtual_lab.py \
  --report-out artifacts/derived_virtual_lab/report.json \
  --corpus-out artifacts/derived_virtual_lab/corpus.json
```

The process exits non-zero if any benchmark acceptance check fails.

## Acceptance bar

The v1 benchmark passes only when all of these hold:

- exactly 512 unique cases are generated;
- all eight profiles are represented;
- zero unsafe cases are missed;
- zero safe cases are falsely rejected;
- provenance-blocked cases remain blocked;
- every repair-eligible clean-background fault is repaired successfully;
- mutating SPI commands remain rejected;
- zero result gains manufacturer-model or physical authority.

## Relationship to the manufacturer-model lane

The intended fidelity ladder is:

```text
manufacturer document facts
        ↓
derived analytical / behavioral surrogate       <- this tranche
        ↓
manufacturer IBIS / Verilog execution            <- PR #93 campaign
        ↓
future physical measurement
```

Disagreement between these layers is itself a blocker/evidence signal.  The derived lab exists
to make development, adversarial testing, and repair benchmarking cheap; it does not replace
the manufacturer-model campaign.

## Astra policy

Astra is absent from this tranche.  The derived corpus, protocol oracle, evaluator, repair
control, and benchmark report are deterministic.  A future Astra experiment should consume a
frozen failing case and deterministic findings only after this benchmark is stable.
