# Engineering Package Export

The Engineering Package is Hardware Splicer's deterministic handoff, audit, and benchmark artifact. It captures one exact project revision as a content-addressed directory and ZIP without copying registered raw source bytes.

## Package identity

A package ID has the form:

`engineering-package-r00000000-<snapshot-digest-prefix>`

It binds:

- project ID;
- exact source revision;
- sanitized project snapshot SHA-256.

The same sanitized snapshot at the same revision produces the same package ID, file payloads, manifest, ZIP bytes, and ZIP SHA-256.

## Deterministic ZIP

The ZIP is created with:

- lexicographically ordered entries;
- fixed entry timestamps;
- fixed file permissions;
- stored, uncompressed payloads;
- canonical sorted JSON with a trailing newline.

This prioritizes cross-run reproducibility and hash stability over compression ratio.

## Package contents

The current package contains:

- `PROJECT_BRIEF.json`
- `REQUIREMENTS.json`
- `SOURCE_MANIFEST.json`
- `SOURCE_CONFLICTS.json`
- `ARCHITECTURE_CANDIDATES.json`
- `DECISIONS.json`
- `ACTION_TRACE.json`
- `TOOL_RESULTS.json`
- `REPAIR_LINEAGE.json`
- `CONVERSATION_BRIEFINGS.json`
- `BLOCKERS.json`
- `AUTHORITY_STATE.json`
- `ARTIFACT_REFERENCES.json`
- `MANIFEST.json`
- `README.md`

`MANIFEST.json` identifies every other included file by SHA-256 and byte count. The manifest intentionally excludes a self-hash. The package record identifies the complete ZIP by SHA-256 and byte count.

## Source boundary

Source files are represented by bounded descriptors such as:

- source identity;
- type;
- content hash;
- authority ceiling;
- parser and derived-source metadata;
- bounded storage identity where available.

Registered raw source bytes are never copied into the package. Raw-content and binary fields are recursively omitted, and common credential/token keys are removed.

Software preview artifacts are referenced by project-relative path, SHA-256, and byte count. Their bytes are not embedded in this package version.

## AI and engineering trace

The package preserves:

- requirements and architecture candidates by session;
- proposal and repair-session identities;
- human action decisions;
- action status and source references;
- software preview summaries and failures;
- repair parent/child lineage;
- JARVIS user questions, answers, evidence references, blockers, and recommended action IDs;
- unresolved project, source, conversation, and tool blockers.

Conversation briefings remain explicitly non-authoritative. Software previews remain software evidence only.

## Authority record

`AUTHORITY_STATE.json` records the project authority fields present in the source revision. Package creation has `authority_effect: none` and cannot grant fabrication, flashing, power-on, motion, operational, or release authority.

The package is a record of project state; it is not itself permission to act on hardware.

## API

Schema:

`GET /v1/engineering/packages/schema`

List:

`GET /v1/projects/{project_id}/engineering-packages`

Create:

`POST /v1/projects/{project_id}/engineering-packages`

with an exact `expected_revision`.

Download:

`GET /v1/projects/{project_id}/engineering-packages/{package_id}/download`

Creation writes the package artifact, appends its record to `engineeringPackages`, and creates one optimistic project revision. A retry using the original source revision returns the existing package record without another project revision.

## Verified download

Download does not trust a caller-supplied filesystem path or a stored arbitrary path. It:

1. validates project and package identities;
2. reconstructs the exact project-local package ZIP path;
3. enforces the project/package directory boundary;
4. verifies the current ZIP byte count;
5. verifies the current ZIP SHA-256;
6. serves the ZIP with package identity, source revision, and SHA-256 response headers.

A missing or tampered ZIP is refused.

## Current limitations

- Software preview artifact bytes are referenced rather than embedded.
- No cryptographic signature or external timestamp authority yet.
- No detached signing key management.
- No PDF summary rendering.
- No package-diff UI.
- No browser package-management surface in this backend tranche.
- No green or deployability claim until exact-head CI completes.
