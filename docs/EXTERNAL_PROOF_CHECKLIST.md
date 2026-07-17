# External proof checklist — v1.1.0-alpha.16

**When to use:** After cold-internal exit; converting to pilot outreach.  
**Goal:** Controlled launch + pilot pull — not mass marketing.  
**Related:** [`COLD_INTERNAL_EXIT.md`](COLD_INTERNAL_EXIT.md) · [`PROOF_PACK_CONTENTS.md`](PROOF_PACK_CONTENTS.md) · [`LAUNCH_v1.1.md`](LAUNCH_v1.1.md)

**Publicity note (2026-07-18):** GitHub repo is **private**. Phase 0 “public prerelease” is **blocked** until founder chooses stance A (open-core) or shares private release links under NDA. Stance **B** (proof pack only) can proceed without making the repo public.

---

## Phase 0 — Release candidate

- [x] Cold-internal exit on `v1.1.0-alpha.16` ([`COLD_INTERNAL_EXIT.md`](COLD_INTERNAL_EXIT.md))
- [x] Two-machine install reports (optiplex + FGEDHGV) under `docs/install_reports/`
- [x] `make doctor` green on progression machine (2026-07-18)
- [x] `make verify-product-v1` green on progression machine (2026-07-18) — log `docs/status/generated/verify-product-v1-2026-07-18.log`
- [x] `verify-install-smoke` + `verify-product-live-smoke` green (2026-07-18) — log `docs/status/generated/verify-smoke-2026-07-18.log`
- [ ] GitHub **prerelease** for `v1.1.0-alpha.16` *(blocked if repo stays private without invitees)*
- [ ] CI green on tagged commit *(check Actions when publishing)*

---

## Phase 1 — Conversion kit (stance B can complete)

| # | Item | Location | Status |
|---|------|----------|--------|
| 1 | Entry doc | [`GITHUB_START_HERE.md`](GITHUB_START_HERE.md) | Exists — keep honest about private/status |
| 2 | Sample zip | `releases/sample-splice-sprint-robot-repair-cafe.zip` | Present |
| 3 | 5-min demo | [`DEMO_5_MIN_UI.md`](DEMO_5_MIN_UI.md) | Present |
| 4 | Pilot offer | [`OFFER_SPLICE_BENCH_KIT_v1.md`](OFFER_SPLICE_BENCH_KIT_v1.md) | Present |
| 5 | Before/after | [`COMPARISON_DEMO_CASE_robot_repair_cafe.md`](COMPARISON_DEMO_CASE_robot_repair_cafe.md) | Check exists |
| 6 | Proof pack index | [`PROOF_PACK_CONTENTS.md`](PROOF_PACK_CONTENTS.md) | Added 2026-07-18 |
| 7 | Dry-run guide | [`EXTERNAL_DRY_RUN_ISSUE_GUIDE.md`](EXTERNAL_DRY_RUN_ISSUE_GUIDE.md) | Present |

---

## Phase 2 — Five conversations

**One-liner:**

> Self-hosted bring-up workbench: design verify, BOM, fab readiness, and bench gates before power-on. Looking for prototype/lab pilots — not SaaS.

**Send:** Proof pack (see [`PROOF_PACK_CONTENTS.md`](PROOF_PACK_CONTENTS.md)) — prerelease link only if repo access granted.

**Ask:**

> Would a readiness package on your next prototype reduce chaos before fabrication or power-on?

---

## Phase 3 — Learnings

| Outcome | Next |
|---------|------|
| 1+ “run this on my files” | Splice Sprint pilot |
| “Need Windows native” | WSL2 path |
| “Need Flux editor” | Out of scope; readiness + gates positioning |
| No fit | Refine segment; do not add random features |

---

## Launch started when

1. Proof pack ready to send (Phase 1)  
2. One deploy (`make splice-ui-serve` or systemd)  
3. One demo recorded or delivered live  
4. One external conversation with kit  

---

*Updated 2026-07-18 · progression takeover · alpha.16*
