# Visual audit — workspace polish (baseline `1368866`)

**Viewport:** ~1440×900  
**Artifacts:** `before/` captured against served UI at `1368866` before polish; `after/` after this pass.

## Findings (before)

| ID | Finding | Screenshot |
|----|---------|------------|
| H1 | Home hierarchy is dense; primary CTA is clear but secondary copy still agent-jargon heavy | `before/01-home.png` |
| H2 | Intake embeds wizard but project header was generic (“Project workspace”) with little stage/status identity | `before/02-intake-goal.png` |
| H3 | Stage tabs all looked equally available even when Verify/Bench/Package had no build | `before/06-verify.png` |
| H4 | After Studio compile, CTA said “Open full project” — implies leaving the app | (Studio DRC panel copy) |
| H5 | Copper honesty used raw `cosmetic_preview` / `agent_loop.copper_tier` jargon | Verify/Studio panels |
| H6 | Bench did not always label simulated vs physical evidence at the stage level | `before/07-bench.png` |
| H7 | Advanced hub is correctly secondary; Interface Lab remains dense adapter UI | `before/09-advanced.png`, `before/10-interface-lab.png` |
| H8 | Next action after each stage was implicit (tabs only), not a single dominant CTA | all workspace shots |

## Changes implemented

1. Stage availability: Verify/Bench/Package disabled until build/package evidence exists.
2. Stable `ProjectStatusHeader` with mode, stage, DRC, copper honesty, bench, evidence chips.
3. Dominant `Next` action bar per stage.
4. Studio CTA → **Continue to Verify**; softer honesty copy.
5. Copper / compile labels use “preview / not fab-ready” language.
6. Bench evidence banner for simulated vs physical.

## Remaining legibility gaps

- Design canvas still empty until modules are placed (expected).
- ReadinessHero + SummaryBar can still duplicate status chips after package exists.
- Advanced / Interface Lab not visually redesigned (intentionally deferred).
- No persistence across refresh (honest “in-memory session” label).
