# Outsider JARVIS Browser End-to-End Validation

This validation exercises the three primary Hardware Splicer product surfaces in a real Chromium browser against a stateful deterministic backend.

It closes a different gap from the rover and semiconductor golden harnesses:

- golden harnesses prove revisioned backend and package contracts;
- this workflow proves that an ordinary user can navigate and understand those contracts through the production frontend.

No production API or UI behavior is changed by this tranche.

## Production surfaces under test

The browser uses a production Next.js build and visits:

1. `/engineering/jarvis`
2. `/engineering/ai-studio`
3. `/engineering/packages`

All browser requests pass through the real authenticated Next.js proxy routes before reaching the mock Hardware Splicer backend.

## Stateful mock project

`scripts/mock_outsider_jarvis_backend.py` exposes one deterministic project:

- project ID: `outsider-fixture`
- parent AI session: `outsider-session`
- initial project revision: 6
- two registered source descriptors;
- one persisted failed `run_compose` action;
- one deterministic tool-result artifact identity;
- all physical-authority fields false.

The failure is the same class used by the semiconductor fixture case:

`1.8 V DUT interface is not protected from 3.3 V controller`

The mock exists only for browser validation. It does not replace the golden backend harnesses.

## Browser path

### 1. Grounded JARVIS question

The outsider enters the project and session IDs, loads revision 6, and asks:

`Is this fixture ready for fabrication?`

The backend advances to revision 7 and returns:

- a blocked pre-fabrication decision briefing;
- a citation to the failed tool-result identity;
- a citation to the DUT source identity;
- explicit unresolved blockers;
- one typed `prepare_verification` proposal;
- visible `Awaiting human review` state.

The browser asserts that JARVIS is still labelled guidance rather than project truth.

### 2. AI Studio repair review

The outsider follows **Review in AI Studio**, reloads the same project/session, and observes:

- the failed compose action;
- the persisted voltage-domain error;
- the software-preview artifact summary;
- the **Propose bounded repair** control.

Creating the repair advances the mock project from revision 7 to revision 8 and displays:

- `failure_repair` successor session;
- default-off translated DUT adapter candidate;
- failed parent action identity;
- failure SHA-256;
- repair iteration;
- fresh proposed repair action.

The original failed result remains available through the parent lineage.

### 3. Engineering Package export and download

The outsider follows the shared **Packages** navigation, loads revision 8, and exports it.

The backend advances to revision 9 and the page displays:

- content-addressed package ID;
- source revision 8;
- 15-file count;
- ZIP byte count;
- snapshot SHA-256;
- manifest SHA-256;
- ZIP SHA-256;
- raw-source-byte exclusion;
- unchanged physical authority.

The browser clicks **Verified ZIP** and asserts:

- the expected download filename;
- non-empty downloaded bytes;
- valid ZIP `PK` signature.

The backend serves a real ZIP stream through the real Next.js binary proxy.

## Workflow isolation

The browser tooling is not added to the frontend production dependency lockfile.

`.github/workflows/outsider-jarvis-browser-e2e.yml` performs an isolated CI-only installation of:

- `@playwright/test` 1.55.0;
- Chromium and its runner dependencies.

It then:

1. compiles the Python mock backend;
2. runs frontend typecheck;
3. creates a production Next.js build;
4. starts the backend on port 8090;
5. starts the production frontend on port 3000;
6. waits for both health surfaces;
7. runs the Chromium path;
8. retains Playwright traces and service logs on failure;
9. terminates both services.

## What this proves

A passing browser run demonstrates that an outsider can:

- load a revisioned project/session;
- ask one grounded question;
- see evidence and blockers;
- understand that recommendations require review;
- inspect a failed deterministic preview;
- create a separate repair successor;
- inspect repair lineage;
- export one exact project revision;
- inspect all package hashes;
- download a ZIP through the verified proxy path;
- see that physical authority remains separate.

## What this does not prove

The mock backend does not prove:

- live-model response quality;
- production database behavior;
- multi-user concurrency;
- deployed authentication configuration;
- real package cryptographic verification inside the mock;
- fabrication readiness;
- DUT safety;
- physical bring-up;
- operational or release authority.

Those remain covered by backend contracts, golden packages, deployment validation, and physical evidence rather than browser presentation alone.
