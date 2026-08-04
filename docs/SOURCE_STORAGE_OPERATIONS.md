# Source Storage Operations

Hardware Splicer now has project-scoped storage audit and explicit cleanup for content-addressed source blobs and resumable upload-session chunks.

## Canonical routes

- `GET /v1/engineering/sources/storage/schema`
- `GET /v1/projects/{project_id}/source-storage/audit`
- `POST /v1/projects/{project_id}/source-storage/cleanup`

The frontend proxies are:

- `GET /api/proxy/engineering/projects/{projectId}/source-storage/audit`
- `POST /api/proxy/engineering/projects/{projectId}/source-storage/cleanup`

## Audit

The audit loads one project snapshot and builds the set of referenced blob paths from:

- `engineeringSources[].metadata.blob_ref`;
- `engineeringSourceUploads[].blob_ref`;
- `engineeringSourceUploads[].metadata.blob_ref`.

It then scans only that project's `sources/sha256` tree and records:

- project-relative blob reference;
- path digest and path-shape validity;
- actual SHA-256 validity;
- size and modification time;
- age in hours;
- referenced versus orphan state;
- corrupt or symlink state.

The audit also scans project upload-session manifests and reports:

- open, finalized, abandoned, or corrupt state;
- declared expiry;
- expired status;
- received chunk count;
- temporary chunk bytes;
- whether the chunk directory remains.

Audit never deletes data and never creates a project revision.

## Cleanup request

Cleanup accepts:

```json
{
  "dry_run": true,
  "minimum_age_hours": 24,
  "delete_orphan_blobs": true,
  "clean_expired_session_chunks": true,
  "include_corrupt_orphans": false,
  "confirm_project_id": ""
}
```

Dry-run is the default.

For destructive apply:

- `dry_run` must be `false`;
- `confirm_project_id` must exactly match the route project ID.

## Blob cleanup boundary

A blob is a normal cleanup candidate only when it is:

- not referenced by the selected project snapshot;
- older than the minimum age;
- a regular non-symlink file;
- located inside the project source tree;
- valid against its path SHA-256.

Referenced blobs are never candidates.

Corrupt unreferenced files remain report-only by default. They enter the candidate set only when `include_corrupt_orphans` is explicitly enabled. Symlinks are never deletion candidates.

The minimum age protects recently published blobs that may belong to an interrupted registration attempt.

## Session cleanup boundary

Expired open or abandoned sessions with remaining chunk directories may be cleanup candidates.

Applying cleanup:

- marks an expired open session abandoned;
- removes temporary chunk files;
- preserves the session manifest;
- does not alter finalized sessions;
- does not create a project revision.

## Storage Ops workspace

`/engineering/storage-ops` provides:

- project-scoped storage audit;
- referenced, orphan, corrupt, and byte summaries;
- upload-session and temporary-chunk summaries;
- configurable minimum candidate age;
- optional inclusion of corrupt orphans;
- dry-run cleanup preview;
- exact typed project confirmation before apply;
- post-operation refreshed audit.

## Authority and safety boundary

Storage operations do not modify engineering evidence authority and do not grant:

- fabrication authority;
- firmware flashing authority;
- power-on authority;
- motion authority;
- operational authority;
- release authority.

Cleanup mutates project-scoped storage files only. It does not rewrite project JSON, remove project revisions, or silently discard referenced sources.

## Current limitations

- Audit is project-scoped, not deployment-wide.
- Cleanup is manual; there is no automatic scheduler.
- Missing referenced blobs are not yet represented as separate audit records.
- Multiple simultaneous cleanup operators are not lock-coordinated.
- No deployment/user/project quota enforcement.
- No quarantine workflow for corrupt files.
- No browser-level test against a running backend.

## Next operations tranche

A later branch should add:

1. missing-reference records;
2. project and deployment quota policies;
3. session-manifest compare-and-swap or locking;
4. cleanup operation manifests and audit signatures;
5. corrupt-file quarantine instead of direct deletion;
6. deployment-wide administrative summaries;
7. browser-level end-to-end tests.
