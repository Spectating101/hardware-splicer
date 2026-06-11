# 10-minute professor demo

Offline-friendly walkthrough. No API keys. Shows honest authority gating and real KiCad/Gerber output.

## Before you start

```bash
python3 -m pip install -r requirements.txt
python3 scripts/hardware_splicer.py doctor
```

Confirm `demo_ready=True`. For Gerber export, confirm `fab_export_ready=True` (`kicad-cli` installed).

## 1. Bare brief → planning package (4/9 gates)

```bash
python3 scripts/hardware_splicer.py intake \
  --brief examples/intakes/plant_watering_brief.json \
  --out /tmp/hs_demo_tier1 --no-start-splicer
```

Open `/tmp/hs_demo_tier1/PRODUCTION_RELEASE_METRICS.json`:

- `gates_passed`: **4/9**
- `circuit_release`: **passed** (compiler-verified DRC)
- Open gaps: mechanical bench, robotics bench, integrated bench, field validation, release review

Point out: planning is coherent, but release is blocked until evidence is attached — not green-check theater.

## 2. Evidence pack → production-ready (9/9 gates)

```bash
python3 scripts/hardware_splicer.py intake \
  --brief examples/intakes/plant_watering_evidence_pack.json \
  --out /tmp/hs_demo_tier3 --no-start-splicer
```

Same project, closed evidence → `production_ready: true`, `gates_passed: 9/9`.

## 3. Real PCB + Gerbers (backend fab path)

```bash
python3 scripts/hardware_splicer.py build \
  --build-id automatic_plant_watering \
  --out /tmp/hs_demo_build
```

Artifacts:

- `build_compilation/main_ctrl_build.kicad_pcb` — DRC-clean KiCad board
- `build_compilation/BOM.json` — module MPNs, not generic headers
- `build_compilation/gerber_package/` — real Gerber layers (with `kicad-cli`)
- `DESIGN_QUALITY.json` — `drc_pass: true`
- `FUNCTIONAL_DELIVERY.json` — honest fab score

Inspect fabrication quality:

```bash
python3 scripts/hardware_splicer.py inspect-fab --build-dir /tmp/hs_demo_build
```

## 4. Tier progression (automated)

```bash
HARDWARE_SPLICER_SKIP_VISION_LIVE=1 make score-intake-tiers
cat /tmp/hardware_splicer_tier_scores/INTAKE_TIER_SCORES.json
```

Shows tier1 → tier3 → tier5 progression on the same plant-watering story.

## 5. Dashboard

```bash
cd apps/hardware-splicer-demo && npm install && npm run dev -- --port 5177
```

Seeded snapshots: brief plant (4/9), evidence plant (9/9), rover brief.

## 6. Full verification (optional)

```bash
make verify
```

114 tests + 15/15 catalog DRC + strict functional-delivery audit.

## What to emphasize

1. **Honest scoring** — `FUNCTIONAL_DELIVERY.json` splits artifact presence vs on-disk fabrication inspection.
2. **Compiler-verified circuit release** — DRC + electrical safety from the build graph, not draft prose.
3. **Evidence unlocks authority** — same archetype, different evidence → 4/9 vs 9/9 gates.
4. **Backend = fab path** — KiCad/Gerber come from `build_compiler.py` + Node graph compiler; Circuit-AI frontend `/build` is visualization + DRC honesty, not the production fab pipeline.
