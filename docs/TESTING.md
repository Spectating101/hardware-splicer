# Testing guide

## Quick commands

```bash
make setup              # venv + npm + 3D-Splicer (required once)
source .venv/bin/activate
make verify             # core professor path (~4 min)
make explore            # all catalog builds + intakes + scenarios (~2 min)
make explore-all        # explore + mecha + 3d app tests
make smoke              # Circuit-AI → Mecha → 3D-Splicer e2e
```

Free scratch space before long runs:

```bash
bash scripts/cleanup_test_artifacts.sh
```

By default, verify/explore write under **`.cache/hardware-splicer/`** in the repo (not `/tmp`). Override with:

```bash
export HARDWARE_SPLICER_TMP_ROOT=/mnt/bigdisk/hardware-splicer-scratch
```

Use a mounted volume or network share when your root disk is tight — CI uses ephemeral GitHub runners and does not need this.

## What each target covers

| Target | What it proves |
|--------|----------------|
| `make verify` | 115 root tests, 15/15 DRC benchmark, strict fab audit, tier scoring |
| `make explore` | Every catalog build, every intake brief, scenarios, compile specs |
| `make test-apps` | mecha-splicer (32) + 3d-splicer (10) |
| `make test-apps-full` | full circuit-ai (~425 tests) + mecha + 3d — installs torch stack, slow |
| `make smoke` | Full mecha + 3D-Splicer HTTP chain |

circuit-ai unit tests inherit your `.env.local` Qwen URLs unless isolated — `apps/circuit-ai/tests/conftest.py` clears those keys automatically.

## Optional profiles

**CadQuery STL rendering** (not required for KiCad fab demo):

```bash
make setup-cadquery
```

**Live Qwen vision** (needs API key in `.env.local`):

```bash
HARDWARE_SPLICER_RUN_VISION_LIVE=1 pytest tests/test_vision_live_optional.py -q
```

## Router / footprint behavior

- **Dual-routable modules** (e.g. buck converters with corner pads): real pad positions from `module-footprints.ts`.
- **Row / quad / dense modules** (MOSFET drivers, OLED, devkits): synthetic dual-column pad layout for DRC-safe routing; KiCad still uses the correct module footprint *name* and body envelope.
- Full per-pad geometry for every module shape is a larger autorouter project — not a quick patch.

## CI

GitHub Actions runs `make setup` + `make verify` + `make explore` on Ubuntu with KiCad + Node. Use that as the canonical green check when local disk is tight.
