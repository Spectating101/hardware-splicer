# Launch plan — Phases A–C (no FreeRouting)

Headless compiler platform for salvage → netlist → KiCad ERC/DRC → fab artifacts.
**FreeRouting / autoroute is explicitly deferred** (`HARDWARE_SPLICER_AUTOROUTE=0` default).

## Phase A — Launchable engine

| Item | Status |
|------|--------|
| `make verify-engine` — 18/18 catalogs KiCad DRC errors = 0 | CI + local |
| Netlist fixture suite (`examples/netlist_fixtures/`, 11 fixtures) | `tests/test_netlist_fixtures.py` |
| Honest quality flags in `DESIGN_QUALITY.json` | `copper_tier`, `fab_recommendation`, `kicad_truth_pass` |
| Compile casefiles on ERC / KiCad DRC failure | `COMPILE_CASEFILE.json` |
| Public verify commands | below |

### Verify commands

```bash
make setup
make verify-engine                    # full catalog bar (~20s, no Java)
pytest tests/test_netlist_fixtures.py # fixture ingest bar
PYTHONPATH=src python3 scripts/verify_engine.py --json /tmp/report.json
```

### Artifact meanings

| File | Meaning |
|------|---------|
| `circuit_netlist.json` | Canonical IR |
| `main_ctrl_build.kicad_sch` | Schematic stub for KiCad ERC |
| `main_ctrl_build.kicad_pcb` | Placed PCB (cosmetic copper by default) |
| `KICAD_DRC.json` / `KICAD_ERC.json` | External truth |
| `DESIGN_QUALITY.json` | Gates + honest fab guidance |
| `circuit_json.json` | tscircuit subset for viewers |
| `COMPILE_CASEFILE.json` | Failure debug bundle |

### Quality flags

- `copper_tier`: `placement_only` \| `cosmetic_preview` \| `autorouted`
- `fab_recommendation`: `blocked_*` \| `review_required_preview_copper` \| `eligible_with_human_review`
- `fabrication_ready`: only when autorouted copper + gerbers + KiCad clean (not default launch profile)

## Phase B — Differentiation

| Item | Status |
|------|--------|
| Rule-based passive suggestions (pull-ups, decoupling) | `netlist/passives.py` |
| JLC BOM enrichment | opt-in `HARDWARE_SPLICER_JLC_ENRICH=1` |
| circuit-json import | `integrations/circuit_json_import.py` |
| HTTP verify backend | `POST /v1/engine-verify` |
| LLM scope | compose / intake only; compile truth = KiCad |

## Phase C — Quality without autoroute

| Item | Status |
|------|--------|
| HPWL-aware placement order | `placement_hpwl.py`, default on |
| DRC warning budget in verify | `--max-warnings` (default 500) |
| KiCad DRC errors = 0 bar | `verify-engine` |
| FreeRouting | **deferred** |

## Deferred

- FreeRouting in CI or default compile path
- Circuit.AI canvas / UI parity
- Ship gerbers without human review

## Salvage bring-up demo

```bash
make salvage-demo
# or
PYTHONPATH=src python3 scripts/salvage_bringup_demo.py \
  --intake examples/intakes/salvage_wifi_logger_brief.json \
  --out /tmp/hs_salvage_bringup
```

Writes `SALVAGE_BRINGUP_REPORT.json` with artifact paths, KiCad truth, and review checklist.

## DRC fix loop (neurosymbolic)

KiCad DRC errors → structured `drc_fixup` hints on the build graph → recompile (default on).

| Env | Default | Meaning |
|-----|---------|---------|
| `HARDWARE_SPLICER_DRC_FIX_LOOP` | `1` | Enable retry loop |
| `HARDWARE_SPLICER_DRC_FIX_MAX` | `4` | Max fix attempts |

Artifacts: `DRC_FIX_LOOP.json`, `quality.drc_fix_loop` in `DESIGN_QUALITY.json`.

## Deferred
