# Engineering Multipart Upload

Hardware Splicer now has a bounded multipart transport for attaching real project files without browser-side base64 conversion.

## Canonical routes

- `GET /v1/engineering/sources/multipart/schema`
- `POST /v1/projects/{project_id}/sources/ingest-file`

The frontend proxy is:

- `POST /api/proxy/engineering/projects/{projectId}/sources/ingest-file`

The request uses `multipart/form-data` with:

- `file` — one uploaded file;
- `expected_revision` — current optimistic project revision;
- `authority_ceiling` — `unknown`, `proposed`, or `declared`;
- `captured_at` — optional capture time;
- `metadata_json` — optional JSON object.

## Transport behavior

The browser Uploads workspace sends the original `File` through `FormData` and `XMLHttpRequest`.

This provides:

- no browser base64 expansion;
- real network upload progress;
- cancellation of the active browser request;
- sequential optimistic writes for multiple queued files;
- direct display of the server hash, classification and blob identity.

The Next.js proxy forwards the incoming multipart request body stream directly to the canonical product API. It does not call `request.formData()`, convert the file to text, or reconstruct the multipart envelope.

## Backend bounds

The backend reads the uploaded file in 1 MiB chunks and refuses content above 16 MiB.

For an accepted file it:

1. validates the project and `expected_revision` before reading file bytes;
2. validates the requested authority ceiling;
3. reads the upload under the hard byte limit;
4. computes SHA-256 server-side;
5. classifies the file conservatively;
6. writes the content-addressed project blob atomically;
7. registers upload and source metadata in the next project revision.

The existing base64 JSON route remains available for compatibility. Multipart is the preferred ordinary-user transport.

## What streaming means here

The frontend proxy preserves the request body as a stream instead of buffering and re-encoding it.

The FastAPI endpoint reads the uploaded file incrementally from `UploadFile`, but the current implementation still accumulates one bounded file in memory before content-addressed publication. Therefore this tranche removes base64 overhead and proxy buffering, but it is not yet a disk-spooled, arbitrarily large, or resumable upload service.

## Idempotence

Uploading the same filename and identical bytes again reuses the content-addressed blob and does not create another project revision when the source is already registered.

The same bytes under a different filename reuse the blob but may create a separate upload audit record. The source identity remains hash-derived.

## Authority boundary

Multipart upload may enter only at:

- `unknown`;
- `proposed`;
- `declared`.

The route rejects `observed`, `measured`, `verified`, or `authorized` upload authority.

Upload does not grant:

- fabrication authority;
- firmware flashing authority;
- power-on authority;
- motion authority;
- operational authority;
- release authority.

## Cancellation boundary

Browser cancellation aborts the active HTTP request from the client side. It cannot reverse a request that the server already fully received and committed. Project revision and source identity remain the authoritative completion record.

## Uploads workspace

`/engineering/uploads` supports:

- project creation and loading;
- drag-and-drop or file selection;
- multi-file queues;
- sequential optimistic revision updates;
- network progress;
- active-request cancellation;
- retry and removal;
- classification, hash and blob inspection;
- transition to Source Lab for parsing and role correction.

## Current limitations

- 16 MiB per file.
- One file per backend request.
- No resumable sessions or chunk manifests.
- No aggregate queue or project quota.
- No disk-spooled temporary upload before final publication.
- No malware scanning.
- No archive extraction.
- No orphan-blob garbage collection.
- No browser-level test against a running backend.

## Next transport tranche

A later branch should add:

1. upload-session identities;
2. resumable chunk manifests;
3. aggregate session and project quotas;
4. disk-spooled temporary objects;
5. final hash reconciliation before publication;
6. abandoned-session cleanup;
7. browser-level product tests.
