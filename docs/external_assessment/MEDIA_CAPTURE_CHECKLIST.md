# Hardware-Splicer — Reusable Media Capture Checklist

Capture these assets once and reuse them across competition decks, videos, papers and partner reviews.

The media kit must show current truth state. Do not stage fake live-model or physical evidence.

## A. Hero assets

### H1 — Product hero

One clean screenshot of the main Hardware-Splicer product surface with:

- project name visible;
- current engineering task visible;
- evidence/revision state visible if possible;
- no developer console clutter;
- no secrets, local usernames or irrelevant browser chrome.

Use on title slides and application thumbnails.

### H2 — Architecture graphic

Render the canonical architecture:

`General-purpose agent → MCP/API → Hardware-Splicer → deterministic constraints + evidence → candidate → human authorization → physical world`

Must visually distinguish:

- model reasoning;
- deterministic system;
- physical evidence;
- human authority.

### H3 — Evidence-state graphic

Simple three-column visual:

- **PROVEN** — software, adversarial corpus, MCP, trace infrastructure;
- **PENDING** — live model, fresh physical SPI, independent operator;
- **NOT CLAIMED** — production readiness/universal correctness.

This is useful precisely because it shows discipline rather than pretending everything is complete.

## B. Product screenshots

### P1 — Project/revision state

Show an exact project and revision boundary.

### P2 — Source/evidence ingestion

Show provenance-bearing source/evidence records rather than raw prose only.

### P3 — Engineering plan/candidate

Show the generated/structured engineering work product.

### P4 — Deterministic blocking state

Prefer a real example where the system refuses to proceed because evidence is missing/conflicting/stale.

### P5 — Engineering Package

Show the final auditable package/artifact list, not merely a chat answer.

### P6 — Physical-evidence/authority surface

Show that real-vs-simulated state and authorization are explicit fields/states.

## C. MCP proof screenshots

### M1 — MCP operation discovery

Show the canonical four-tool gateway or operation catalog without overwhelming the judge with all 193 operations.

### M2 — Stateful MCP interaction

Show one clean trace proving:

1. project write;
2. later project read;
3. cleanup/delete.

### M3 — Closed authority

Show a trace/result where MCP physical authority remains false/closed.

### M4 — External-runner manifest

Show frozen case count/config/trace structure **without pretending a live provider run occurred**.

## D. Adversarial corpus assets

### C1 — Ten-case matrix

Create a compact table showing:

baseline / source reverse / source rotate / neutral labels / mission paraphrase / partial evidence / identity conflict / parser failure / analogy trap / stale revision.

### C2 — One failure-mode example

Pick one case such as identity conflict or stale revision and visually show:

`input evidence → unresolved/blocked state → why that is correct behavior`

This is more persuasive than ten walls of JSON.

## E. 3-minute video shot list

### 0:00–0:20 — problem

Show a plausible AI hardware answer, then overlay the unanswered questions: identity? voltage? provenance? revision? measured?

### 0:20–0:40 — principle

Show the four-layer architecture and the doctrine:

`AI proposes → deterministic systems constrain → bench evidence decides → human authorizes`

### 0:40–1:20 — product

Navigate one real Hardware-Splicer project:

- evidence/source;
- engineering state;
- candidate/package;
- a deterministic gate.

### 1:20–1:55 — model independence / MCP

Show MCP discovery and one stateful tool interaction. State explicitly that the gateway reaches the canonical backend rather than reimplementing engineering logic.

### 1:55–2:25 — adversarial evaluation

Show the ten-case corpus matrix and one adversarial example.

### 2:25–2:45 — evidence state

Show PROVEN / PENDING / NOT CLAIMED.

### 2:45–3:00 — closing

> Hardware-Splicer does not need the AI to be infallible. It needs uncertainty to remain unable to silently become physical authority.

## F. Capture hygiene

Before recording:

- use a clean browser profile/window;
- close personal tabs;
- remove API keys/tokens/local paths from screen;
- use one consistent project name;
- ensure timestamps/revision labels are coherent;
- avoid old branding such as Circuit-AI/mecha-splicer unless historical evolution is explicitly relevant;
- avoid opening internal engineering diaries during a judge-facing demo;
- do not show a green CI job as if it were a physical bench result;
- do not label the frozen corpus as “passed by GPT” until the actual live run exists.

## G. Minimum viable media package

If time is constrained, capture only:

1. H1 product hero;
2. H2 architecture;
3. P4 deterministic block;
4. P5 engineering package;
5. M2 MCP interaction;
6. C1 ten-case matrix;
7. H3 evidence state;
8. one continuous 3-minute recording using the shot list above.

Those eight assets are enough to populate most near-term submissions without additional design work.
