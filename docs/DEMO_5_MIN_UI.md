# 5-minute UI demo — Splice Agent v1

**Purpose:** Repeatable demo for pilots, grant reviewers, and visual auditors (e.g. ChatGPT).

**Prerequisites:** [`QUICKSTART_SPLICE_v1.md`](QUICKSTART_SPLICE_v1.md) complete; `hs-doctor` OK.

---

## Setup (once)

```bash
source .venv/bin/activate
make splice-ui-serve
```

Open **http://127.0.0.1:8787**

Confirm sidebar shows **Engine: Online** and version (e.g. v1.0.1).

---

## Demo script (~5 min)

### 1. Home (30 s)

- Read headline: salvage → carrier → gates
- Point at pipeline: Describe → Compile → Package → Gates
- Note **What you get** sidebar (KiCad, package, safety gates)

### 2. Quick demo (60–90 s)

- Click **Quick demo (1-click)**
- Build overlay appears with elapsed time
- Auto-navigates to **Project** when complete
- Toast: “Build complete — review safety gates”

*Alternative:* **Examples** → pick `splice_salvaged_robot_drive` → **Build selected example**

*Faster path:* **Recent builds** → click a succeeded job (skip compile wait)

### 3. Project summary (60 s)

- **Gate verdict** pill (e.g. `COMPILE READY REVIEW BENCH`)
- Progress bar: bench gates closed / total
- **Power-on: hold** until gates close
- Click **Close N gates on bench →** (jumps to Bench tab)

### 4. Gates tab (60 s)

- **Safety gate verdict** + blockers list
- Gate cards: critical vs open, prompts (what to measure)
- Emphasize: honest blocked state — not “looks good” schematics

### 5. Bench tab (60 s)

- Pick one open gate
- Enter measured value + unit (e.g. `5.02`, `V`)
- **Close gate** → toast confirms
- Refresh verdict / progress bar

### 6. Other tabs (30 s each, optional)

- **Parts** — BOM lines and estimate
- **Wiring** — markdown wiring guide
- **Build** — assembly steps
- **Overview** — goal, assumptions, build ID

### 7. Download (15 s)

- **↓ Download zip** — job bundle (KiCad, package JSON, guides)

---

## Talking points

| Audience | Say |
|----------|-----|
| Maker / repair | “No power-on until the checklist is green.” |
| EMS / NPI | “DRC truth + casefile on failure, not hand-wavy AI.” |
| Grant / tech | “CI-backed verify bar; same spine via HTTP and MCP.” |

---

## API parity (optional 30 s)

```bash
curl -s http://127.0.0.1:8787/health
curl -s http://127.0.0.1:8787/v1/examples/splice-intakes | head
```

Open http://127.0.0.1:8787/docs for integrators.

---

## Troubleshooting live demo

| Issue | Fix |
|-------|-----|
| Offline | Start `make splice-ui-serve` |
| Build fails | Check terminal / job error; `hs-doctor` |
| Empty recent builds | Run quick demo once |
| Gates already closed | Load different job or reset bench session on disk |

---

## Record for external proof

Screen recording should show: Online → build → gates blocked → one measurement → download zip.

For install proof on another machine, use [`INSTALL_REPORT_TEMPLATE.md`](INSTALL_REPORT_TEMPLATE.md).
