# External dry-run issue guide

**Purpose:** How external operators file blockers from [`AGENT_DRY_RUN_CHECKLIST.md`](AGENT_DRY_RUN_CHECKLIST.md) without maintainer hand-holding.

---

## When to file

File a GitHub issue **only if** you completed the checklist through the failing step using public docs and could not proceed.

Do **not** file for:

- `copper_tier: cosmetic_preview` with **0 KiCad DRC errors**
- Missing `QWEN_API_KEY` on optional curl 3 (skip it)
- Port 8787 already in use (pick another port or stop the old API)

---

## How to file

1. Open **Issues → New issue → External dry-run blocker**
2. Title: `[Dry-run] <short failure>` e.g. `[Dry-run] catalog count 27 on alpha.8`
3. Paste:
   - Tag tested (`git describe --tags` or commit SHA)
   - Failing checklist step number
   - Exact command + output (curl, install log, pytest)
   - `hs-doctor` output
   - OS + KiCad + Python + Node versions

---

## Maintainer triage

| Symptom | Likely action |
|---------|----------------|
| Old tag / stale API | Point to latest alpha; restart API from fresh clone |
| Catalog < 50 | Upgrade to `main` or latest tag |
| `out_dir` validation | Set `HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1` for local MCP |
| Clone hang on WSL | `git archive` + `scp` per FGEDHGV install report |
| Salvage step wrong mode | Ensure `donor_context` + `salvage_mode`; check tag ≥ alpha.8 |
| Bench loop not authorized | Expected until capture submitted; use `simulate_bench: true` for CI path |

---

## Optional proof artifact

Copy [`INSTALL_REPORT_TEMPLATE.md`](INSTALL_REPORT_TEMPLATE.md) → `INSTALL_REPORT_<hostname>_<date>.md` in your fork or attach to the issue.

**Alien shortcut (maintainers):** `bash scripts/deploy_alien_quickstart.sh <tag>`
