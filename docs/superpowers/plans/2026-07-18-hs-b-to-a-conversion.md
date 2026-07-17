# Hardware-Splicer B→A Conversion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Hardware-Splicer from cold-internal readiness into paid/pilot conversion under **stance B** (private + proof pack), then upgrade to **stance A** (public open-core) when a real signal hits or after a 2-week timer.

**Architecture:** Do not expand the product spine. Ship a repeatable proof pack and outreach loop first; only then add LICENSE + public visibility + prerelease. Architon remains optional compose, not a release blocker.

**Tech Stack:** Existing HS Make/Python/KiCad stack; GitHub private→public; tar proof pack; Bench Kit offer docs.

**Decision locked (2026-07-18):** B now → A on trigger. Not C.

---

## File map

| File | Responsibility |
|------|----------------|
| `docs/PROOF_PACK_CONTENTS.md` | What goes in the pack (exists) |
| `docs/PROGRESSION_STATUS.md` | Living owner/status |
| `docs/EXTERNAL_PROOF_CHECKLIST.md` | Phase gates |
| `docs/OFFER_SPLICE_BENCH_KIT_v1.md` | Pilot commercial offer |
| `docs/outreach/PILOT_OUTREACH_NOTES.md` | *(create)* one-liners + log of conversations |
| `/tmp` or `releases/proof-packs/` | Built tarball artifacts |
| `LICENSE` | *(create before A)* root license |
| `SECURITY.md` / harden `README.md` | *(before A)* public honesty |
| GitHub prerelease `v1.1.0-alpha.16` | *(A phase)* |

---

## Phase B — Private conversion (Week 0–2)

### Task 1: Lock status docs to B→A

**Files:**
- Modify: `docs/PROGRESSION_STATUS.md`
- Modify: `docs/EXTERNAL_PROOF_CHECKLIST.md` (note B→A decision)

- [ ] **Step 1:** Set publicity to **B active / A scheduled**
- [ ] **Step 2:** Record A triggers: (1) one “run on my files” reply, OR (2) 14 days after B pack first sent, OR (3) founder override
- [ ] **Step 3:** Commit progression docs only when founder asks (or batch at end of Task 3)

---

### Task 2: Build the proof-pack tarball

**Files:**
- Use: `docs/PROOF_PACK_CONTENTS.md` bundle command
- Create: `releases/proof-packs/hs-proof-pack-alpha16-YYYYMMDD.tgz` (or `/tmp` then copy)

- [ ] **Step 1:** Run bundle from repo root (copy offer, demo, cold exit, release notes, sample zip, alpha16 install reports)
- [ ] **Step 2:** Verify archive lists expected files: `tar tzf … | head`
- [ ] **Step 3:** Note SHA256 of tarball in `docs/PROGRESSION_STATUS.md` log
- [ ] **Step 4:** Fill offer **Contact** line in `OFFER_SPLICE_BENCH_KIT_v1.md` with founder email (ask if missing)

---

### Task 3: Outreach kit (5 conversations, no spam)

**Files:**
- Create: `docs/outreach/PILOT_OUTREACH_NOTES.md`

- [ ] **Step 1:** Write 3 one-liner variants (lab / repair-café / EMS-adjacent prototype)
- [ ] **Step 2:** Write short email/DM body: attach proof pack + ask the readiness question from checklist
- [ ] **Step 3:** Create tracking table: date / who / channel / outcome / next
- [ ] **Step 4:** Founder (or agent with approval) sends **first** message — target 5 over 14 days, not blast

**Success for Phase B:** ≥1 conversation started with pack attached. Ideal: ≥1 “send me access / run on my files.”

---

### Task 4: Demo readiness (local)

**Files:** none required beyond existing demo docs

- [ ] **Step 1:** `make splice-ui-serve` (or documented port) smoke — UI loads
- [ ] **Step 2:** Walk `docs/DEMO_5_MIN_UI.md` once; fix only broken steps in that doc
- [ ] **Step 3:** Optional 3–5 min screen recording saved outside git or under `docs/status/generated/` (gitignored if large)

---

### Task 5: Phase B checkpoint

- [ ] **Step 1:** Update `PROGRESSION_STATUS.md`: pack SHA, outreach count, demo OK/fail
- [ ] **Step 2:** If any A trigger met → proceed Phase A
- [ ] **Step 3:** If no replies after 14 days → still proceed Phase A (visibility was the missing ingredient), unless founder chooses stay-B

---

## Phase A — Public open-core upgrade (after trigger)

### Task 6: License + public honesty

**Files:**
- Create: `LICENSE` (recommend **MIT** for broad pilot adoption; AGPL only if founder wants copyleft like Architon)
- Modify: `README.md` — cold-exit honesty, link proof pack / offer, no SaaS claims
- Create or verify: `SECURITY.md` (or point to existing)

- [ ] **Step 1:** Confirm license choice with founder (default MIT if no reply in 48h during A kickoff)
- [ ] **Step 2:** Add root `LICENSE`
- [ ] **Step 3:** README: Status = cold-internal + seeking pilots; link `COLD_INTERNAL_EXIT.md`, `PROOF_PACK_CONTENTS.md`
- [ ] **Step 4:** `make doctor` still green

---

### Task 7: Make repo public + prerelease

**Files / GitHub:**
- GitHub settings: visibility public
- Release: tag already exists `v1.1.0-alpha.16` — publish **prerelease** with notes + attach proof-pack tarball + sample zip

- [ ] **Step 1:** Push any pending doc commits to `origin/main`
- [ ] **Step 2:** Set repository visibility to public
- [ ] **Step 3:** `gh release create v1.1.0-alpha.16 --prerelease …` with assets
- [ ] **Step 4:** Confirm Actions CI green on tag/main
- [ ] **Step 5:** Update `GITHUB_START_HERE.md` — remove “may be private” caveat

---

### Task 8: Post-A conversion loop

- [ ] **Step 1:** Replace outreach links with public prerelease URL
- [ ] **Step 2:** Add GitHub Sponsors or “pilot inquiry” contact in README (optional)
- [ ] **Step 3:** Log first public issue/dry-run if any; triage via `EXTERNAL_DRY_RUN_ISSUE_GUIDE.md`
- [ ] **Step 4:** Optional Architon: install `rv`, add `scripts/optional_architon_gate.sh` only if a pilot asks for contract scan

---

## Explicit non-goals

- Mecha / 3d S4 SKU work
- Cite-Agent coupling
- Physical café measurement until board on desk
- Competing as “another KiCad MCP” on PyPI
- Mass marketing / ads

---

## Timeline (suggested)

| Day | Focus |
|-----|--------|
| 0 | Tasks 1–2: lock docs, build tarball, fill contact |
| 1–3 | Tasks 3–4: outreach notes + demo walk |
| 1–14 | Send up to 5 conversations; log outcomes |
| Trigger or Day 14 | Tasks 6–7: LICENSE + public + prerelease |
| After A | Task 8: public links + Sponsors/pilot CTA |

---

## Success criteria

**Phase B done when:** proof-pack tarball exists with SHA logged; outreach notes ready; ≥1 outbound conversation attempted.

**Phase A done when:** public repo + LICENSE + prerelease with assets; start-here docs honest; CI not red.

**Conversion win:** one scheduled Splice Sprint / Bench Kit intake (paid or clearly scoped pilot).
