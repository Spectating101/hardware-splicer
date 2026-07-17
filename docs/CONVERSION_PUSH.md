# Hardware-Splicer — Conversion push plan (after B→A)

**Purpose:** What we do *after* the proof pack exists and (when triggered) the repo is public — how we actually get pilots and cash.  
**Depends on:** [`superpowers/plans/2026-07-18-hs-b-to-a-conversion.md`](superpowers/plans/2026-07-18-hs-b-to-a-conversion.md)  
**Offer:** [`OFFER_SPLICE_BENCH_KIT_v1.md`](../OFFER_SPLICE_BENCH_KIT_v1.md)  
**Pack:** [`PROOF_PACK_CONTENTS.md`](../PROOF_PACK_CONTENTS.md)

**Product one-liner (always use):**

> Self-hosted bring-up workbench: KiCad carrier + design verify + BOM/fab readiness + bench gates before power-on. Not a chat-to-PCB toy. Not SaaS.

---

## 1. What “ready to push” means

| Gate | Required |
|------|----------|
| Proof pack tarball | Yes (Phase B) |
| Demo walkable in 5–30 min | Yes |
| Offer + liability language | Yes |
| Public prerelease (Phase A) | Preferred; private pack + invite OK for first 1–2 pilots |
| Physical café board | **No** — book as paid option later |

Until those exist, do not spray outreach.

---

## 2. Who we convert (priority order)

Only three segments. Ignore consumers and “build my startup PCB from a prompt.”

| Priority | Segment | Why they pay | What to send |
|----------|---------|--------------|--------------|
| **1** | **Repair / maker / robot café labs** (TW + remote) | Chaos before power-on; donor parts; need gates | Pack + repair-café comparison case |
| **2** | **Prototype / EMS-adjacent small teams** | One bad fab spin costs more than a Sprint | Pack + cold-exit honesty + Bench Kit price band |
| **3** | **Embedded / robotics labs (uni or indie)** | Bring-up diligence before student/demo power-on | Pack + public repo (after A) + agent dry-run guide |

**Do not prioritize:** VC consumer, Altium shop-ins, “AI PCB generator” crowds, Upwork scraping as primary (optional cash later only).

---

## 3. Conversion funnel (exact)

```text
Aware          →  Proof pack or public prerelease link
Interest       →  30-min DEMO_5_MIN_UI (screen share)
Commit         →  Splice Sprint SOW (OFFER) + deposit if needed
Deliver        →  Intake → PROJECT_PACKAGE → gate review
Expand         →  Second board / site license quote
```

**One metric that matters in 30 days:**  
`conversations_started → demos_held → sprints_booked`  
Target: **5 → 2 → 1**.

---

## 4. How we push (channels)

### Wave 1 — Warm / direct (days 0–14, with pack)

| Channel | Action | Cadence |
|---------|--------|---------|
| Personal network | 5 people who touch hardware / labs | 1–2 msgs/day max |
| Existing TW tech / maker contacts | Same one-liner + pack | Batch of 5 total |
| YZU / lab-adjacent if warm | “Prototype readiness before power-on” | Only if real relationship |

**Script shape:**
1. One-liner  
2. What they get (package + gates)  
3. Ask: *Would a readiness package on your next prototype reduce chaos before fab or power-on?*  
4. Attach pack (or private release link)  
5. Offer 30-min demo slot  

### Wave 2 — Semi-public (after Phase A)

| Channel | Action |
|---------|--------|
| GitHub prerelease + README CTA | “Pilot inquiry” email / form |
| Post once | Relevant Discord/forum/lab Slack *where you already exist* — no spam boards |
| Taiwan ecosystem (later) | Soft-landing / Inception-style programs — **after** 1 pilot proof, not before |

### Wave 3 — Optional cash buffer (not primary)

- Selective Upwork / freelance only if a job is literally “bring-up / donor board / KiCad package” — sell the Sprint, not hourly coding.

### Deliberately weak channels (skip or last)

- Cold LinkedIn blasts  
- Product Hunt-style launches  
- “Another KiCad MCP” PyPI SEO  
- Hackathons as primary conversion  

---

## 5. What we sell (SKU discipline)

| SKU | When | Price anchor (from offer) |
|-----|------|---------------------------|
| **Splice Sprint** (primary) | First conversion | NT$15k–60k / ~$500–2k |
| **Site license** | After 1 good Sprint | Annual quote |
| **On-site café measurement** | Only when board + DMM available | Add-on, not required to close |

Never lead with site license. Never lead with SaaS subscription.

---

## 6. Objection handling (short)

| They say | You say |
|----------|---------|
| “Just use ChatGPT + KiCad” | We don’t invent copper trust — `kicad-cli` DRC + bench gates + package you can defend |
| “Need full ECAD like Altium” | Out of scope — we sell readiness before power-on/fab |
| “Need Windows native” | WSL2 path; same agent |
| “Is it open source?” | After A: yes + license; during B: pack + private access for pilot |
| “Prove it works” | Install reports + sample zip + live 30-min demo |

---

## 7. Operating rhythm (post-pack)

**Weekly (founder or agent+founder):**
- Mon: check outreach log; send ≤3 new touches  
- Wed: demos / follow-ups  
- Fri: update `docs/outreach/PILOT_OUTREACH_NOTES.md` outcomes; refine one-liner if all “no fit”

**Stop rules:**
- After 5 nos with same segment → change segment or one-liner, don’t add features  
- After 1 booked Sprint → pause spray; deliver excellently; ask for referral  

---

## 8. After first Sprint (compound)

1. Redact + add a one-page case note to proof pack v2  
2. Ask for intro to one peer lab  
3. Decide site-license quote  
4. Only then: Taiwan program applications / Sponsors / broader public push  

---

## 9. Success definition (90 days)

| Level | Definition |
|-------|------------|
| **Minimum** | 5 conversations + 2 demos |
| **Good** | 1 Splice Sprint booked or completed |
| **Excellent** | 1 Sprint + 1 referral or site-license discussion |

Capability without this loop ≠ conversion.

---

## 10. Agent vs founder split

| Agent can do | Founder must do |
|--------------|-----------------|
| Pack build, docs, demo env, outreach drafts, log | Final send to real humans, price, SOW sign, intake scheduling |
| Prep A (LICENSE draft, README) | Approve public flip + license SPDX |
| Triage dry-run issues | Physical bench / on-site |

---

*2026-07-18 · pairs with B→A plan*
