# HS product restoration — Dell Latitude E5250 (real technician case)

**November 3, 2026.** First deliberately **whole-product** repair dossier. Prior benchmarks scored labeling and routing; this demonstration traces one source-backed repair from intake through electrical observations, component work, second startup failure and reported functional boot, with hard part/acceptance gates. No standalone app or new repair intelligence is invented: the operator report executes existing `RepairCaseEvaluator`, `RepairEncyclopedia`, `RepairVideoPlaybookBuilder` and `BoardSessionStore`.

## Source and observations

**Original professional technician:** [Sorin Electronics, October 5, 2026](https://sorinelectronics.co.uk/dell-laptop-not-charging/). [Linked electronics repair video](https://www.youtube.com/watch?v=fi-Vt34Al_A), which was not separately frame-audited.

- Intake: a Dell Latitude E5250 does not boot or charge; external adapter reports **19.9 V** unloaded, but its indicator extinguishes when connected to the laptop.
- Isolation: technician reports a nominal 19 V bench supply delivered **2.3 A** into the short while the rail collapsed nearly to zero; removing the charging port did not clear the short.
- Localization: a current-sense resistor appeared warm, but was merely passing fault current. A nearby ceramic capacitor subsequently exhibited heat evidence; removing it reportedly cleared the short.
- Component restoration: source technician describes installing a donor MacBook capacitor (**exact electrical specification not supplied**); the repaired input rail later reportedly measured **19.9 V** at roughly **40 mA**.
- Second fault state: laptop initially remained nonbooting with power button logic at **3.3 V**. Technician reported that a BIOS/RTC battery disconnect before charger application changed startup behavior. Source describes risky energized RTC reconnection — do **not** reproduce that technique.
- Claimed outcome: system booted to a Windows **BitLocker password prompt** and later power cycles reportedly behaved normally. Battery cycling, thermal burn-in, owner data access and full product sign-off are not documented. These are technician reports, not measurements by HS.

## Executable system deliverables

Input: `examples/whole_product_restorations/dell_latitude_e5250_technician_case_2026.json`.

Run:
```bash
python -m pip install -e . "numpy>=1.26,<3" "networkx>=3,<4"
python -m scripts.run_hs_whole_product_restoration_e5250 --out .cache/hs_e5250_product_restoration
python -m scripts.verify_hs_whole_product_restoration_e5250 --case examples/whole_product_restorations/dell_latitude_e5250_technician_case_2026.json --out .cache/hs_e5250_product_restoration
```

Outputs: `WHOLE_PRODUCT_ENGINE_TRACE.json` (actual raw stage-by-stage original-engine responses), `WHOLE_PRODUCT_SOURCE_LEDGER.json` (attribution, source technician readings and interventions), `WHOLE_PRODUCT_DISPOSITION.json` (product readiness), `WHOLE_PRODUCT_RESTORATION_DOSSIER.md` (human operator report), `WHOLE_PRODUCT_MANIFEST.json` (content checksums), `WHOLE_PRODUCT_EVIDENCE_AUDIT.json` (separate evidence verifier under CI).

This deliberately does not tune the engine to obtain a flattering result. The assessment is **retrospective** because the source's outcome was known at selection; stage T5 remains withheld from prediction inputs, but this is **not a new blind study**.

## Correct engineering gate

Conditional model-specific capacitor **cannot be ordered or authorized** without verified capacitance, dielectric, voltage rating, footprint, installation reference, board revision and supplier data. No invented parts price, labor bill, resale value or arbitrage margin. The technician reportedly restored **three of eight** source-functional acceptance items; HS independently verified **zero of eight**. In particular, OS/BitLocker screen appearance does not prove battery health, continued operation, disk access or full customer acceptance.

**Safety:** never substitute an unspecified donor MLCC, use a flammable solvent in heat diagnosis, hot-plug an RTC battery on a powered board, or inject high current into a motherboard based on this replay. All hazardous work requires a qualified technician and model-specific documented procedures.

## Decision after running

- Preserve whatever the existing Circuit-AI actually predicted on the five source chronology checkpoints (including wrong leading fault).
- Operator report must show measurements, risk gates, source method and final functional acceptance matrix in the same artifact.
- A future **real device** pilot must attach manufacturer model/board revision, owner consent, qualified technician test logs, verified replacement component and signed functional acceptance before HS could claim an independently repaired product.
