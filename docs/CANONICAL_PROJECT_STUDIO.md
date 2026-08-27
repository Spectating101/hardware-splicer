# Canonical Hardware Splicer Project Studio

## Status

Draft product contract for the primary first-use interface introduced at:

```text
/engineering/studio
```

This surface is intended to become the normal entry point for engineers, students, laboratories, startups, repair teams, and reviewers. Existing pages such as Source Lab, AI Studio, JARVIS Console, Uploads, Packages, and the Engineering Inspector remain available as advanced or diagnostic workspaces.

The canonical Studio does not replace their backend contracts. It removes the requirement that ordinary users understand those contracts before accomplishing useful work.

---

## Product promise

A user should be able to enter Hardware Splicer with only this knowledge:

> What am I trying to build, validate, repair, or understand?

The interface should carry that user through:

```text
intent
→ project
→ evidence
→ requirements and candidates
→ human review
→ deterministic software checks
→ bounded repair
→ evidence-grounded JARVIS conversation
→ reproducible Engineering Package
```

The interface must never imply that successful conversation, software execution, or export authorizes fabrication or physical operation.

---

## User mental model

Users should see **one project**, not a collection of unrelated AI tools.

A project contains:

- mission and constraints;
- exact revision;
- sources and parsed records;
- requirements;
- architecture candidates;
- proposed actions;
- human decisions;
- deterministic preview results;
- failures and repair successors;
- JARVIS briefings;
- blockers;
- packages;
- physical-authority state.

Session IDs, action IDs, hashes, parser identities, provider names, and internal routes remain available under **Advanced details**, but they are not the primary navigation model.

---

## Primary layout

The canonical Studio uses three persistent regions.

### Left: project and progress

The left rail answers:

- Which project am I working on?
- Which revision is active?
- Where am I in the engineering workflow?
- What work has already been completed?

It contains:

1. persisted project list;
2. resume action;
3. six-stage project progress rail.

The six stages are:

1. **Brief** — a persisted project exists;
2. **Evidence** — sources have been registered;
3. **Candidate** — a revision-pinned AI session exists;
4. **Review** — a proposal has received a human decision or software result;
5. **JARVIS** — at least one conversation turn has been persisted;
6. **Package** — a deterministic Engineering Package exists.

These are workflow milestones, not authority levels.

### Center: work

The center is the normal user path:

1. define the project;
2. add evidence;
3. generate and review candidates;
4. ask JARVIS;
5. export a handoff package.

All mutations stay in the current project context and advance the optimistic project revision.

### Right: truth and control

The right rail answers:

- What should I do next?
- How much evidence exists?
- What is blocked?
- Which physical gates are closed?

It contains:

- next-best-move explanation;
- project counts;
- explicit fabrication, flashing, power, motion, operation, and release gates;
- open questions, tool failures, and JARVIS blockers;
- advanced technical identities.

This region should remain visible while the center content changes.

---

## First-use modes

The initial brief offers four comprehensible starting patterns.

### Build something new

For greenfield boards, machines, products, and prototypes.

Expected evidence:

- requirements;
- reference designs;
- component constraints;
- cost, size, power, environmental, or manufacturing limits.

### Validation fixture

For semiconductor support hardware, adapter boards, socket fixtures, lab interfaces, and NPI test hardware.

Expected evidence:

- DUT datasheet and pin map;
- socket or connector drawing;
- voltage and current limits;
- test specification;
- fixture controller manual;
- bring-up procedure.

### Repair or inherit

For incomplete, damaged, undocumented, donor, or inherited hardware.

Expected evidence:

- board photos;
- symptoms;
- service notes;
- schematics or partial layouts;
- continuity, resistance, voltage, current, thermal, and functional observations.

### Robot or machine

For mechatronics and robotics.

Expected evidence:

- mechanical envelope;
- parts and power system;
- wiring and connector information;
- firmware manifests;
- ROS or middleware contracts;
- assembly and bring-up procedures.

The mode changes defaults and guidance. It must not silently grant a stronger source authority or engineering permission.

---

## Evidence intake model

The intended intake sequence is:

```text
select or drop files
→ store exact bytes
→ compute content identity
→ classify source
→ run bounded parser
→ inspect derived records
→ resolve source role or conflict
→ expose usable evidence to the project session
```

### Current canonical Studio tranche

The first tranche performs:

- multipart file selection;
- bounded 16 MiB-per-file upload;
- optimistic project revision checks;
- declared maximum authority;
- source count and parser-run visibility.

### Existing advanced capabilities

Source Lab already supports:

- stored-byte re-verification;
- bounded parser execution;
- parsed-record inspection;
- source-type correction;
- authority-ceiling correction without authority elevation.

### Next intake tranche

The next interface improvement should make parsing ordinary rather than advanced:

1. automatically identify newly registered sources with no successful parser run;
2. show an **Extract usable evidence** action;
3. run eligible bounded parsers sequentially against exact revisions;
4. present a compact triage result:
   - parsed successfully;
   - needs source-role confirmation;
   - unsupported format;
   - conflict detected;
   - parser failed;
