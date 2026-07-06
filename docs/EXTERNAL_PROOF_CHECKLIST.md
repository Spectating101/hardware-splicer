# External proof checklist — after internal maturity

**When to use:** Tier I–III green (`make verify-product-internal` on dev-linux + one alien report). **Stop internal hardening**; run this list.

**Goal:** Controlled external proof — not mass marketing.

---

## Phase 0 — Final internal sanity (you, 30 min)

- [ ] GitHub Actions **Splice Agent v1 bar** green on latest `main`  
  https://github.com/Spectating101/hardware-splicer/actions
- [ ] Optional: fresh `git clone` + `make verify-product-internal` on non-dev machine
- [ ] Tag matches surfaces: `/health`, OpenAPI, `pyproject.toml`

---

## Phase 1 — Conversion kit (ship once)

| # | Item | Location / command |
|---|------|-------------------|
| 1 | **GitHub Release** | Tag `v1.0.2` + `RELEASE_NOTES_v1.0.2.md` |
| 2 | **Sample zip** | `releases/sample-splice-sprint-robot-repair-cafe.zip` |
| 3 | **Entry doc for strangers** | `docs/GITHUB_START_HERE.md` |
| 4 | **5-min demo script** | `docs/DEMO_5_MIN_UI.md` |
| 5 | **Pilot offer** | `docs/OFFER_SPLICE_BENCH_KIT_v1.md` |

---

## Phase 2 — Five conversations (not a blast)

Target profiles (pick 5):

1. Repair café / makerspace lead  
2. University lab manager (EE / mechatronics)  
3. Small hardware team doing salvage / donor builds  
4. Contract EE shop / design house  
5. Accelerator or grant mentor with hardware portfolio  

**One-liner:**

> Self-hosted Splice Agent: donor intake → KiCad carrier with DRC truth → bench gates before power-on. Full internal verify on Linux and lab WSL. Looking for one **Splice Sprint** pilot, not SaaS.

**Send:**

- Link to `GITHUB_START_HERE.md`
- Sample zip (or GitHub Release asset)
- Offer one-pager (`OFFER_SPLICE_BENCH_KIT_v1.md`)

**Ask:**

> Would a 1–2 hour intake + splice build + gate walkthrough be useful on your next donor project?

---

## Phase 3 — Learnings (after 5)

| Outcome | Next |
|---------|------|
| 1+ pilot interest | Schedule Splice Sprint; use `INSTALL_REPORT_TEMPLATE` on their machine |
| “Need native Windows” | WSL2 doc path; defer native installer |
| “Need Flux-class editor” | Out of scope v1; gates + compile honesty positioning |
| No fit | Stop outreach; refine offer from objections |

---

## Do not do yet

- Public SaaS / billing  
- Grant applications without a partner letter  
- More competitor strategy docs  
- Fleet-wide cluster Splice installs  
- GDELT / data-lab work mixed into Splice launch  

---

## Definition of external proof started

You can say **external proof phase begun** when:

1. GitHub Release `v1.0.2` is live with sample zip  
2. At least **one** conversation happened with materials above  
3. CI green on release tag  

Not required: paid pilot closed, demo video (helpful but optional for first week).
