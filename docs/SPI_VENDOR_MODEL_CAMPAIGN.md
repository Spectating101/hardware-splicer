# SPI vendor-model campaign

Status: staged on PR #93. No Astra execution is required.

This tranche converts the raw-document SPI result into one exact **virtual** implementation target and then refuses to award simulation credit until official manufacturer model bytes are captured and hash-bound.

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

The first campaign requires three captured artifacts:

1. TI `TXU0304 IBIS Model`, advertised as `SCEM787.ZIP`.
2. Winbond `W25Q128JWSIQ IBIS Model`, documentation item `DA03-AAG072`.
3. Winbond `W25Q128JW-Q Verilog Model`, documentation item `DA02-AAG072`.

An official landing page is **not** a captured model. `remote_available_not_captured` is therefore a blocker, not a weak pass.

TI exposes a stable direct model locator (`https://www.ti.com/lit/zip/SCEM787`). The Winbond model pages are currently represented by their official documentation landing locators because those download endpoints can be session/redirect mediated. HS must capture the resulting bytes explicitly before using them.

## Capture contract

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

Every capture still reports:

```text
modeled_evidence_only=true
measured_evidence_present=false
physical_correctness=UNPROVEN
physical_authority_granted=false
authority_effect=none
```

## Campaign readiness

Run:

```bash
python scripts/run_spi_virtual_model_campaign.py
```

Before model capture, the expected status is:

```text
model_capture_required
```

After supplying all three valid capture manifests:

```bash
python scripts/run_spi_virtual_model_campaign.py \
  --capture-manifest TXU.capture.json \
  --capture-manifest WINBOND_IBIS.capture.json \
  --capture-manifest WINBOND_VERILOG.capture.json
```

The strongest status the planner can produce is:

```text
ready_for_model_execution
```

That means only that the deterministic static bar, fault detection, and immutable model inputs are ready. It does **not** claim that any IBIS/Verilog run happened or passed.

## Frozen initial model executions

The planner preregisters five first executions:

1. nominal 3.3-V ↔ 1.8-V IBIS signal-integrity case at 5 MHz;
2. low DUT-rail corner at 1.773 V;
3. high DUT-rail corner at 1.827 V;
4. DUT rail absent / translator isolation boundary; and
5. read-only JEDEC-ID (`0x9F`) Verilog protocol case at 5 MHz.

These are modeled checks only. Later expansion can add load/cable/series-resistance sweeps, setup/hold analysis, overshoot/undershoot metrics, clock-rate sweeps, power-rail analytical/SPICE checks, and explicit failure thresholds.

## What remains blocked even after exact part selection

Exact virtual parts close useful ambiguity, but they do not yet close:

- physical DUT identity;
- actual programmer voltage/timing behavior;
- captured model hashes;
- loaded translator overshoot/output envelope;
- complete SPI propagation/setup/hold budget;
- worst-case DUT current and full 1.8-V rail current budget;
- system sequencing/protection/decoupling;
- schematic/ERC/PCB/DRC; or
- bench measurements.

The correct progression remains:

```text
catalog source
→ exact virtual target
→ immutable vendor model capture
→ deterministic model execution
→ adversarial/corner campaign
→ canonical bounded result
→ later physical evidence
```

Astra is deliberately absent from every stage above. Only after the deterministic verifier, model campaign, and repair-loop contracts are stable should a single bounded Astra repair experiment be considered.
