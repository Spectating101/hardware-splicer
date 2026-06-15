# Material modes — scratch vs salvage

Same compile engine, editor, and netlist IR. The **only** difference is **what parts you're allowed to use**.

## Scratch (open / “zero”)

**Meaning:** Start from a goal or blank canvas. The design may **add any catalog module** needed — level shifters, regulators, MOSFETs, extra sensors.

| Surface | Same engine? |
|---------|----------------|
| NL compose (`compose`, phrase → modules) | Yes |
| Canvas / editor partial graph | Yes |
| Catalog kit recipes | Yes (curated starting points) |

**Constraints:** `strategy_mode: "open"` or default scratch compose.

## Salvage (constrained)

**Meaning:** Start from **what you have** (parts bin, intake photos, inventory list). You may only **buy a small set of gap-fillers** — not the full catalog.

| Source | Role |
|--------|------|
| `available_parts` / inventory | Primary modules |
| `allowed_purchases` | Optional buys (level shifter, LDO, …) |

**Constraints:** `salvage_mode: true` and/or `compose_from_inventory: true`, `strategy_mode: "constrained"`.

Default `allowed_purchases` when not specified:

- `level-shifter-4ch`
- `ldo-ams1117-3v3`
- `buck-mp1584`
- `resistor-10k`
- `mosfet-irlz44n`
- `relay-1ch-5v`

## Not abandoning the editor

The Circuit.AI canvas and scratch compose are **first-class**. Salvage is a **mode flag**, not a separate product:

```
                    ┌─────────────────────┐
                    │  Netlist + compile  │
                    │  (KiCad ERC/DRC)    │
                    └──────────▲──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
   Canvas / editor      NL scratch compose    Salvage intake
   (graph_mode)         (open catalog)      (inventory + buys)
```

## Quality JSON fields

`DESIGN_QUALITY.json` may include:

- `material_mode`: `"scratch"` | `"salvage"`
- `strategy_mode`: `"open"` | `"constrained"`
- `copper_preview_mode`: `"dual_layer"` (default, KiCad-clean) | `"single_layer"` (opt-in, may cross)
- `copper_tier`, `fab_recommendation` (honest fab guidance)

KiCad `via_dangling` **warnings** on preview copper are expected; errors must still be zero.

## Example intakes

| File | Mode |
|------|------|
| `examples/intakes/scratch_compose_brief.json` | Scratch / open |
| `examples/intakes/salvage_wifi_logger_brief.json` | Salvage / constrained |
| `examples/intakes/sensor_logger_brief.json` | Salvage with BME280 parts list |

## Is this valuable?

**Yes, in a specific way:** you can **prove** junk-drawer → KiCad-clean PCB package faster than hand-wiring in KiCad from scratch — with evidence artifacts for review.

**Not yet:** Flux-class autorouted copper, full symbol libraries, or “ship gerbers without looking.”

The wedge is **inventory-constrained bring-up with external verification** — scratch/editor remain the **unconstrained** face of the same engine.

## API and CLI (lightweight — no FreeRouting)

| Endpoint | Use |
|----------|-----|
| `POST /v1/compose` | phrase, `module_ids`, `netlist`, or `canvas_nodes` |
| `POST /v1/compose-canvas` | editor nodes (+ optional wires) |
| `POST /v1/engine-verify` | catalog KiCad bar |

Flags: `material_mode`, `strategy_mode` (`open` \| `constrained`), `salvage_mode`, `allowed_purchases`.

```bash
# Open scratch (catalog)
PYTHONPATH=src python3 scripts/hardware_splicer.py compose \
  --phrase "wifi temperature logger" --strategy-mode open --out /tmp/scratch

# Canvas / editor (same engine)
PYTHONPATH=src python3 scripts/hardware_splicer.py compose \
  --canvas-json examples/canvas/usb_esp_dht22.json --out /tmp/canvas

# Salvage (inventory + allowed buys)
make salvage-demo
```

Schematic export uses embedded `HS:*` block symbols + real footprint properties (no external KiCad libs required).

