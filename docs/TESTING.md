# Testing guide

## Quick commands

```bash
make setup              # venv + npm + 3D-Splicer (required once)
source .venv/bin/activate
make test               # complete root Python regression
make verify             # root regression, catalogs, audits, tiers and smoke
make explore            # all catalog builds + intakes + scenarios (~2 min)
make explore-all        # explore + mecha + 3d app tests
make smoke              # Circuit-AI → Mecha → 3D-Splicer e2e
```

Run the cleanup target after verification jobs finish.

```bash
make cleanup
```

This removes the completed `exploration`, `functional_audit`, `backend_benchmark` and `tier_scores` directories containing their matching HS reports. Exploration and cluster verification leave cleanup to the operator. The default scratch directory is **`.cache/hardware-splicer/`** in the repo. To run and clean tests on another volume, choose a dedicated directory.

```bash
export HARDWARE_SPLICER_TMP_ROOT=/mnt/bigdisk/hardware-splicer-scratch
```

Use a mounted volume or network share when your root disk is tight — CI uses ephemeral GitHub runners and does not need this.

## What each target covers

| Target | What it proves |
|--------|----------------|
| `make test` | Complete root Python regression; optional profiles retain their explicit skip gates |
| `make verify` | Root tests, catalog checks, golden intakes, backend benchmark, functional audit, tier scoring, splice and smoke checks |
| `make explore` | Every catalog build, every intake brief, scenarios, compile specs |
| `make test-apps` | Mecha-Splicer and 3D-Splicer app suites in their configured Python environments |
| `make test-apps-full` | full circuit-ai (~425 tests) + mecha + 3d — installs torch stack, slow |
| `make smoke` | Full mecha + 3D-Splicer HTTP chain |

circuit-ai unit tests inherit your `.env.local` Qwen URLs unless isolated — `apps/circuit-ai/tests/conftest.py` clears those keys automatically.

After integrating backend branches, run the complete root regression as well as focused tests. To keep the full run offline:

```bash
PYTHONPATH=src \
HARDWARE_SPLICER_SKIP_VISION_LIVE=1 \
HARDWARE_SPLICER_OFFLINE_LLM=1 \
HARDWARE_SPLICER_OFFLINE_VISION=1 \
HARDWARE_SPLICER_OFFLINE_SALVAGE=1 \
QWEN_DISABLED=1 \
.venv/bin/python -m pytest tests -q --tb=short \
  --junitxml=.cache/hardware-splicer/root-results.xml
```

The [November 16 full verification](GITHUB_FEATURE_INTEGRATION_2026-11-16.md#full-suite-verification) records 4,202 passing root tests, 32 optional skips, three passing subtests, and the separate app-suite results. The root run took about 15 minutes on the tested workstation; allow time for native KiCad and compiler checks.

## Optional profiles

**CadQuery STL rendering** (not required for KiCad fab demo):

```bash
make setup-cadquery
```

**Live Qwen vision** (needs API key in `.env.local`):

```bash
HARDWARE_SPLICER_RUN_VISION_LIVE=1 pytest tests/test_vision_live_optional.py -q
```

The [extended native verification](GITHUB_FEATURE_INTEGRATION_2026-11-16.md#extended-native-verification) exercises 29 of those previously skipped cases using CadQuery, trimesh, PyBullet, native `pcbnew`, pinned vendor libraries and restored public source fixtures. The complete run and the 105-test follow-up are recorded separately; their overlapping counts must not be added. The remaining three gaps are live-vision provider checks. A separate Gemini attempt failed because its configured key was invalid.

For this profile, use one Python environment that can import all required packages, including packages used by CLI subprocesses:

```bash
"$NATIVE_PYTHON" -c 'import pytest, cadquery, trimesh, pybullet, pcbnew, pypdf'
PYTHONPATH=src "$NATIVE_PYTHON" -m pytest tests -q --tb=short
```

The exact fixture URLs, immutable commits, file hashes, dependency versions and opt-in environment settings are in the [extended receipt](status/generated/extended-native-verification-2026-11-16.json). External source tests retain their existing explicit availability gates; restore the recorded source files to the locations they expect before claiming that coverage. Both Java routing paths force headless operation.

Positive evidence-closure tests using `assume_clean_kicad_erc` test downstream behavior under that stated assumption. Their success does not validate the example circuit. The real KiCad replay rejects the plant package's production claim with four ERC errors, while retaining its planning-only package and listing the electrical work still required.

## Router / footprint behavior

- **Dual-routable modules** (e.g. buck converters with corner pads): real pad positions from `module-footprints.ts`.
- **Row / quad / dense modules** (MOSFET drivers, OLED, devkits): synthetic dual-column pad layout for DRC-safe routing; KiCad still uses the correct module footprint *name* and body envelope.
- Full per-pad geometry for every module shape is a larger autorouter project — not a quick patch.

## CI

GitHub Actions runs `make setup` + `make verify` + `make explore` on Ubuntu with KiCad + Node. Use that as the canonical green check when local disk is tight.
