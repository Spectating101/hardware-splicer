# 10-Minute Demo Script

## 0:00-0:45 - Opening

Introduce Circuit.AI Hardware Splicer as an AI agent for board understanding,
repair, reuse, and safe recomposition.

Key line:

```text
This is not a PCB photo labeler. It is an evidence-gated repair authority agent.
```

## 0:45-2:00 - Problem

Explain the practical problem:

- unknown boards are difficult to reuse safely
- visual AI can identify parts but cannot prove electrical safety
- repair/reuse requires measurements, test planning, and scoped claims

## 2:00-3:15 - System Architecture

Show `ARCHITECTURE_ONE_PAGER.md`.

Explain:

- multi-photo evidence
- Qwen/vision extraction
- topology hypothesis
- measured bench packet
- deterministic verifier
- production casefile

## 3:15-6:45 - Live Showcase

Open:

```text
http://127.0.0.1:3001/showcase?state=release
```

Demo steps:

1. Start on `Release ready`.
   - show score `1.00`
   - show production repair authorized
   - show 6/6 gates closed
   - show backend route and `live_model_advisory=false`

2. Click `Reference only`.
   - score drops to `0.18`
   - gates drop to `2/6`
   - casefile says authority is still gated
   - measurement closure shows `0/6`

3. Click `Measured packet`.
   - show measured topology and deterministic checks unlocked
   - explain this is not final release yet

4. Click `Release ready`.
   - show production repair authorized again
   - explain the scoped release claim

## 6:45-8:00 - Why AI Agent Matters

Explain model roles:

- vision model identifies candidates from photos
- reasoning model helps plan measurements and hypotheses
- deterministic verifier controls final authority

Key line:

```text
The model can suggest; the evidence ledger decides.
```

## 8:00-9:15 - July-August Plan

Summarize roadmap:

- multi-photo board intake
- Qwen vision trial under budget controls
- real-board case corpus
- bilingual UI
- final measured board demo

## 9:15-10:00 - Closing

End with:

```text
The goal is to make physical circuit boards legible and reusable without letting
AI overclaim safety. Circuit.AI turns uncertain board evidence into measured,
auditable repair authority.
```

## Q&A Prep

Likely questions:

- Why is this related to semiconductor AI?
  - It applies AI agents to practical electronics, circuit boards, test
    planning, repair, and reuse, which are downstream semiconductor/hardware
    workflows.

- Why not just use a vision model?
  - Vision is useful for candidate extraction, but repair authority requires
    physical measurements and scoped safety gates.

- What will the subsidy be used for?
  - Native vision tests, multi-photo extraction, case corpus evaluation, and
    final demo preparation.

- Is it safe?
  - The system blocks high-risk actions and refuses production authority without
    measured topology and bench evidence.

