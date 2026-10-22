# Donor-to-Device v1 — RC toy to supervised inspection-rover drive base

This is a **consolidation and decision** layer over existing Hardware
Splicer's RC donor-to-carrier work, not a new circuit generator.

### Reused subsystems

| Existing capability | Existing location | New use |
| --- | --- | --- |
| Donor functional salvage | `examples/fixtures/splice_donor_rc_motor_board.json` and Circuit-AI | Treat the H-bridge and harness as conditional reuse, protect unknown donor power section |
| Splice planning and KiCad carrier | `examples/splice/manifest.json`, `splice_manifest.py`, `splice_demo.py` | Re-run canonical `robot_drive_from_rc_toy` instead of inventing another rover carrier |
| Cross-domain feasibility | `device_splice_feasibility.py` | Identify unresolved motor-power, signal, firmware, mounting and thermal interfaces |
| Safe build handoff | `real_device_work_package.py` | Convert the unresolved interfaces into measurable operator acceptance gates |
| External specialist engines | `external_engine_orchestration.py` | SolidCraft/FreeCAD remain OPTIONAL pending real donor measurements; never invent CAD dimensions |

### What is genuinely known?

The **intake declares** two 6 V geared motors, each 0.45 A running
and 0.9 A stall. Their declared combined stall-current demand is
1.8 A, plus other loads not yet characterized. Intake battery voltage
is 7.4 V nominal, with 2,200 mAh capacity. The motor driver/H-bridge
identities and real electrical ratings are unverified. The 7.4 V
battery MUST NOT be treated as directly compatible with a 6 V motor
without a supported controller/rail design. No independent motor,
driver or battery measurements exist in this package.

Donor fixture is a **synthetic/declared engineering scenario**, even if
an unrelated golden photo or manual capture exists elsewhere in HS.
No motor current, polarity, power-supply, wheel-diameter or chassis
measurements have been taken for this particular donor.

### Run

```bash
python scripts/build_donor_to_device_review.py \
  --out /tmp/hs-donor-rover-review
```

This emits:

- `DONOR_DEVICE_REVIEW.json`: source hashes, reuse/reject decisions,
  motor/power math, cross-domain compatibility and missing cost/geometry.
- `DONOR_DEVICE_WORK_PACKAGE.json`: existing HS structured engineering
  tasks, open unknowns and gate requirements.
- `DONOR_EVIDENCE_GATES.json`: measurable operator checkpoints.
- `DONOR_DEVICE_README.md`: concise source-backed handoff.

To exercise the EXISTING compile path rather than introduce new carrier
electrical code:

```bash
HARDWARE_SPLICER_AUTOROUTE=0 \
HARDWARE_SPLICER_DRC_FIX_LOOP=1 \
HARDWARE_SPLICER_SKIP_VISION_LIVE=1 \
HARDWARE_SPLICER_OFFLINE_SALVAGE=1 \
python scripts/splice_demo.py \
    --case robot_drive_from_rc_toy \
    --out /tmp/hs-rc-canonical-splice

python scripts/build_donor_to_device_review.py \
    --splice-result /tmp/hs-rc-canonical-splice/SPLICE_DEMO_RESULT.json \
    --out /tmp/hs-rc-compiled-handoff
```

When the compiler produces a same-run `.kicad_pcb`, the handoff
records its SHA-256. A reported DRC pass is not a fresh independent KiCad
receipt and is certainly not evidence of an assembled device.

### Physical and economic decision boundary

Full practical viability requires: identifying **the actual** H-bridge,
testing motors independently on a current-limited setup, authenticating
power/logic interfaces, verifying an emergency stop and timeout, and
measuring chassis/wheels/gearboxes for real CAD work. A motor's declared
running current is not its verified continuous duty capability.

Component SKUs, unit prices, yield/failure-path costs, assembly labor,
and viable resale price remain NULL. HS cannot claim gross margin or
a cheaper-than-buying alternative from this fixture. Buying parts or
running a physically powered motor is NOT approved.

This review can succeed as an **audit** while the device's engineering
status remains **blocked**. That separation is intentional and essential
to a credible hardware product.

### Consolidation discipline

This work lives on a separate branch based on the specialist-engine
orchestration PR #188. The earlier stacked PRs #184–#189 remain unmerged,
and the older SPI enclosure work is not duplicated here. After isolated
CI passes, evaluate rebasing against the then-current integration head;
do not automatically merge all six PRs or treat queued actions as passing.

Next decision after this acceptance: replace declared motor/driver/chassis
inputs with instrument/photo/dimension evidence from a **specific donor**.
Only then generate mechanical mounts with SolidCraft and bind verified
protection choices, assembly geometry, costs and operator bench results.
