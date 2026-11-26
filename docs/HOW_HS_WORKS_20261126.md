# How Hardware-Splicer works (state on 2026-11-26)

## What it is for

**HS turns junk into working hardware.** For every objective it tries, in order: salvage or adapt discarded devices,
buy a finished or used product when that is cheaper, and design new only for what is left. Its edge over a factory is
not price on things that already sell (a US$30 robot beats any one-off build); it is making something work from
whatever is at hand, and saying honestly what is proven. The business case and grant applications rest on the numbers
every project now produces: new spend, junk reused, new-part value replaced, and hours.

## How one objective flows

```text
objective ─► 1 what exists? ─► 2 which junk? ─► 3 decide ─► 4 engineer ─► 5 cost ─► 6 package ─► 7 verify
             (enforced)        (catalogue)      (reasons)   (checks)      (enforced)  (build guide) (software ≠ physical)
```

| Step | HS tools | What is enforced |
|---|---|---|
| Open | `hs_project_open`: one project folder, an append-only ledger of every step | Every tool run is recorded with its inputs |
| 1. What already exists | `hs_prior_art_search`: HS's own past findings (docs, examples, project records, the landscape register), GitHub projects by stars and topic, BoardRepo boards, GitHub KiCad files, with licences; `hs_read_board`. Shops (Shopee, AliExpress, Amazon) by web search | Project status shows "prior art" open until a search or research is recorded |
| 2. Which junk | `hs_junk_lookup`: 13 device types (phones, robot vacuums, RC toys, laptop batteries, hoverboards, printers...), what each gives, tests, hazards, Ruten prices; the older board-level `salvage_plan` for taking a board apart | Microwaves and swollen batteries are refused |
| 3. Decide | `hs_project_record` with kind decision | A decision needs a choice and a reason |
| 4. Engineer | Sizing and checks: `hs_size_rover_drive`, `hs_size_arm_actuators`, `hs_check_propulsion`, `hs_energy_budget`, `hs_rover_chassis` (printable CAD), `hs_motion_sweep`; boards: `hs_component_board` (KiCad schematic, PCB, fab files), `hs_review_kicad_schematic`, `place_free_footprints` and FreeRouting for layout | A failed check stays open until the same check passes |
| 5. Cost | `hs_price_parts` (JLCPCB), `hs_bom_check` | Every bought line cites a shop page; every salvaged line names its donor; a list with no salvaged part stays open until the reason is given; budget overruns are flagged |
| 6. Package | `hs_project_write_artifact`: guides, firmware, wiring, self-tests | Files are deliverables, never counted as checks |
| 7. Verify | `hs_project_status` separates software-checked, open, physical-required | Nothing here grants fabrication or release; a software check is never physical proof |

Any agent can drive this: the tools are on HS's MCP server and REST API (`/v1/toolbelt/<tool>`).

## What keeps HS informed

* **Landscape watch**: a weekly job (Mondays 09:00) collects new hardware-AI tools, open-hardware sites and projects,
  and established top-starred projects by topic (salvage, robot vacuums, hoverboards, smartphone robots, rovers, arms,
  drones, KiCad...) into `~/.local/share/hs-landscape/register.json` (309 items), which the prior-art search reads.
* **Operating rules** in `CLAUDE.md` and the Mission Freeze amendment (salvage first), and the agent's memory.

## Where things stand

| Project | Done in software | Not done |
|---|---|---|
| HS-BUS-A (USB to servo-bus board) | Schematic, layout, rule checks, fab files; JLCPCB quote US$97-106 for 5 assembled | Not ordered, built or tested |
| HS-ROVER-A (all new parts) | Sized, chassis CAD, quoted: US$263, over budget | Loses to a US$30-50 pet robot; kept as the counter-example |
| HS-ROVER-SALVAGE-A (phone + toy car) | Parts NT$574-822 (under NT$200 new), build guide, OpenBot path, fallback firmware and Wi-Fi self-test tested against a simulated rover | Nothing bought or built |
| RealPCB pilot (one production board) | Placed and routed by HS: every layout-quality check passed | 11 of 251 connections left open: router does not finish |

**Nothing has been physically built yet.** That is the largest gap: real hours, real failure rates and grams of junk
reused only come from a build.

## Known gaps

1. A physical build (the owner's hands, or someone's) with the self-test and a video as evidence.
2. Router: FreeRouting ignores its pass limit and HS discards work on timeout; no step closes the last connections.
3. The placer is a helper script, not yet a toolbelt tool.
4. Shops cannot be searched by the tools (Shopee blocks scripts); finished products need a web search.
5. The drone and arm objectives have not been run through the toolbelt.
6. All of this is on the local branch `agent/propulsion-energy-sizing`, not on `main`.
