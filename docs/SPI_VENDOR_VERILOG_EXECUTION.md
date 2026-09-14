# SPI manufacturer-model execution path

This tranche sits on top of PR #97's real TI capture and fail-closed capability gate. Its job is
to make the remaining Winbond acquisition handoff mechanical and to prepare the first genuine
manufacturer-model behavioral execution without pretending that development fixtures are vendor
evidence.

## Frozen evidence order

```text
vendor listing
-> original vendor bytes
-> capture manifest + outer/member hashes
-> static model-content capability audit
-> exact-source compiler / engine preflight
-> capability-gated execution readiness
-> exact preregistered testbench execution
-> sealed + audited model result
-> surrogate-to-manufacturer calibration
-> later physical measurement
```

No earlier stage implies a later one.

## Required vendor files

The frozen campaign expects exactly these three model identities:

| Model ID | Publisher | Kind | Acquisition |
| --- | --- | --- | --- |
| `txu0304-ibis-scem787` | Texas Instruments | IBIS | public official `SCEM787.ZIP`; pinned by PR #97 |
| `w25q128jwsiq-ibis-da03-aag072` | Winbond | IBIS | Winbond portal / session download |
| `w25q128jw-q-verilog-da02-aag072` | Winbond | Verilog | Winbond portal / session download |

As observed on 2026-09-14, Winbond's exact `DA03-AAG072` and `DA02-AAG072` download pages redirect
an unauthenticated browser to Winbond sign-in. Hardware Splicer therefore does not scrape mirrors
or treat the searchable landing page as captured model bytes.

## One-shot preparation after Winbond download

Keep the two downloaded Winbond ZIPs unchanged. Then run:

```bash
PYTHONPATH=src python scripts/prepare_spi_vendor_campaign_inputs.py \
  --winbond-ibis /path/to/original-winbond-ibis.zip \
  --winbond-verilog /path/to/original-winbond-verilog.zip \
  --out-dir /tmp/hs-spi-vendor-inputs
```

The command:

1. re-fetches the pinned TI `SCEM787.ZIP` from the official endpoint (or accepts `--txu-zip`);
2. imports the two foreground Winbond ZIPs through the existing local-file capture contract;
3. validates outer hashes, archive safety, member hashes and model kinds;
4. audits TXU0304 IBIS capability;
5. audits W25Q128JWSIQ IBIS signal-integrity structures;
6. audits W25Q128JW-Q Verilog for a bounded `0x9F` / `EF6018` source candidate;
7. compile-preflights the exact Winbond Verilog members with Icarus;
8. builds PR #93's input-readiness campaign;
9. overlays PR #97's semantic-capability gate;
10. writes metadata/manifests/audits only. It does **not** copy raw vendor ZIPs into the output directory.

## Verilog preflight semantics

`spi_winbond_verilog_capability` performs static inspection only. It can identify modules,
behavioral logic, an explicit JEDEC-ID command marker, and the expected `EF6018` identity. Static
inspection alone keeps `jedec_id_read_9f_supported=false`.

`spi_vendor_verilog_preflight` then materializes only hash-bound recognized Verilog members into a
private temporary directory and runs Icarus with:

```text
iverilog -g2012 -tnull <exact captured model members>
```

Only a source candidate that also compiles can set the campaign capability field
`jedec_id_read_9f_supported=true`. In this context that field means **eligible for the bound JEDEC
testbench**, not "the JEDEC test passed." The preflight explicitly returns
`execution_credit_granted=false`.

The dedicated GitHub workflow uses a Hardware-Splicer-authored control fixture to prove the
capture/audit/Icarus plumbing. That fixture is labelled `development_control_only`, contains no
Winbond bytes, and is structurally ineligible for manufacturer-model campaign credit.

## IBIS semantics

The Winbond IBIS auditor requires the exact captured model to contain the W25Q128JW family marker
and ordinary IBIS signal-integrity structures before it can set
`eligible_for_later_signal_integrity_execution=true`.

That capability plus PR #97's audited TXU0304 capability can make the nominal, low-rail and
high-rail IBIS cases *eligible to execute*. It is still not a signal-integrity result.

The TXU rail-absent isolation case remains separately blocked because the captured TI IBIS model
does not execute the required `VCC disconnect / OE -> high-Z` transition.

## Next actual execution

After the original Winbond Verilog ZIP passes preparation, inspect its exact top-level module and
ports and build a testbench bound to those bytes. The frozen behavioral execution must:

1. drive standard SPI read-only command `0x9F` at 5 MHz;
2. observe `EF 60 18` from the manufacturer model;
3. prove no write or erase side effect;
4. retain exact model, harness, engine-version and raw-output identities;
5. seal the result through `spi_model_execution_contract`;
6. reject any missing, failed, foreign or authority-promoting result.

Until that execution occurs, Hardware Splicer has **manufacturer-model acquisition/preflight
evidence only**, not a passing manufacturer-model behavioral result.

## Authority ceiling

Every output in this lane remains bounded by:

```text
modeled_evidence_only=true
measured_evidence_present=false
physical_correctness=UNPROVEN
fabrication_ready=false
power_on_ready=false
physical_authority_granted=false
authority_effect=none
```
