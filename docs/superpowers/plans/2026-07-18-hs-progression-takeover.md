# Hardware-Splicer Progression Takeover

> **For agentic workers:** Execute task-by-task. Checkboxes track progress.

**Goal:** Advance Hardware-Splicer from cold-internal exit to conversion-ready (external proof kit + honest public/private stance), without expanding S4 mech scope.

**Architecture:** Product spine is done (`COLD_INTERNAL_EXIT.md` alpha.16). Remaining work is proof depth, distribution honesty, and conversion kit — not new glue. Optional Architon gate is an adapter, not a rewrite.

**Tech Stack:** Python 3.12+, KiCad 9+ `kicad-cli`, Node splice-ui, Make verify targets, existing MCP/API.

**Default publicity stance (until founder overrides):** **B — private core + public proof pack** (install reports, offer, sample zip, start-here docs). Do not force full public open-core without explicit ask.

**Out of scope this plan:** Cite-Agent, Mecha/3d S4 SKU, physical café bench (needs hardware on desk), mass marketing.

---

## Current baseline (2026-07-18)

- Git: `main` @ `0cacc1e` **in sync** with `origin/main`
- Cold-internal exit declared; Tier I–III claimed PASS in maturity docs
- Conversion docs exist but checklist still references older `alpha.1` wording
- Repo is **private** on GitHub — capitalization blocked by invisibility unless proof pack is shared deliberately

---

### Task 1: Progression ownership doc + plan

**Files:**
- Create: `docs/superpowers/plans/2026-07-18-hs-progression-takeover.md` (this file)
- Create: `docs/PROGRESSION_STATUS.md`

- [x] **Step 1:** Write this plan
- [ ] **Step 2:** Write living `PROGRESSION_STATUS.md` (owner, next actions, blockers)
- [ ] **Step 3:** Point README / GITHUB_START_HERE at progression status if missing

---

### Task 2: Green-bar baseline on this machine

**Files:** none (commands only); capture log under `docs/status/generated/` if useful

- [ ] **Step 1:** `hs-doctor` or `make doctor`
- [ ] **Step 2:** Run `scripts/agent_quickstart_verify.sh` (or `make verify-product-internal` if quicker subset) and record pass/fail
- [ ] **Step 3:** If fail, fix only regressions that block conversion kit — no feature creep

---

### Task 3: Align external-proof checklist to alpha.16

**Files:**
- Modify: `docs/EXTERNAL_PROOF_CHECKLIST.md`
- Modify: `docs/GITHUB_START_HERE.md` (honest status: private + cold-internal / conversion kit)

- [ ] **Step 1:** Rewrite Phase 0 for current tag `v1.1.0-alpha.16` (or latest describe)
- [ ] **Step 2:** Mark what’s done vs blocked by private GitHub / prerelease visibility
- [ ] **Step 3:** List exact artifacts for a shareable proof pack (zip + offer + reports)

---

### Task 4: Conversion kit harden (no outreach spam)

**Files:**
- Modify: `docs/OFFER_SPLICE_BENCH_KIT_v1.md` if pricing/honesty stale
- Verify: `releases/sample-splice-sprint-robot-repair-cafe.zip` exists
- Create or update: `docs/PROOF_PACK_CONTENTS.md` (what to send a pilot)

- [ ] **Step 1:** Inventory conversion kit files; fix broken links
- [ ] **Step 2:** Write one-page proof-pack contents for pilot outreach
- [ ] **Step 3:** Dry-run the install path from `QUICKSTART` / alien script docs (doc-only if env heavy)

---

### Task 5: Optional Architon compose spike

**Files:**
- Create: `docs/integrations/ARCHITON_GATE.md` (how to run `rv` after compose)
- Optional later: `scripts/optional_architon_gate.sh`

- [ ] **Step 1:** Document install + where HS emits KiCad/netlist/BOM for `rv scan`
- [ ] **Step 2:** If Architon CLI available, run once on a golden package and record result
- [ ] **Step 3:** Stop — no hard dependency in default install

---

### Task 6: Checkpoint with founder

- [ ] **Step 1:** Report baseline verify result + proof-pack readiness
- [ ] **Step 2:** Ask: public open-core (A) vs proof-pack only (B) vs stay silent (C)
- [ ] **Step 3:** Only then: GitHub prerelease / visibility changes

---

## Success criteria

1. Living progression status doc exists and is accurate
2. Verify bar result known on this machine
3. External proof checklist matches alpha.16 reality
4. Proof pack can be handed to one pilot conversation without apologizing for missing files
5. Architon documented as optional compose path
