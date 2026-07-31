# Consolidation audit — 2026-07-31

Record of a repo-state audit. Written so a fresh agent or contributor does not
re-derive it. Point-in-time: accurate as of `f9e5f93`.

## Verdict

The repo is healthy and self-contained. Everything the project needs is tracked
and pushed.

| Check | Result |
|-------|--------|
| Python suite | 737 passed, 4 skipped, 0 failed (~6.5 min) |
| `verify-money-paths` | 8/8 PASS |
| `verify-splice-real-bench` | PASS |
| `verify-physical-closed-loop` | 1/1 PASS (software-ready) |
| Working tree | clean |
| Unpushed work | none, on any branch |

## Monorepo consolidation is complete

`apps/circuit-ai` and `apps/3d-splicer` were folded in from standalone repos
(see [`GIT_MIGRATION.md`](GIT_MIGRATION.md)). That consolidation was verified,
not assumed:

- The final state of each standalone repo is **fully present** in this repo.
  Circuit-AI: 1,166 files at the migration tip, all present among the 1,438
  tracked today.
- The only file in a backup tip and absent here is `.claude/settings.local.json`,
  which is deliberately gitignored.
- Every other path in the old history was **already deleted before** the
  migration snapshot — superseded intermediate states, not dropped work.

**Nothing is missing from this repo.** Pre-migration nested `.git` directories
are kept locally by the maintainer and are intentionally not published; they
contain no code this repo lacks.

## Documentation state

`DOCUMENTATION_INDEX.md` had drifted three weeks and omitted 18 of 77 top-level
docs, including every current-era one. It now lists all of them, and its
precedence rule was reordered so architecture and living status outrank the
dated handoff docs.

Treat these as **record, not current truth** — they describe the repo on the day
they were written: `HANDOFF_UPDATE.md`, `AGENT_HANDOFF.md`,
`FUNCTIONAL_ASSESSMENT_*`, `install_reports/`.

## Resolved, do not re-investigate

- **Real-bench golden fixture** — was failing on an obsolete fixture expecting
  `power_on_authorized` immediately from manual capture. Migrated to the
  two-stage contract sequence; now PASS.
- **Catalog-engine KiCad failure** — was CI-environment-specific, not a
  serializer bug. CI now pins the `kicad-9.0-releases` PPA and asserts
  `--format` support on `pcb drc` and `sch erc`. Local evidence in
  `review-ui/evidence-first-local-2026-07-20/DIAGNOSIS.md`.

## Found and fixed: BOM undercounted repeated parts

`build_salvage_bom_estimate` de-duplicated by `module_id` and emitted every line
at the default `qty` of 1, so any design needing more than one of a part
understated it. Four of the eight money paths were affected; `printer_plotter`
listed one limit switch where the graph needs five, and could not be assembled
from its own BOM.

Fixed in `c861b87`, tests in `f9e5f93`.

Worth noting how it survived: `qty` was plumbed correctly through pricing the
whole time — `_line_for_module` computed `unit × qty` properly. Only the caller
never counted. Every existing test asserted on prices and totals, which were
self-consistently wrong.

**This bug class is invisible to the authority doctrine.** Nothing overstated
authority; a *count* was understated, and a BOM quantity is not a claim. A gate
cross-checking BOM quantities against build-graph instance counts would close
the gap.

## Open

- **Physical bench loop.** `PHYSICAL_BENCH_EVIDENCE.json` remains
  `pending_operator`. The pack builds clean and pin-consistent
  (`PAN_PIN=18`/`TILT_PIN=16` agree across firmware, wiring guide, and evidence
  template), but no board has been through print → wire → flash → power-on.
  Everything currently green is software verifying software. Design-partner
  invites stay paused until this closes — see
  [`PROGRESSION_STATUS.md`](PROGRESSION_STATUS.md).
  Bench needs **2× SG90** (the BOM said 1 before the fix above).
- **Unmerged agent branches.** Several `agent/*` remotes carry work not in
  `main`, the largest ~5,500 insertions across 64 files. Check before assuming
  one is live:
  ```bash
  git branch -r --merged origin/main
  git diff --shortstat origin/main..origin/agent/<topic>   # mostly deletions ⇒ already landed
  ```
- **Cosmetic.** Two deprecation warnings (`httpx2`,
  `HTTP_422_UNPROCESSABLE_CONTENT`); ~14 pre-existing broken links inside
  `apps/circuit-ai` docs (legacy standalone app).
