# Engineering Source Ingestion and Project Preflight

Hardware Splicer now has a bounded path for attaching real files to a revisioned engineering project and then generating a guided plan from that exact persisted source boundary.

## Canonical routes

- `GET /v1/engineering/sources/ingestion/schema`
- `POST /v1/projects/{project_id}/sources/ingest`
- `POST /v1/projects/{project_id}/engineering/plan`

Frontend proxies:

- `PUT /api/proxy/engineering/projects/{projectId}/snapshot`
- `POST /api/proxy/engineering/projects/{projectId}/sources/ingest`
- `POST /api/proxy/engineering/projects/{projectId}/plan`

All writes carry `expected_revision`. Stale writes return a revision conflict instead of silently overwriting newer project state.

## Source-ingestion request

```json
{
  "filename": "robot.urdf",
  "content_base64": "...",
  "declared_media_type": "application/xml",
  "authority_ceiling": "declared",
  "captured_at": null,
  "metadata": {},
  "expected_revision": 1
}
```

The current transport is canonical base64 and is limited to 16 MiB decoded per file. This is a bounded first transport, not the final streaming or multipart upload surface.

## Storage and identity

The server:

1. validates the project identity and optimistic revision;
2. decodes the bounded content;
3. computes SHA-256 over the received bytes;
4. classifies the file conservatively;
5. stores it under the project in a content-addressed path;
6. registers an upload audit record and source descriptor in a new project revision.

Project JSON retains metadata and an immutable blob reference. Raw bytes are not returned in the API response and are not embedded in the snapshot.

The project-scoped layout is:

```text
<project-root>/<project-id>/
  project.json
  revisions/
  sources/
    sha256/
      <digest-prefix>/
        <full-digest>
```

Repeated identical bytes reuse the same blob. Repeating the exact same filename/content registration is idempotent and does not create another project revision.

## Bounded classification

Structured parser routing is prepared for:

- URDF, SDF and MJCF → `robot_model_import`;
- STEP/STP → `step_geometry`;
- valid JSON → `engineering_source_descriptor`.

The following are retained as inventory-only:

- KiCad files;
- firmware binaries and source bundles;
- PDFs;
- photographs and images;
- videos;
- CSV and general text;
- archives;
- unknown binary formats.

Inventory-only means the bytes are stored, hashed and registered. It does not mean they were parsed, validated, executed or interpreted.

Archives are deliberately not extracted. Extraction remains blocked until path traversal, symlink, decompressed-size, expansion-ratio and aggregate-session controls exist.

## Project-bound guided planning

`POST /v1/projects/{project_id}/engineering/plan` loads the current project revision, collects its registered `engineeringSources`, combines any explicitly supplied additional source descriptors, runs the canonical guided planner, and saves the result as the next optimistic revision.

The route preserves:

- upload audit records;
- registered source descriptors and blob references;
- unknown future project fields;
- the project ID boundary;
- fail-closed physical authority.

The generated snapshot receives the normal guided-plan, MachineProject, source graph, topology, analysis, manufacturing, execution, operator-guide, readiness and unified-status fields.

## User-facing workspaces

### Engineering Sources

`/engineering/sources` lets an ordinary user:

- create or load a revisioned project;
- drag and drop or select real files;
- queue multiple files;
- see browser-read and network-upload progress;
- cancel an active upload;
- remove or retry failed items;
- upload sequentially against the newest revision;
- inspect SHA-256, blob identity, classification, parser disposition and limitations;
- download the registered source manifest.

### Project Preflight

`/engineering/project-preflight` lets the user:

- load a revisioned project;
- see its registered-source count;
- enter mission, mode, parts and constraints;
- generate the canonical guided plan from persisted sources;
- save the plan as the next project revision;
- inspect phase, blockers, advisories, next action and authority gates;
- download the plan or open Project inspector.

## Authority boundary

An uploaded file may enter only as `unknown`, `proposed` or `declared` authority. The ingestion route rejects attempts to introduce a file directly as `observed`, `measured`, `verified` or `authorized`.

Neither ingestion nor project planning grants:

- fabrication authority;
- firmware flashing authority;
- power-on authority;
- motion authority;
- release authority.

A hash proves byte identity inside the HS project store. It does not prove that the file is correct, safe, current, physically matched, authored by a trusted party or suitable for production.

## Current limitations

- Base64 transport, not streaming multipart upload.
- One file per backend request; the UI sequences multiple requests.
- No resumable upload sessions.
- Browser cancellation cannot reverse a request already completed server-side.
- No archive extraction.
- No automatic PDF, image or video interpretation.
- No automatic KiCad project assembly.
- Structured classification does not yet invoke and persist parser output in the same transaction.
- Source-role correction is not yet available in the UI.
- A failed project-revision write after blob publication can leave an unreferenced content-addressed blob; garbage collection is later maintenance work.

## Next tranche

1. Invoke supported structured parsers against stored blobs and persist bounded parser output.
2. Add source-role correction without permitting authority elevation.
3. Move from base64 JSON to bounded streaming or multipart sessions.
4. Add resumable uploads and aggregate-session ceilings.
5. Add content-addressed orphan reporting and garbage collection.
6. Add browser-level interaction tests against a running backend.
