# HS Native Electronics Acceptance — SPI Flash Adapter (2026-10-31)

**Scope:** re-execute the **existing** native KiCad SPI flash adapter instead of introducing another unsupported PCB generator. The ESP32 Sensor 001 engineering acceptance in PR #233 remains a separate baseline with firmware, mechanical, and catalog-level electrical verification.

## Existing true engineering capability

`hardware/reference_designs/spi_flash_adapter_v1` contains editable native KiCad 9 schematic and routed two-layer board, complete manufacturer-part-number BOM, a project rules file, generated package scripts, source datasheet hashes and `verify_design.py`. The design is a 3.3 V host to 1.8 V Winbond SPI flash adapter based on TXU0304PWR, TLV75518PDBVR and W25Q128JWSIQ.

The committed native verification receipt `verification.json` already records 0 ERC violations, 0 actionable DRC violations, 0 unconnected pads, 0 schematic-parity issues, 0 BOM parity errors and 0 routing-ground-reference errors, from KiCad 9.0.2. This is prior evidence, **not proof of a fresh CI run**.

## New independent reproducibility and Atlas lane

`.github/workflows/native-spi-eda-acceptance.yml` explicitly installs KiCad 9 CLI, the installed footprint/symbol libraries and `pcbnew` on Ubuntu 24.04. The launcher copies the entire canonical design into a fresh, isolated temp directory and invokes the original `verify_design.py`; no original source files or checked-in receipt can be overwritten.

The checker then independently ensures:

- Newly generated KiCad ERC/DRC reports and netlist really exist, follow the expected schemas and relate to the correct schematic/PCB.
- ERC has no violation, and DRC has no missing/unconnected pads or schematic-to-board parity issues; any footprint advisory must be narrowly characterized and matched to the reference verifier.
- The original source schematic/board/project/BOM/manifest/verifier hashes match the native receipt; changed sources must fail.
- The verifier and project manifest explicitly forbid physical power-on and fabrication, and the exact board and selected component identities remain the same.
- An Atlas-independent `hardware_splicer.external_capability.v1` manifest lists the validated native domains, input requirements, selected parts, toolchain versions, artifact types, report hash, reproduction commands and release blockers.

The separate adversarial test suite mutates the canonical hashes, reports, board-net parity, KiCad version, BOM checks and physical-authority flags. It runs without opening a browser or building firmware.

## Reproduce

On a system with KiCad 9 CLI, footprint libraries and `pcbnew` installed:

```bash
/usr/bin/python3 -m pytest -q tests/test_native_spi_capability.py
/usr/bin/python3 scripts/verify_native_spi_capability.py --out /tmp/hs-native-spi-check
```

The native check must actually run; a missing KiCad binary, unrecognized report schema, bad footprint or nonzero native rule check **blocks acceptance**, rather than falling back to a mock.

## Engineering boundaries

The SPI flash adapter is a **pre-fabrication modeled design**. The native EDA pass does not establish real power-rail behavior, board-assembly fidelity, edge timing, layout impedance, thermal safety, real host interoperability or actual manufacturing yield.

**This is not the same source specification as ESP32 Sensor 001.** The two cases must remain separate capability IDs. Only the versioned Atlas evidence contract is reused. We must not combine the SPI adapter's KiCad pass with the ESP32 device's firmware/geometry success and claim a single physically qualified product.

## Benchmark plan

The next external comparison can use this frozen SPI target and an identical design/BOM/rules dossier across HS, a domain engineer with KiCad and a general-purpose agent. Capture the actual native ERC/DRC, net parity, correctness, corrections, time and engineering cost for each arm. No relative performance, autonomous design superiority or inference cost claim is made in this PR.

Release tier: `MODELED_PRE_FAB_ONLY`, no physical authority.
