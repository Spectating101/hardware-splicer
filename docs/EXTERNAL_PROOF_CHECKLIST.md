# External proof checklist — v1.1 launch

**When to use:** `v1.1.0-alpha.1` tagged; `make verify-product-v1` green.

**Goal:** Controlled launch + pilot pull — not mass marketing.

**Launch runbook:** [`LAUNCH_v1.1.md`](LAUNCH_v1.1.md)

---

## Phase 0 — Release candidate (done when checked)

- [x] `v1.1.0-alpha.1` tag on `main`
- [ ] GitHub **prerelease** published with `RELEASE_NOTES_v1.1.0-alpha.1.md`
- [ ] CI green on tag commit
- [ ] `make verify-product-v1` on release machine

---

## Phase 1 — Conversion kit

| # | Item | Location |
|---|------|----------|
| 1 | **GitHub prerelease** | `v1.1.0-alpha.1` |
| 2 | **Sample zip** | `releases/sample-splice-sprint-robot-repair-cafe.zip` (v1.0.2 gates story) |
| 3 | **Entry doc** | `docs/GITHUB_START_HERE.md` |
| 4 | **5-min demo** | `docs/DEMO_5_MIN_UI.md` |
| 5 | **Pilot offer** | `docs/OFFER_SPLICE_BENCH_KIT_v1.md` |
| 6 | **Before/after** | `docs/COMPARISON_DEMO_CASE_robot_repair_cafe.md` |

---

## Phase 2 — Five conversations

**One-liner:**

> Self-hosted bring-up workbench: design verify, BOM, fab readiness, and bench gates before power-on. Looking for prototype/lab pilots — not SaaS.

**Send:** GitHub prerelease link + sample zip + offer doc.

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

1. Prerelease live  
2. One deploy (`make splice-ui-serve` or systemd)  
3. One demo recorded or delivered live  
4. One external conversation with kit  

---

*Updated July 2026 · v1.1 interface preview*
