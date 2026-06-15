# Flux target

**Strategic bar:** beat Flux on the **compile engine**, then hang any UI on it. Not a side quest — the product thesis.

## What “kill Flux” means here

Not “clone their marketing.” It means a user can do in Circuit.AI what they do in Flux — **design a board, check it, export fab** — with less friction, and our checks are **real** (KiCad-native, not cosmetic).

| Capability | Flux | Us today | Must be true to compete |
|------------|------|----------|-------------------------|
| Schematic / design model | Full symbol sheet | Module graph + netlist IR (growing) | Arbitrary components + nets |
| Edit on canvas | Core product | Circuit.AI `/build` (module wiring) | Same API as engine |
| ERC | Yes | IR ERC + client safety rules | Single ERC truth |
| Placement | Yes | Arbitrary footprint placement + module slots | Arbitrary placement |
| Copper routing | Yes | Cosmetic segments (default); FreeRouting opt-in (`AUTOROUTE=1`) | KiCad-grade or equivalent |
| DRC | Yes | Internal + **KiCad CLI DRC** on routed PCB | KiCad DRC clean on shipped boards |
| KiCad in/out | Yes | PCB export; netlist import | `.kicad_sch` + `.kicad_pcb` round-trip |
| AI from intent | Copilot | Jarvis compose + salvage | NL → netlist → compile |
| One compiler | Yes | **OPEN** — TS fork still in frontend | Python only |

## Where we already pull ahead (if engine holds)

- Salvage / junk-drawer → wired build
- Headless CI compile (pytest, golden manifests, casefiles)
- Robotics / mech proof bundles
- Evidence-first fab gate (not “looks fine on canvas”)

## Engine order (no UI detour)

1. **KiCad files KiCad can open** — PCB v9 format (done in serializer)
2. **KiCad DRC on every compile** — `kicad_cli_drc.py` (done; gate not blocking yet)
3. **Real routing** — FreeRouting bridge wired; enable with `HARDWARE_SPLICER_AUTOROUTE=1` when ready
4. **Schematic IR export** — `.kicad_sch` from netlist (done)
5. **Retire TS compile** — `/build` calls `/v1/compose` + `/v1/compile-build` only
6. **UI** — borrow Flux/KiCad patterns; don’t invent

## Honest score

- **Bootstrap kits + compose:** competitive for makers
- **Flux-class arbitrary PCB:** engine path complete — routing + schematic + KiCad DRC/ERC; remaining gap is editor (Phase 4) and TS compiler fork (1.5)
- **Worth doing:** yes, if we keep measuring against this table, not against “18 kits pass”

See `docs/ENGINE_DONE.md` for gate IDs and CI status.
