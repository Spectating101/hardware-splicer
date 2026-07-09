# Dry-run issue guide (cold-internal + external)

**Purpose:** How operators file blockers from [`AGENT_DRY_RUN_CHECKLIST.md`](AGENT_DRY_RUN_CHECKLIST.md) without maintainer hand-holding.

**Cold-internal counts:** A maintainer on FGEDHGV / a fresh archive who follows only public docs is the default proof path until strangers are available. Same issue template; title prefix `[Cold-run]` or `[Dry-run]`.

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

**Alien shortcut (maintainers):** `bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.16`  
**With Qwen + live vision:** `HS_ALIEN_QWEN=1 bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.16`

**After a green cold-run:** copy [`INSTALL_REPORT_TEMPLATE.md`](INSTALL_REPORT_TEMPLATE.md) → `docs/install_reports/INSTALL_REPORT_<hostname>_<date>.md` (or attach to the issue) so the bar is auditable without strangers.
