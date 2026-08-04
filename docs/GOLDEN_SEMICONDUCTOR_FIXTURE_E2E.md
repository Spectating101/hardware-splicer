# Golden Semiconductor DUT Fixture End-to-End Validation

This validation applies the revisioned Hardware Splicer JARVIS workflow to semiconductor testing and validation support hardware rather than robotics.

The case represents a low-voltage mixed-signal DUT socket adapter used before PCB fabrication and before any DUT is powered.

## Product scope

The validation is aligned with the project's semiconductor competition scope:

- test fixtures;
- validation and adapter boards;
- socket and pogo interfaces;
- lab and NPI support hardware;
- pre-fabrication readiness checking;
- evidence-gated review rather than autonomous production approval.

It does not model wafer processing, IC design, production test certification, or automatic fabrication release.

## Fixture case

`examples/semiconductor_fixture_e2e/low_voltage_dut_validation_adapter.json` defines:

- a replaceable 32-pin QFN DUT socket;
- a 1.8 V DUT core and digital I/O domain;
- a 3.3 V USB fixture controller;
- programmable current-limited DUT power;
- high-side current measurement;
- protected analog observation;
- keyed external test-equipment interface;
- fixture identification EEPROM;
- socket keepout and orientation constraints.

The case contains six synthetic, revisioned source documents:

1. DUT electrical limits;
2. DUT pin map;
3. socket mechanical drawing;
4. DUT test limits;
5. fixture-controller electrical manual;
6. current-limited bring-up procedure.

The fixture documents are deliberately synthetic so the validation is deterministic and redistributable. They are still treated as declared evidence rather than physical proof.

## Deliberate pre-fabrication blocker

The initial candidate assumes the 3.3 V fixture controller can manage the DUT digital interface after firmware initialization.

The declared evidence says:

- DUT digital I/O is 1.8 V;
- digital-pin absolute maximum is 2.0 V;
- direct 3.3 V drive is prohibited;
- controller reset may enable weak 3.3 V pull-ups;
- controller outputs are guaranteed disabled only after firmware initialization.

The deterministic compose preview therefore fails with:

`1.8 V DUT interface is not protected from 3.3 V controller`

The failure is expected and required. A tool failure here demonstrates correct readiness blocking.

## Seven-revision trace

The strict harness requires:

1. Revision 1 — six-source fixture project persisted.
2. Revision 2 — one DUT-adapter candidate and `run_compose` proposal persisted.
3. Revision 3 — named human acceptance for software preview only.
4. Revision 4 — deterministic voltage-domain failure persisted with artifact identity.
5. Revision 5 — separate protected-interface repair successor appended.
6. Revision 6 — JARVIS returns a blocked pre-fabrication decision briefing and typed `prepare_verification` proposal.
7. Revision 7 — exact revision-6 Engineering Package record persisted.

Replaying source revision 6 must verify the package and return idempotently without creating revision 8.

## Repair successor

The repair fixture requires:

- default-off 1.8 V referenced level translation;
- powered-off high-impedance behavior;
- per-line protection;
- explicit enable sequencing;
- reserved DUT pins remaining no-connect;
- a fresh deterministic preview only after a new human decision.

The original failed action and its tool artifact remain immutable.

## JARVIS decision briefing

JARVIS must cite:

- the exact failed tool-result identity;
- the DUT datasheet source;
- the fixture-controller manual source.

It must state that the fixture is not pre-fabrication ready and identify at least these unresolved areas:

- exact translator part and powered-off behavior;
- reserved-pin no-connect validation;
- current-limit and sequencing checks;
- socket pin-1 orientation;
- absence of physical resistance, power, thermal, and functional evidence.

Its recommended project-changing step is emitted as a typed `prepare_verification` proposal. It remains unaccepted and unexecuted.

## Engineering Package proof

The verified package must preserve:

- all six sanitized source descriptors;
- initial and repair requirements;
- initial and successor candidates;
- named human decision;
- failed deterministic preview;
- repair parent/child lineage;
- JARVIS evidence references and recommendation;
- source, open-question, tool-failure, and conversation blockers;
- package and project authority state.

The package must omit every raw synthetic document body. The browser or harness does not substitute hashes; ZIP size and SHA-256 are verified against the persisted backend record.

## Dual-domain regression

`.github/workflows/golden-semiconductor-fixture-e2e.yml` runs both:

- the semiconductor DUT fixture golden case;
- the indoor rover golden case.

This is intentional. The JARVIS architecture is only useful if the same evidence, action, repair, conversation, and package contracts remain valid across different hardware domains.

## Outputs

The semiconductor run writes:

- `GOLDEN_SEMICONDUCTOR_FIXTURE_E2E.json`
- `GOLDEN_SEMICONDUCTOR_FIXTURE_E2E.md`
- `GOLDEN_SEMICONDUCTOR_FIXTURE_PACKAGE.zip`

The workflow uploads these together with the rover report and package.

## Run locally

```bash
PYTHONPATH=src python scripts/run_golden_semiconductor_fixture_e2e.py \
  --strict \
  --out /tmp/golden-semiconductor-fixture-e2e
```

Subprocess contract:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_golden_semiconductor_fixture_e2e.py
```

## Authority boundary

A passing run does not authorize:

- PCB fabrication;
- fixture assembly;
- DUT insertion;
- DUT power-up;
- firmware flashing;
- production test;
- qualification;
- operational use;
- release.

It proves only that Hardware Splicer can preserve a semiconductor-fixture evidence conflict, produce a bounded repair successor, explain the remaining blockers, and export a reproducible pre-fabrication review package.
