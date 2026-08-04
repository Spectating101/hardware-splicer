# Resumable Source Uploads

Hardware Splicer now supports bounded, project-scoped upload sessions for files that may need to resume after an interrupted browser request.

## Canonical routes

- `GET /v1/engineering/sources/upload-sessions/schema`
- `POST /v1/projects/{project_id}/source-upload-sessions`
- `GET /v1/projects/{project_id}/source-upload-sessions/{session_id}`
- `PUT /v1/projects/{project_id}/source-upload-sessions/{session_id}/chunks/{chunk_index}`
- `POST /v1/projects/{project_id}/source-upload-sessions/{session_id}/finalize`
- `DELETE /v1/projects/{project_id}/source-upload-sessions/{session_id}`

## Session creation

A session records:

- project and pinned expected revision;
- filename and declared total size;
- declared media type;
- authority ceiling, capped at `declared`;
- optional whole-file expected SHA-256;
- fixed chunk size and chunk count;
- creation and expiration times;
- received chunk hashes;
- finalization state.

Creating a session does not mutate the project revision.

The current limits are:

- 16 MiB total file size;
- 1 MiB chunks;
- at most 16 chunks;
- 24-hour declared session lifetime.

The expiration timestamp is recorded, but automatic expiry cleanup is not yet scheduled in this tranche.

## Chunk upload

Each chunk is uploaded as a raw request body. The request may carry `X-Chunk-SHA256`.

The server requires the exact expected byte count for that chunk, computes SHA-256, stores it atomically, and records the chunk in the session manifest.

Repeating a chunk with identical bytes is idempotent. Reusing the same chunk index with different bytes is rejected.

Chunk upload does not mutate the project revision.

## Finalization

Finalization requires:

1. every expected chunk;
2. each stored chunk to match its manifest size and hash;
3. the assembled byte count to match the declared total;
4. the whole-file SHA-256 to match the optional expected hash;
5. the project still to be at the session's pinned revision.

After reconciliation, Hardware Splicer uses the same bounded classification and content-addressed registration model as multipart ingestion, then writes one optimistic project revision.

The session is marked finalized only after the project registration succeeds. Temporary chunks are removed after finalization while the session manifest and final ingestion record remain.

## Crash recovery boundary

If project registration succeeded but the process stopped before the session manifest was marked finalized, a later finalize request recomputes the file identity and checks the current project registry. When the exact filename and content hash are already registered, the session is repaired to finalized instead of writing another project revision.

An unrelated project revision change blocks finalization.

## Abandonment

Deleting an open session marks it abandoned and removes temporary chunks. It does not mutate the project.

A finalized session cannot be abandoned.

## Browser workspace

`/engineering/resumable-uploads` supports:

- project creation and loading;
- local whole-file SHA-256 commitment;
- upload-session creation;
- recovery by session ID;
- selection of the original file before resume;
- filename and size matching;
- missing-chunk upload;
- per-chunk SHA-256 headers;
- network progress;
- cancellation of the active chunk;
- final whole-file reconciliation;
- abandonment;
- transition to Source Lab and project planning.

The browser stores only the session ID in local storage. It cannot recover a browser `File` object after reload; the user must reselect the original file.

## Authority boundary

Sessions and chunks are transport state only. They never grant:

- fabrication authority;
- firmware flashing authority;
- power-on authority;
- motion authority;
- operational authority;
- release authority.

A source enters the project only at successful finalization and remains bounded to `unknown`, `proposed`, or `declared` authority.

## Current limitations

- 16 MiB total file ceiling.
- Fixed 1 MiB chunk size.
- No parallel chunk coordination or server-side locking for multiple writers.
- No automatic cleanup worker for expired sessions.
- No aggregate user, project, or deployment quota.
- Final assembly remains memory-bounded rather than disk-streamed.
- No malware scanning.
- No browser-level test against a running backend.

## Next operational tranche

A later branch should add:

1. explicit session cleanup and quota reporting;
2. atomic session locking or compare-and-swap manifests;
3. disk-streamed final assembly;
4. deployment-wide and project quotas;
5. orphan blob and abandoned session administration;
6. browser-level tests against the product API.
