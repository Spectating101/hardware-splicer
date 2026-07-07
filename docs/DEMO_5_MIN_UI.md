# 5-minute UI demo — Splice Agent v1.1 (Interface Preview)

**Purpose:** Repeatable demo for pilots, grant reviewers, and external proof.

**Prerequisites:** [`QUICKSTART_SPLICE_v1.md`](QUICKSTART_SPLICE_v1.md) complete; `hs-doctor` OK.

**Launch checklist:** [`RELEASE_v1.1.md`](RELEASE_v1.1.md)

---

## Setup (once)

```bash
source .venv/bin/activate
make splice-ui-serve
```

Open **http://127.0.0.1:8787**

Confirm sidebar shows **Engine: Online**.

---

## Demo script (~5 min)

### 1. Home (30 s)

- Headline: auditable bring-up + **design verification**
- **Before you fabricate or power on** pitch box
- Pipeline: Describe → Compile → **Verify** → Package → Gates
- Click **Quick demo (1-click)**

*Faster path:* **Recent builds** → succeeded job

### 2. Readiness verdict (45 s)

- **Readiness verdict** hero — hold vs power-on authorized
- Blocker list: open gates, DRC review, etc.
- Summary bar: gate progress, compile, power-on hold
- Say: *“This catches handoff gaps before fab or power-on.”*

### 3. Design verify (90 s)

- **Design verify** tab (default after build)
- Design flow stepper → KiCanvas preview
- **Compile truth** — DRC errors/warnings
- **Compile BOM** + **Fab artifact coverage**
- **Exports & interchange** — download path

### 4. Gates + bench (90 s)

- **Gates** tab — safety verdict, blockers
- **Bench** — close one gate with a measurement
- Readiness hero updates toward power-on OK (if all closed)

### 5. Wiring + download (30 s)

- **Wiring** — guide (topology diagram when present)
- **↓ Download zip** — full job bundle

### 6. Interface lab (optional 60 s)

- **Interface lab** — adapter proving ground (not main wizard)
- Canvas compile → View board in KiCanvas
- OSS integration map

---

## Talking points

| Audience | Say |
|----------|-----|
| Maker / repair | “No power-on until the checklist is green — and you can see fab/BOM gaps first.” |
| Lab / professor | “One package for student handoff: preview, BOM, fab readiness, gates.” |
| Prototype engineer | “DRC truth + casefile on failure — not hand-wavy AI.” |

**Value test question:** “Does this make a messy prototype easier to trust before fabrication or power-on?”

---

## API parity (optional 30 s)

```bash
curl -s http://127.0.0.1:8787/health
curl -s http://127.0.0.1:8787/v1/integrations/catalog | head
```

---

## Record for launch

Screen recording should show: Online → build → **readiness hold** → Design verify → one gate closed → download zip.

---

*Updated for v1.1.0 · July 2026*