5. require the user to resolve only ambiguous or consequential cases.

The user should not need to know the phrase “parser route” to use the product.

---

## Candidate and action interaction

The central candidate experience borrows proven patterns from existing AI engineering tools while preserving Hardware Splicer’s authority boundary.

### Candidate card

A candidate must show:

- title;
- bounded summary;
- requirement count;
- source-linked requirements;
- unresolved questions;
- trade-offs;
- proposed status.

It is never displayed as a verified design merely because a model produced it.

### Action card

Every project change is represented as a typed action.

The user can:

- accept the proposal;
- reject the proposal;
- run an allowlisted software preview after acceptance;
- create a bounded repair successor after a persisted failure.

The sequence remains visible:

```text
proposal
→ human decision
→ optional deterministic preview
→ persisted result
→ optional repair successor
```

The interface must not collapse these into one “Run AI” button.

---

## JARVIS interaction

JARVIS lives inside the project rather than beside it.

A user asks a concrete question against the active revision. The answer may contain:

- technical explanation;
- decision briefing;
- evidence references;
- blockers;
- one or more typed proposed actions.

The conversation is not itself project truth.

Recommended changes must enter the ordinary action queue and require the same review and execution boundaries as every other proposal.

Typical questions include:

- What is unsupported?
- Why did this preview fail?
- Which source controls this requirement?
- Is the design ready for fabrication?
- What evidence is missing before first power?
- What should we review next?

---

## Engineering Package interaction

Package export is the final step in the visible workflow, but not necessarily the end of engineering.

The package records:

- source descriptors and hashes;
- requirements;
- candidates;
- decisions;
- action trace;
- deterministic tool results;
- repair lineage;
- JARVIS briefings;
- blockers;
- artifact references;
- physical-authority state.

The Studio shows:

- source revision;
- package ID;
- ZIP SHA-256;
- verified download.

Package export must continue to have no physical-authority effect.

---

## Progressive disclosure

The normal path avoids exposing:

- project IDs during ordinary resume;
- AI session IDs;
- action IDs;
- provider configuration;
- prompt hashes;
- context hashes;
- API routes;
- parser identities.

These remain accessible through **Advanced details** and the dedicated technical workspaces.

The objective is not to hide provenance. It is to expose provenance when it helps a decision rather than forcing every user to operate the database manually.

---

## Resume behavior

Opening a persisted project should restore:

- latest project revision;
- project brief;
- source and parser counts;
- most recent AI or repair session;
- active requirements, candidate, and actions;
- JARVIS turn history;
- package list;
- blockers;
- physical gates.

The user should not paste a project ID and session ID into multiple pages.

The current Studio automatically selects the latest persisted AI session from the project snapshot.

---

## Discoverability

A persistent **Start here → Project Studio** launcher is displayed throughout the application except inside the canonical Studio itself.

This is a transitional product measure while the older Circuit.AI surfaces and the new Hardware Splicer workflow coexist.

Longer term, the application’s primary navigation should become:

```text
Projects
Studio
Evidence
Packages
Administration
```

Analyze, Components, CAD, Source Lab, AI Studio, JARVIS Console, and other specialist surfaces should move under project-scoped advanced tools.

---

## Current limitations

The first canonical Studio tranche does not yet provide:

- automatic parser execution after upload;
- URL-addressable project context;
- explicit **New project** reset after a project is active;
- project search and filtering;
- team membership or role-based access;
- comments, assignments, approvals, or notifications;
- batch source-role triage;
- live provider/model selection;
- production deployment authentication proof;
- real physical evidence capture;
- mobile-optimized engineering review.

These limitations must not be hidden behind “JARVIS” branding.

---

## Recommended next interface tranches

### 1. Evidence extraction and triage

Make upload-to-usable-evidence one guided interaction.

### 2. Project URL and context persistence

Use a route such as:

```text
/engineering/studio/{project_id}
```

The route should restore the latest revision and optionally select a session, candidate, action, or package through URL state.

### 3. New-project and project-switching polish

Add:

- **New project** reset;
- searchable project switcher;
- recent projects;
- archived projects;
- duplicate-from-template;
- unsaved-change protection.

### 4. Candidate comparison

Display two or three candidates in a structured comparison across:

- requirement coverage;
- source coverage;
- power;
- size;
- cost;
- component availability;
- manufacturing burden;
- verification burden;
- unresolved risk.

### 5. Physical evidence workspace

Turn bring-up from a collection of forms into a guided procedure with:

- required instrument and calibration identity;
- current-limited power sequence;
- expected values;
- captured measurements;
- artifacts and photos;
- pass/fail disposition;
- scoped authority transition.

### 6. Collaboration

Add named project members, action ownership, review requests, comments, and approval history only after the single-user project flow is stable.

---

## Product decision rule

Every visible feature should answer at least one of these questions:

1. What are we trying to accomplish?
2. What evidence supports it?
3. What has the AI proposed?
4. What did deterministic tools establish?
5. What remains unknown or failed?
6. What may the human safely do next?
7. How can another person reproduce the decision?

Features that cannot answer one of these questions should not compete for prominence in the canonical Studio.
