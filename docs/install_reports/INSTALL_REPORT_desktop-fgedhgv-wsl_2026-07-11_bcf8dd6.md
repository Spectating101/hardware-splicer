# Install / alien-machine report — DESKTOP-FGEDHGV (WSL2) — `bcf8dd6`

**Purpose:** Durable provenance that Splice Agent `bcf8dd6` installs and runs on a machine that is **not** the Optiplex development box, including optional FreeRouting.

**Operator:** Cursor/Grok agent via SSH → WSL (not an independent human).  
**Frontend status:** Remains frozen at this commit — no product code changes in this evidence pass.

Evidence bundle: [`evidence/fgedhgv-bcf8dd6-alien/`](evidence/fgedhgv-bcf8dd6-alien/)

---

## Report metadata

| Field | Value |
|-------|-------|
| **Tester** | Agent (SSH from Optiplex → `desktop-fgedhgv`) — **not** independent human |
| **Date** | 2026-07-11 |
| **Git commit** | `bcf8dd6a6a8a9dc1b6020690ffccc847d0da361c` |
| **Machine** | `DESKTOP-FGEDHGV` |
| **OS** | Windows host + WSL2 Ubuntu 24.04 (`Linux … 6.6.87.2-microsoft-standard-WSL2`) |
| **KiCad / pcbnew** | `kicad-cli` / pcbnew **9.0.9** |
| **Java** | OpenJDK **21.0.11** (installed during this probe) |
| **FreeRouting** | **2.1.0** jar (downloaded to cache; not in repo) |
| **Python / Node** | Present via `install_splice_v1.sh` (doctor: fastapi/uvicorn/node/npm ok) |

---

## What was proven

```text
install + doctor
→ serve integrated UI (SERVE_UI)
→ Intake → Continue to Design
→ KiCad canvas agent-loop (ESP32 + DHT22)
→ DRC 0 errors / preview copper
→ synchronous package archive download
→ opt-in FreeRouting (confirm=true) → routed PCB, 62 tracks
```

Honesty preserved after FreeRouting: still `cosmetic_preview` / `review_required_preview_copper` / `fabrication_ready=false`.

---

## Exact commands (alien WSL)

Deploy archive of `bcf8dd6` to Windows home, then in WSL as root:

```bash
# Core install (from extracted archive)
bash scripts/install_splice_v1.sh
source .venv/bin/activate
PYTHONPATH=src python scripts/hardware_splicer.py doctor

# Optional autoroute dependencies (NOT required for core product)
sudo apt-get update
sudo apt-get install -y openjdk-21-jre-headless
mkdir -p ~/.cache/hardware-splicer/freerouting
curl -fL -o ~/.cache/hardware-splicer/freerouting/freerouting-2.1.0.jar \
  https://github.com/freerouting/freerouting/releases/download/v2.1.0/freerouting-2.1.0.jar
export HARDWARE_SPLICER_FREEROUTING_JAR=$HOME/.cache/hardware-splicer/freerouting/freerouting-2.1.0.jar

# Serve UI + API
cd apps/splice-ui && npm install && npm run build && cd ../..
HARDWARE_SPLICER_SERVE_UI=1 HARDWARE_SPLICER_AUTOROUTE=0 \
HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 HARDWARE_SPLICER_OUTPUT_ROOT=/tmp/hardware_splicer_api \
PYTHONPATH=src python -m uvicorn hardware_splicer.api:app --host 127.0.0.1 --port 8787

# Canvas agent-loop (deterministic modules)
curl -s -X POST http://127.0.0.1:8787/v1/compose/agent-loop \
  -H 'Content-Type: application/json' \
  -d '{"phrase":"ESP32 DHT22 soil moisture logger with OLED","canvas_nodes":[{"id":"m1","moduleId":"esp32-devkit"},{"id":"m2","moduleId":"dht22"}],"allow_llm_first":false,"max_manual_retries":2,"finalize_package":true,"project_name":"alien_fr_esp32_dht22","export_gerber":false}'

# Package archive (sync Studio/build_dir path)
curl -sf -o project-package.zip \
  "http://127.0.0.1:8787/v1/build-files/package-archive?build_dir=<OUT_DIR>"

# Opt-in FreeRouting only
curl -s -X POST http://127.0.0.1:8787/v1/build-files/autoroute \
  -H 'Content-Type: application/json' \
  -d '{"build_dir":"<OUT_DIR>","confirm":true}'
```

Do **not** make Java mandatory for core install. Do **not** enable FreeRouting by default.

---

## Results summary

### Compose / DRC (`agent_loop_fr_summary.json`)

| Field | Value |
|-------|-------|
| Agent resolved | `true` |
| KiCad DRC errors | `0` |
| Copper tier | `cosmetic_preview` |
| Fabrication ready | `false` |
| Project package present | `true` |
| Build dir | `/tmp/hardware_splicer_api/compose/0d51c0af1d0642bc99ba028e4fcd049e` |

### FreeRouting (`autoroute_after_install.json`)

| Field | Value |
|-------|-------|
| `ok` | `true` |
| Skipped | `false` |
| Version | `2.1.0` |
| Track count | `62` |
| Routed PCB (ephemeral on alien) | `/tmp/hs-fr-ie6odgt8/routed.kicad_pcb` |
| Copper after FR | still `cosmetic_preview` |

### Hashes (artifacts not committed)

| Artifact | SHA-256 | Size |
|----------|---------|------|
| `freerouting-2.1.0.jar` | `2c07d58f75dac03782664081e7a58b41c25400d871a9fcf166a2ea6fe60d5def` | ~64 MiB |
| `project-package.zip` (pre-FR) | `f9be5288b7ef16b996bfaf1211206ed429b9a9bab67afaa8f693cfbd03000544` | 25843 B |
| `project-package-after-fr.zip` | `583fbb5b8e32bd75a762cdca43d19090d57a2f13ca42b08816f37372b4d2aa1c` | ~25 KiB |

ZIP and JAR remain on the alien host / local scratch only — **not** in git.

---

## Screenshots (selected)

| File | Content |
|------|---------|
| `01-home.png` | Home / Start a project |
| `02-intake.png` | Intake stage (Design locked) |
| `03-intake-review.png` | Review → **Continue to Design** |
| `04-design.png` | Design empty-state with Intake goal |

Verify/Package UI screenshots were not required: package handoff was proven by downloading the ZIP on the alien machine. Sync builds are not persisted as Recent Jobs after restart (known in-memory limitation).

---

## Explicit non-claims

- Not an independent-human usability test.
- FreeRouting success ≠ electrically correct or fabrication-ready copper.
- Routed PCB quality (widths, vias, topology) was not reviewed by a human.
- Physical board / café measurement not performed.
- Commercial demand not tested.

---

## Bottom line

Second-machine qualification for `bcf8dd6` is **complete enough**: install, UI, KiCad DRC, package archive, and optional FreeRouting all executed on DESKTOP-FGEDHGV WSL with claim honesty preserved.

**Next unknown requires a human** with only the public quickstart and no live guidance.
