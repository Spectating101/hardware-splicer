# Engineering Package Workspace

The Engineering Package workspace is the product-facing export and download surface for revisioned Hardware Splicer handoffs.

Route:

`/engineering/packages`

## Project loading

The workspace loads one project ID, the latest project revision, current project authority fields, and all persisted `engineeringPackages` records.

The package list remains separate from the editable project snapshot displayed by the page. Package creation returns the new project revision and package record explicitly.

## Creating a package

**Export revision N** sends the exact current project revision as `expected_revision`.

The backend either:

- creates a deterministic package from that revision and advances the project by one package-record revision; or
- verifies and returns an existing package created from that source revision without another revision.

The workspace displays whether the package was newly created or replayed after verification.

## Package records

Each package card displays:

- content-addressed package ID;
- source project revision;
- included-file count;
- ZIP byte size;
- sanitized snapshot SHA-256;
- manifest SHA-256;
- complete ZIP SHA-256;
- raw-source-byte exclusion;
- package authority effect;
- unchanged physical authority.

The browser does not calculate or replace these identities. It renders the persisted backend package record.

## Verified download

The **Verified ZIP** control uses the canonical proxy for:

`GET /v1/projects/{project_id}/engineering-packages/{package_id}/download`

The backend reconstructs the project-local package path and verifies the current ZIP size and SHA-256 before serving it.

The Next.js proxy streams the backend response body and forwards only bounded download headers:

- content type;
- content length;
- content disposition;
- package ID;
- package SHA-256;
- source revision.

It does not fetch from a browser-supplied server path or proxy arbitrary filesystem content.

## Product navigation

The shared engineering navigation presents:

1. JARVIS — question and decision briefing;
2. AI Studio — proposal review, previews, and repair lineage;
3. Packages — reproducible handoff and audit export;
4. specialist source, planning, storage, and inspection surfaces.

The navigation is horizontally scrollable on narrower screens rather than clipping product routes.

## Authority and data boundary

The workspace states that a package records project state but cannot authorize:

- fabrication;
- firmware flashing;
- power-on;
- motion;
- operation;
- release.

It also states that registered raw source bytes are excluded and downloads are served only after backend hash and size verification.

## Current limitations

- No in-browser inspection of package JSON files.
- No package-to-package semantic comparison.
- No detached signature or external timestamp display.
- No package deletion or pruning controls.
- No browser-level test against a running backend.
- No green production-build claim until exact-head CI completes.
