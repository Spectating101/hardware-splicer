# Hardware-Splicer — working notes for agents

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

## Gotchas

`src/` is not installed — run Python directly with `PYTHONPATH=src`. Makefile
targets resolve `$(PYTHON)` to `.venv/bin/python` on their own and need no
prefix.

The full Python suite takes ~6.5 minutes. While iterating, prefer the focused
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
