# SPI vendor-model campaign

Status: staged on PR #93. No Astra execution is required.

This tranche converts the raw-document SPI result into one exact **virtual** implementation target and then refuses to award model-backed credit until the relevant manufacturer-model bytes are captured, hash-bound, executed through a bounded engine, and adjudicated.

## Exact virtual target

The selected software target is intentionally not a claim about the physical chip on a bench:

- DUT: `W25Q128JWSIQ`, SOP-8 208 mil, 128 Mb, 1.7–1.95 V, 133 MHz STR catalog maximum.
- Translator: `TXU0304PWR`, TSSOP (PW), 14 pins.
- Translator rail A: 3.3 V host domain.
- Translator rail B: 1.8 V DUT domain.
- Signal map: A1→B1Y SCLK, A2→B2Y MOSI, A3→B3Y CS#, B4→A4Y MISO.
- OE policy: tied to the 1.8-V B-side rail in this virtual candidate so the translator is not intentionally enabled without the DUT domain.
- Virtual 1.8-V source: `TLV75518PDBVR`, SOT-23 (DBV), 5 pins.
- Initial requested SPI clock: 5 MHz. This is a test point, not a proven maximum.

`physical_identity_asserted=false` remains mandatory. The selected Winbond orderable suffix is a simulation target only until a physical marking/package is observed and independently reconciled.

## Manufacturer source boundary

Catalog facts are bound to official manufacturer sources:

- Winbond 2025 Code Storage Flash product-selection guide for `W25Q128JWSIQ` package, voltage, interface, and catalog STR rate.
- TI TXU0304 product/part page for `TXU0304PWR` and package identity.
- TI TXU0304 datasheet pin table for the three A→B plus one B→A channel arrangement, OE behavior, and rail references.
- TI TLV755P part page for `TLV75518PDBVR`, fixed 1.8-V variant, output-current class, soft start, package, and minimum output-capacitor statement.

The exact URLs are persisted in `hardware_splicer.spi_virtual_target`.

## Required manufacturer models

The complete first campaign requires three captured artifacts:

1. TI `TXU0304 IBIS Model`, advertised as `SCEM787.ZIP`.
2. Winbond `W25Q128JWSIQ IBIS Model`, documentation item `DA03-AAG072`.
3. Winbond `W25Q128JW-Q Verilog Model`, documentation item `DA02-AAG072`.

An official landing page is **not** a captured model. `remote_available_not_captured` therefore earns no modeled execution credit.

TI exposes a stable public model locator at `https://www.ti.com/lit/zip/SCEM787`. Winbond publicly lists both target resources as ZIP-format model artifacts, but the selected download page can return `login_required`. HS therefore supports both direct network capture and explicit local-file import; a vendor session requirement is an acquisition boundary, not a reason to weaken the model-evidence contract.

## Capture contracts

### Direct network capture

`scripts/capture_vendor_model.py` performs one explicit foreground fetch. The capture layer:

- accepts only HTTPS;
- requires an explicit manufacturer-host allowlist;
- revalidates the final redirect host;
- enforces a byte ceiling;
- rejects HTML/login/interstitial responses masquerading as model files;
- hashes the complete payload;
- inventories and hashes every ZIP member without extracting it;
- rejects encrypted or path-traversing ZIP members; and
- emits `hardware_splicer.vendor_model_capture.v1`.

### Local import for vendor-session downloads

When a vendor requires login, cookies, terms acceptance, or another browser session, download the model file normally and import the exact local file:

```bash
python scripts/import_vendor_model.py \
  --model-id w25q128jw-q-verilog-da02-aag072 \
  --file ~/Downloads/<vendor-file>.zip \
  --manifest-out artifacts/WINBOND_VERILOG.capture.json
```

The local importer uses the frozen HS model registry to select the expected vendor host and model kind. It does **not** persist the local full path, does not execute the model, and does not publish the raw model bytes. It applies the same byte ceiling, semantic model recognition, outer SHA-256, member inventory/hash, and authority boundary as network capture.

Every capture reports:

```text
modeled_evidence_only=true
measured_evidence_present=false
physical_correctness=UNPROVEN
physical_authority_granted=false
authority_effect=none
```

## Campaign readiness is per execution

Run:

```bash
python scripts/run_spi_virtual_model_campaign.py
```

With no valid model captures, the expected status is:

```text
model_capture_required
```

A partial capture can unlock only the executions whose complete model set is available. For example, a valid TXU0304 IBIS capture can make the TXU-only DUT-rail-absent/isolation case ready while nominal/high/low two-device IBIS cases and the Winbond Verilog case remain blocked:

```text
partial_model_execution_ready
ready_execution_ids = ["ibis-dut-rail-absent"]
```

Likewise, a valid Winbond Verilog capture alone can make only `verilog-jedec-id-read-9f` ready. Missing model inputs never get substituted or fabricated.

After supplying all three valid capture manifests:

```bash
python scripts/run_spi_virtual_model_campaign.py \
  --capture-manifest TXU.capture.json \
  --capture-manifest WINBOND_IBIS.capture.json \
  --capture-manifest WINBOND_VERILOG.capture.json
```

The planner can then reach:

```text
ready_for_model_execution
```

That means only that every preregistered execution has immutable required inputs and the shared deterministic preconditions are safe. It does **not** claim that an IBIS/Verilog run happened or passed.

## Frozen initial model executions

The planner preregisters five first executions:

1. nominal 3.3-V ↔ 1.8-V IBIS signal-integrity case at 5 MHz;
2. low DUT-rail corner at 1.773 V;
3. high DUT-rail corner at 1.827 V;
4. DUT rail absent / translator isolation boundary; and
5. read-only JEDEC-ID (`0x9F`) Verilog protocol case at 5 MHz.

A per-execution result must bind the exact required model hashes, engine/version, successful process exit, raw-output SHA-256, case-specific machine-readable checks, finite metrics, and the modeled-only authority boundary. A partial campaign may receive credit for a ready individual execution, but **complete campaign credit remains impossible** until exactly one accepted result exists for every preregistered execution.

The campaign adjudicator rejects missing executions, duplicates, foreign execution IDs, failed per-execution audits, or authority promotion. Its strongest result remains `passed_modeled_campaign`, never a physical pass.

## What remains blocked even after model execution

Exact virtual parts and passing simulations close useful software uncertainty, but they do not establish:

- physical DUT identity;
- actual programmer voltage/timing behavior;
- real interconnect parasitics and workmanship;
- complete system sequencing/protection/decoupling under physical conditions;
- schematic/ERC/PCB/DRC equivalence to an assembled article; or
- bench measurements.

The progression is:

```text
catalog source
→ exact virtual target
→ immutable vendor model capture/import
→ per-case deterministic model execution
→ full preregistered modeled campaign
→ canonical bounded result
→ later physical evidence
```

Astra is deliberately absent from every stage above. Only after the deterministic verifier, model campaign, and repair-loop contracts are stable should a single bounded Astra repair experiment be considered.
