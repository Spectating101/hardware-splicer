# Engineering Source Ingestion

Hardware Splicer now has a bounded first-pass path for attaching real project files to a revisioned engineering project.

## Canonical routes

- `GET /v1/engineering/sources/ingestion/schema`
- `POST /v1/projects/{project_id}/sources/ingest`

The frontend proxy for the write route is:

- `POST /api/proxy/engineering/projects/{projectId}/sources/ingest`

A project must already have at least one persisted revision. The request carries `expected_revision`; stale writes return a revision conflict instead of silently overwriting newer project state.

## Request

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

The current transport is canonical base64 and is limited to 16 MiB decoded per file. This is an initial bounded API contract, not the final streaming or multipart upload surface.

## Storage and identity

The server:

1. validates the project identity and optimistic revision;
2. decodes the bounded content;
3. computes SHA-256 over the received bytes;
4. classifies the file conservatively;
5. stores it under the project in a content-addressed path;
6. registers an upload record and source descriptor in a new project revision.

Project JSON retains only metadata and an immutable blob reference. Raw bytes are not returned in the API response and are not embedded in the snapshot.

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

Structured parser routing currently exists for:

- URDF, SDF and MJCF → `robot_model_import`;
- STEP/STP → `step_geometry`;
- valid JSON → `engineering_source_descriptor`.

The following are retained as inventory-only in this tranche:

- KiCad files;
- firmware binaries and source bundles;
- PDFs;
- photographs and images;
- videos;
- CSV and general text;
- archives;
- unknown binary formats.

Inventory-only means the bytes are stored, hashed and registered. It does not mean they were parsed, validated, executed or interpreted.

Archives are deliberately not extracted. Archive extraction remains blocked until path traversal, symlink, decompressed-size, expansion-ratio and aggregate-session controls exist.

## Authority boundary

An uploaded file may enter only as `unknown`, `proposed` or `declared` authority. The ingestion route rejects attempts to introduce a file directly as `observed`, `measured`, `verified` or `authorized`.

Ingestion never grants:

- fabrication authority;
- firmware flashing authority;
- power-on authority;
- motion authority;
- release authority.

A hash proves byte identity inside the HS project store. It does not prove that the file is correct, safe, current, physically matched, authored by a trusted party or suitable for production.

## Current limitations

- Base64 transport, not streaming multipart upload.
- One file per request.
- No upload progress, cancellation or resumable sessions yet.
- No archive extraction.
- No automatic PDF, image or video interpretation.
- No automatic KiCad project assembly.
- Structured classification does not yet invoke and persist parser output in the same transaction.
- A failed project-revision write after blob publication can leave an unreferenced content-addressed blob; garbage collection is a later maintenance tranche.

## Next interface tranche

The next UI work should:

1. create or select a revisioned project;
2. send files through the project-scoped proxy;
3. show per-file progress, cancellation and retry;
4. display the server hash, classification, parser disposition and limitations;
5. allow bounded correction of source role without raising authority;
6. pass registered source descriptors into guided planning;
7. save the generated plan as the next optimistic project revision;
8. open that exact revision in Project inspector.
