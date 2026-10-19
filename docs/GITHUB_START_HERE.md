# Start here (GitHub / external review)

**Repo:** [Spectating101/hardware-splicer](https://github.com/Spectating101/hardware-splicer)  
**Product:** Splice Agent **v1.1.0-alpha.16** — auditable hardware bring-up + design verification  
**Status:** Cold-internal exit complete · **design partners open** · MIT  
**Pilots:** [`DESIGN_PARTNER.md`](DESIGN_PARTNER.md) · [`OFFER_SPLICE_BENCH_KIT_v1.md`](OFFER_SPLICE_BENCH_KIT_v1.md) · [`PROOF_PACK_CONTENTS.md`](PROOF_PACK_CONTENTS.md)

Use this page as the **single entry** when browsing on GitHub.

**Want to see what this means without reading an engineering report?**
Try the [old mouse → foot button worked example](MOUSE_REUSE_DEMO.md).
It shows the saved agent proposal and lets you try the actual software with
pretend presses. No hardware, account or model allowance is needed.

---

## 1. What to read first (15 minutes)

| # | Doc | Purpose |
|---|-----|---------|
| 1 | [RELEASE_v1.1.md](RELEASE_v1.1.md) | **Install, verify, deploy** |
| 2 | [COLD_INTERNAL_EXIT.md](COLD_INTERNAL_EXIT.md) | What is / isn’t claimed |
| 3 | [DESIGN_PARTNER.md](DESIGN_PARTNER.md) | How to join the 3-slot cohort |
| 4 | [QUICKSTART_SPLICE_v1.md](QUICKSTART_SPLICE_v1.md) | Install → doctor → first build |
| 5 | [DEMO_5_MIN_UI.md](DEMO_5_MIN_UI.md) | Demo script |

---

## 1b. Architecture (for contributors and agents)

Read these before changing engine or API code — both encode authority rules that
tests enforce.

| Doc | Purpose |
|-----|---------|
| [MACHINE_PROJECT_SPINE.md](MACHINE_PROJECT_SPINE.md) | Canonical project model, durable revisions, staged review workflow |
| [INTEGRATION_STACK.md](INTEGRATION_STACK.md) | Evidence-first boundary to external tools; donor virtual modules |
| [CONSOLIDATION_AUDIT_2026-07-31.md](CONSOLIDATION_AUDIT_2026-07-31.md) | **Current repo state** — what is verified, resolved, and still open |

## 1c. Build a device and run it off-hardware

| Doc | Purpose |
|-----|---------|
| [DEVICE_MODELED_RUN.md](DEVICE_MODELED_RUN.md) | Plan, generate, test and report an ESP32 + OLED + BME280 application with modeled execution — not physically validated hardware |
| [DEVICE_ADDING_PARTS.md](DEVICE_ADDING_PARTS.md) | How a controller board, sensor or display is added as cited data, and what each output needs from it |
| [AGENT_DEVICE_DESIGN.md](AGENT_DEVICE_DESIGN.md) | How an AI agent drives the device pipeline: spec schema, plan, suggested repairs, review, case, modeled run, with the authority limits |
| [DEVICE_ENGINEERING_REVIEW.md](DEVICE_ENGINEERING_REVIEW.md) | What a device layout implies for the bus, supply, heat, antenna, fit and printing, with every number sourced or assumed |
| [status/DEVICE_FAULT_MATRIX_BENCHMARK_2026-10-12.md](status/DEVICE_FAULT_MATRIX_BENCHMARK_2026-10-12.md) | How well its tests catch seeded bugs, and where they do not |

**Core doctrine, one line:** authority is never implicitly upgraded — importing,
seeding, diffing, and reviewing report state; they never promote a claim.

---

## 2. Verify

```bash
make verify-product-internal
```

CI: **Splice Agent v1** job on GitHub Actions.

---

## 3. Conversion / doctrine

| Doc | Purpose |
|-----|---------|
| [CONVERSION_DOCTRINE.md](CONVERSION_DOCTRINE.md) | Strong conversion strategy |
| [CONVERSION_PUSH.md](CONVERSION_PUSH.md) | Funnel tactics |
| [PROGRESSION_STATUS.md](PROGRESSION_STATUS.md) | Living status |

---

## 4. OSS interface layer (v1.1)

| Doc | Purpose |
|-----|---------|
| [V1.1_INTERFACE_PREVIEW.md](V1.1_INTERFACE_PREVIEW.md) | Scope boundary |
| [OSS_INTEGRATION_STATUS.md](OSS_INTEGRATION_STATUS.md) | Wired vs planned |
| [integrations/ARCHITON_GATE.md](integrations/ARCHITON_GATE.md) | Optional Architon compose |

---

## 5. Security & liability

- [SECURITY.md](../SECURITY.md)
- [SUPPORT_AND_LIABILITY_v1.md](SUPPORT_AND_LIABILITY_v1.md)
- [LICENSE](../LICENSE) — MIT
