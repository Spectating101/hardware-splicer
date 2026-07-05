# Apps in this monorepo

**Hardware-Splicer Splice Agent v1.0** ships from the **repository root** (`src/hardware_splicer/`, `scripts/`, `apps/splice-ui/`). The folders below are **platform depth** — not the v1 product install path.

---

## v1 product (ship this)

| Path | Role |
|------|------|
| [`splice-ui/`](splice-ui/) | **Consumer web UI** — wizard, async builds, gates, bench |
| [`circuit-ai/circuit-ai-frontend/`](../apps/circuit-ai/circuit-ai-frontend/) | KiCad graph compiler (Node) — required for splice compile |

Install: [`../docs/QUICKSTART_SPLICE_v1.md`](../docs/QUICKSTART_SPLICE_v1.md)

---

## Not v1 SKU (reference / future)

| Path | Role | Status |
|------|------|--------|
| [`circuit-ai/`](../apps/circuit-ai/) | Electronics intelligence, repair, vision, full API | Imported modules; broad platform |
| [`mecha-splicer/`](../apps/mecha-splicer/) | Mechanical splice, enclosures, DFM | S4 / future |
| [`3d-splicer/`](../apps/3d-splicer/) | Parametric enclosure API (CadQuery) | Optional compile chain |
| [`hardware-splicer-demo/`](../apps/hardware-splicer-demo/) | Authority dashboard (seeded snapshots) | Portfolio demo |

Do not point pilot customers at `make setup` full monorepo unless they are engine contributors.

---

## Documentation

| App | Docs |
|-----|------|
| Splice UI | [`splice-ui/README.md`](splice-ui/README.md) · [`../docs/UI_V1.md`](../docs/UI_V1.md) |
| Circuit-AI | [`circuit-ai/docs/README.md`](circuit-ai/docs/README.md) |
| Mecha-splicer | [`mecha-splicer/docs/`](mecha-splicer/docs/) |

Canonical index: [`../docs/DOCUMENTATION_INDEX.md`](../docs/DOCUMENTATION_INDEX.md)
