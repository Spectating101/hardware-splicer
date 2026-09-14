# TXU0304 manufacturer-model capture

Status: real TI model bytes captured in CI; metadata evidence retained; raw vendor bytes not published.

This tranche is the first manufacturer-model acquisition step above the frozen SPI verification
infrastructure. It does not claim a passing model execution or any physical result.

## Official acquisition

The source is the TI TXU0304 product's published simulation model:

- requested URL: `https://www.ti.com/lit/zip/SCEM787`;
- advertised artifact: `SCEM787.ZIP`;
- expected model kind: IBIS;
- acquisition method: bounded HTTPS network fetch from the TI host allowlist.

The exact CI capture produced:

```text
outer size:    58,240 bytes
outer SHA-256: sha256:1b7b33ae0ce9452eb69ed6ccea4d05f558fef83023d7bc6637b8e9342eb4b4d0
IBIS member:   TXU0304.ibs
member size:   308,012 bytes
member SHA-256: sha256:189defbd3a8b3a8405eef3128bf539c13a9341aed4793d97746d33b2ab56145a
```

Raw `SCEM787.ZIP` is deleted before artifact publication. The CI artifact contains only the
capture manifest, capability audit, input-readiness projection, capability-gated projection,
and final adjudication.

## Observed IBIS capability boundary

The captured model contains four component identities:

- `TXU0304BQA`;
- `TXU0304DTR`;
- `TXU0304PW`;
- `TXU0304RUT`.

The bounded audit found 10 model definitions with `Input` and `Output` model types. It found pin,
model, pull-up, pull-down, ground-clamp, ramp, rising-waveform, and falling-waveform structures.
It did not find a 3-state model, a power-clamp section, or textual power-state markers.

That is useful manufacturer-model structure for later signal-integrity work. It is not an
executable representation of the system-level TXU0304 rule that outputs become high impedance when
a supply is disconnected.

## Two readiness layers

The original campaign planner from PR #93 reports **input readiness**: with the TXU capture present,
all required model files named for `ibis-dut-rail-absent` are available.

The real-byte capability gate is stricter. It reports:

```text
input campaign status:      partial_model_execution_ready
input-ready execution:      ibis-dut-rail-absent
capability-gated status:    captured_models_no_semantically_executable_case
capability-ready executions: []
executed model results:     0
```

This distinction is intentional. Possessing a genuine vendor model is not evidence that the model
contains the semantics required by every preregistered check.

## Remaining manufacturer-model blockers

The three nominal/high/low signal-integrity executions still require the Winbond
`W25Q128JWSIQ` IBIS model (`DA03-AAG072`). The read-only `0x9F` protocol execution still requires
the Winbond `W25Q128JW-Q` Verilog model (`DA02-AAG072`). Their official landing pages are
session/login-gated, so Hardware Splicer keeps those bytes uncaptured until a legitimate vendor
session supplies files for the existing local import path.

## Evidence ceiling

All retained outputs remain:

```text
modeled_evidence_only=true
measured_evidence_present=false
physical_correctness=UNPROVEN
fabrication_ready=false
power_on_ready=false
physical_authority_granted=false
authority_effect=none
```
