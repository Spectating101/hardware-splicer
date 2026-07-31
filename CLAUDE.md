# Hardware-Splicer — working notes for agents

Read [`docs/GITHUB_START_HERE.md`](docs/GITHUB_START_HERE.md) first. This file
covers only conventions that are easy to get wrong.

## The one rule that matters

**Authority is never implicitly upgraded.**

Importing, seeding, composing, diffing, and reviewing all *report* state — none
of them promote an engineering claim. A functional analogy never inherits an
electrical contract. Release assessment reports blockers; it does not mark a
project build-ready. Tests enforce this, so a change that quietly promotes a
claim will fail rather than silently ship.

If a change makes something pass that previously required evidence, that is a
bug, not progress.

Architecture: [`docs/MACHINE_PROJECT_SPINE.md`](docs/MACHINE_PROJECT_SPINE.md)
(project model, revisions, review) and
[`docs/INTEGRATION_STACK.md`](docs/INTEGRATION_STACK.md) (external-tool
boundary). Both end in a numbered invariants list — check it before editing
engine or API code.

## Environment

Python lives in `.venv`, and `src/` is not installed — set `PYTHONPATH`:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/
```

The Makefile resolves `$(PYTHON)` to `.venv/bin/python` automatically, so `make`
targets need no prefix. Requires Python 3.12+, KiCad 9+ (`kicad-cli`), Node 18+.

`make doctor` checks the toolchain.

## Verification ladder

Cheapest first — don't run the whole bar for a small change.

| Command | Scope |
|---------|-------|
| `PYTHONPATH=src .venv/bin/python -m pytest -q tests/` | Python suite |
| `make splice-ui-build` | Frontend tests + Vite production build |
| `make verify-splice-v1` | Core v1 bar (no npm, no splice-ui) |
| `make verify-product-v1` | Core bar + UI build + product API tests |
| `make verify-product-internal` | Everything, including install and live smoke |

The full suite is slow (several minutes). Prefer the focused test lists in the
architecture docs while iterating.

Some verifications need KiCad and write reports under `/tmp/hs_*`. CI installs
KiCad from the `kicad-9.0-releases` PPA and asserts `--format` support on both
`pcb drc` and `sch erc` — a DRC failure that reproduces only in CI is usually an
environment gap, not a serializer bug.

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

Feature work goes on `agent/<topic>` branches, merged to `main`. Some remote
`agent/*` branches are already merged and awaiting pruning — confirm with
`git branch -r --merged origin/main` before assuming a branch is live.

## Generated output

`out/`, `artifacts/`, `data/`, and `/tmp/hs_*` hold generated run artifacts and
are gitignored. Don't commit them.

Durable evidence is different: dated captures under `review-ui/<slug>-<date>/`
and logs under `docs/status/generated/` **are** tracked on purpose. Follow the
existing naming when adding more.
