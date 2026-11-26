# Hardware-Splicer — working notes for agents

**Read first for project direction:** [`docs/HARDWARE_SPLICER_MISSION_FREEZE.md`](docs/HARDWARE_SPLICER_MISSION_FREEZE.md). This is the canonical strategic scope and work-selection contract; do not replace user engineering outcomes with synthetic benchmarks, reference-kit duplication or demo builds. Existing engineering authority/safety contracts still apply.

Orientation: [`docs/GITHUB_START_HERE.md`](docs/GITHUB_START_HERE.md).
Setup: [`docs/SETUP.md`](docs/SETUP.md) · Tests: [`docs/TESTING.md`](docs/TESTING.md) ·
API/MCP: [`docs/AGENT_QUICKSTART.md`](docs/AGENT_QUICKSTART.md).

This file holds only what those don't cover.

## The one rule that matters

**Authority is never implicitly upgraded.**

Importing, seeding, composing, diffing, and reviewing all *report* state — none
of them promote an engineering claim. A functional analogy never inherits an
electrical contract. Release assessment reports blockers; it does not mark a
project build-ready.

Tests enforce this. If a change makes something pass that previously required
evidence, that is a bug, not progress.

Both architecture docs end in a numbered invariants list — read the relevant one
before editing engine or API code:

| Doc | Covers |
|-----|--------|
| [`docs/MACHINE_PROJECT_SPINE.md`](docs/MACHINE_PROJECT_SPINE.md) | Canonical project model, durable revisions, staged review |
| [`docs/INTEGRATION_STACK.md`](docs/INTEGRATION_STACK.md) | Evidence-first boundary to external tools, donor virtual modules |

## Know what HS already has

HS has 600+ modules; do not read them, the area pages or the 130 docs to find something. Search first:

```bash
PYTHONPATH=src python -m hardware_splicer.capability_map find <words>   # matches with status, reach and tests
PYTHONPATH=src python -m hardware_splicer.capability_map show <module>  # importers, imports, tests of one module
```

(the `hs_capability_search` tool does the same over MCP/REST). Then read `docs/CAPABILITY_MAP.md` (generated, ~120
lines) and `docs/CAPABILITY_CONSOLIDATION.md` (which module is canonical for each job). New agent tools go in
`engineering_toolbelt` as thin adapters over existing modules. After adding or deleting a module, regenerate with
`python -m hardware_splicer.capability_map`; `tests/test_capability_map.py` fails until you do. On 2026-11-26 an agent
rebuilt pieces of `machine_project`, `sdk` and `device_lab` and called FEM, thermal review and arm kinematics missing
because it never looked.

## Salvage first: HS turns junk into working hardware

This is the core of HS and the basis of its business and grant case (owner, 2026-11-26). For every objective, try
strategies in this order and record the reason each earlier one was dropped:

1. **Salvage or adapt** what people already throw away: old phones (camera, Wi-Fi, battery, compute), broken toys and
   RC cars (motors, gearboxes, wheels), dead laptops, routers, power tools, printers, chargers.
2. **Buy** a finished or used product when one does the job for less than salvage would (check Shopee, AliExpress,
   Amazon and Banggood, not only open hardware: a US$30 pet robot beat the new-parts rover).
3. **Build new** only for what neither covers.

`hs_bom_check` enforces this: lines carry `origin` (new, used, salvaged), a salvaged line names its donor, the result
reports new spend, mass diverted and the new-part value replaced, and a list with no salvaged part stays open until
`salvage_rejected_because` says why. Never force a donor where it makes the result unsafe or unworkable (a swollen
battery, an unknown motor on a load path); say so and buy instead. Labour per unit, not materials, decides whether a
salvage design pays, so record hours as well as cost.

## Reuse before you build

Before HS designs a board, mechanism or tool, search for one that already exists: BoardRepo (https://boardrepo.com,
searchable by part; `https://boardrepo.com/{handle}/{slug}.md` reads any public board without an account), Kitspace,
kicad.org/made-with-kicad, `gh search code "<part> extension:kicad_sch"`, and established open-source tools (atopile,
SKiDL, tscircuit, FreeRouting, KiBot). Name what exists and its license, adopt it (MIT, Apache, BSD and CC BY with
attribution; GPL/AGPL only as separate programs, never copied in), run HS's checks on it, and build only what is missing.
A published board is a starting point, not evidence that it was built or works.

## Gotchas

`src/` is not installed — run Python directly with `PYTHONPATH=src`. Makefile
targets resolve `$(PYTHON)` to `.venv/bin/python` on their own and need no
prefix.

The full Python suite took 31.5 minutes serially on 2026-11-26 (7,106 tests). While iterating, prefer the focused
test lists at the end of each architecture doc.

Scratch output defaults to `.cache/hardware-splicer/` (see `HARDWARE_SPLICER_TMP_ROOT`
in `docs/TESTING.md`); some splice verifications write to `/tmp/hs_*` instead.

A KiCad DRC failure that reproduces **only in CI** is usually an environment gap,
not a serializer bug. CI pins the `kicad-9.0-releases` PPA and asserts `--format`
support on `pcb drc` and `sch erc`.

## Commit conventions

Imperative mood, capitalized, no prefix, no trailing period, **one concern per
commit**. The history is deliberately fine-grained — match it.

```text
Add staged project revision review store
Test high-risk machine diff review flags
Assert stable revision conflict error contract
```

Author identity is set **repo-locally** to the maintainer's student account,
which differs from their personal account email. Don't "fix" it.

Feature work goes on `agent/<topic>` branches merged to `main`. Several remote
`agent/*` branches are already merged or squash-landed — check before assuming
one is live:

```bash
git branch -r --merged origin/main
git diff --shortstat origin/main..origin/agent/<topic>   # mostly deletions ⇒ already landed
```

## What is tracked, and what is not

Generated run artifacts are gitignored: `out/`, `artifacts/`, `data/`,
`.cache/`, `/tmp/hs_*`.

Durable evidence **is** tracked on purpose — dated captures under
`review-ui/<slug>-<date>/` and logs under `docs/status/generated/`. Follow the
existing naming when adding more.
