# Proof pack contents — what to send a pilot

**Purpose:** One folder/email of artifacts for a Splice Bench Kit conversation without requiring a public GitHub browse.

**Tag:** Prefer `v1.1.0-alpha.16` (or newer cold-exit tag).  
**Stance:** Works with **private** repo (share zip + docs) or public prerelease later.

---

## Always include

| # | Artifact | Path |
|---|----------|------|
| 1 | One-liner + offer | [`OFFER_SPLICE_BENCH_KIT_v1.md`](OFFER_SPLICE_BENCH_KIT_v1.md) |
| 2 | What shipped | [`../RELEASE_NOTES_v1.1.0.md`](../RELEASE_NOTES_v1.1.0.md) + [`RELEASE_v1.1.md`](RELEASE_v1.1.md) |
| 3 | Demo script | [`DEMO_5_MIN_UI.md`](DEMO_5_MIN_UI.md) |
| 4 | Sample sprint zip | `releases/sample-splice-sprint-robot-repair-cafe.zip` |
| 5 | Honesty / cold exit | [`COLD_INTERNAL_EXIT.md`](COLD_INTERNAL_EXIT.md) (what is / isn’t claimed) |
| 6 | Liability | [`SUPPORT_AND_LIABILITY_v1.md`](SUPPORT_AND_LIABILITY_v1.md) |

## Strongly recommended

| # | Artifact | Path |
|---|----------|------|
| 7 | Install evidence | `install_reports/INSTALL_REPORT_optiplex_cold_2026-07-10_alpha16.md` |
| 8 | Second-machine evidence | `install_reports/INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-10_alpha16.md` |
| 9 | Before/after case | [`COMPARISON_DEMO_CASE_robot_repair_cafe.md`](COMPARISON_DEMO_CASE_robot_repair_cafe.md) |
| 10 | Entry map | [`GITHUB_START_HERE.md`](GITHUB_START_HERE.md) |

## Optional (technical buyers)

| # | Artifact | Path |
|---|----------|------|
| 11 | Agent dry-run | [`AGENT_DRY_RUN_CHECKLIST.md`](AGENT_DRY_RUN_CHECKLIST.md) |
| 12 | OSS compose map | [`OSS_INTEGRATION_STATUS.md`](OSS_INTEGRATION_STATUS.md) |
| 13 | Architon gate (optional) | [`integrations/ARCHITON_GATE.md`](integrations/ARCHITON_GATE.md) |

---

## Bundle command (maintainer)

From repo root:

```bash
mkdir -p /tmp/hs-proof-pack && \
cp docs/OFFER_SPLICE_BENCH_KIT_v1.md \
   docs/DEMO_5_MIN_UI.md \
   docs/COLD_INTERNAL_EXIT.md \
   docs/PROOF_PACK_CONTENTS.md \
   RELEASE_NOTES_v1.1.0.md \
   releases/sample-splice-sprint-robot-repair-cafe.zip \
   /tmp/hs-proof-pack/ && \
cp docs/install_reports/INSTALL_REPORT_*alpha16*.md /tmp/hs-proof-pack/ 2>/dev/null || true && \
(cd /tmp && tar czf hs-proof-pack-alpha16.tgz hs-proof-pack)
```

Send `hs-proof-pack-alpha16.tgz` + calendar link for a 30-minute demo.

---

## Do not claim in outreach

- Public stars / open download if repo is private  
- Fab-ready copper by default  
- Physical café measurement of *their* board until booked  
- UL/CE certification  
