# KiCad artifact retention

Hardware Splicer revisions are JSON envelopes. The compile `build_dir` they
point at is a mutable path reference — a later compose overwrites the same
files. This module copies the KiCad schematic and PCB that were reachable at
retention time into a content-addressed store so Compare can redline any two
retained revisions.

**Authority is never implicitly upgraded.** Retaining files and diffing them
changes no snapshot, revision, review, thread, or engineering claim.

## What is retained, and when

Only `.kicad_sch` and `.kicad_pcb` are stored. One file of each kind is
chosen, preferring paths under `build_compilation/` and then the first
relative path in sort order. Non-KiCad files are ignored.

| When | Basis | Who |
|------|-------|-----|
| After a successful new revision save | `at_save` | Product API (`PUT /v1/projects/{id}/snapshot` and other `ProjectStore.save` call sites). Best-effort and non-blocking. |
| Explicit retry | `after_save` | `POST /v1/projects/{id}/revisions/{revision}/artifacts/retain` |

`retain_revision_artifacts` returns `None` — and fabricates nothing — when the
snapshot has no usable build directory or no KiCad files. A build directory
outside the `build_files_security` allow-list, a symlink build dir, or a
symlinked KiCad file is skipped, not followed.

The save response may include `artifact_retention: {status, reason}` where
`status` is `retained`, `skipped`, or `failed`. A retention failure never
fails or rewrites the save.

## Content addressing and integrity

Blobs live beside the project tree, not inside revision JSON:

```text
projects/<id>/artifacts/sha256/<first two hex>/<64 hex>
projects/<id>/artifact_pins/<revision:08d>.json
```

Writes use `mkstemp` + `fsync` + `os.link` (create-only). An existing blob
with identical bytes is a no-op. Every read hashes the bytes and requires
`sha256(bytes) == name`; mismatch or a missing blob raises
`ArtifactIntegrityError`.

Pin schema `hardware_splicer.artifact_pins.v1`:

```json
{
  "schema_version": "hardware_splicer.artifact_pins.v1",
  "project_id": "robot",
  "revision": 1,
  "retained_at": "2026-10-05T00:00:00+00:00",
  "retention_basis": "at_save",
  "artifacts": {
    "schematic": {"relative": "build_compilation/board.kicad_sch", "sha256": "sha256:…", "size_bytes": 123},
    "pcb": null
  }
}
```

## Pin immutability

A pin is create-only. Pinning the same revision again with the same artifact
bytes is idempotent. Different bytes raise `ArtifactPinConflict`. Revision
files themselves are never modified.

## `at_save` versus `after_save`

`at_save` is the best-effort copy taken immediately after the revision JSON
lands. It can still miss: no build dir yet, path policy denied the dir, or
the retain step failed.

`after_save` is an explicit retry. **The bytes captured now may differ from
the bytes at save time because build directories are mutable.** The retry
route states that in the response. A revision already pinned to different
bytes cannot be overwritten.

## Diff endpoint

`GET /v1/projects/{id}/artifact-diff?base=<int>&candidate=<int>&kind=schematic|pcb`

- Both revisions must exist; otherwise `404` `{detail:{type,message}}`.
- A revision with no pin or a null entry for `kind` is **not** an error:
  HTTP 200 `{ok:true, project_id, available:false, reason:"Revision N has no retained <kind> artifact."}`.
- `base == candidate` with both sides present returns `available: true` and
  an empty structural diff.
- Both present: `{ok, project_id, base_revision, candidate_revision, kind,
  available:true, artifact:{base:{relative, sha256, retention_basis},
  candidate:{…}}, diff:<diff_kicad_text>}`.
- `KicadDiffError` → `422` `artifact_diff_error`. `ArtifactIntegrityError`
  → `500` `artifact_integrity_error`. Invalid `kind` / revision query →
  `422` `invalid_request`.

Also:

- `GET /v1/projects/{id}/revisions/{revision}/artifacts` → `{ok, revision, pin|null}`
- `POST /v1/projects/{id}/revisions/{revision}/artifacts/retain` → `200 {ok, pin}`
  (`after_save`), `404` if the revision or build dir is missing, `409` on
  pin conflict.

The diff is `diff_kicad_text` only. Caller-supplied filesystem paths are
never passed to `diff_kicad_files`.

## Cost

Every new revision reads and hashes at most the two KiCad files (one
schematic, one PCB), each capped at `max_kicad_content_bytes`. Identical
bytes are stored once: a blob whose digest already exists is a no-op.

## Limits

The structural diff matches items by uuid then geometry. A uuid-less item
that moves reads as removed + added.

Retention trusts the build directory root allow-list
(`HARDWARE_SPLICER_OUTPUT_ROOT` / `HARDWARE_SPLICER_BUILD_FILE_ROOTS`) and
does not defend against a build directory whose parent directory is swapped
to a symlink between the allow-list check and the read (local-attacker
TOCTOU), same as the build-files viewer. It does not make a build directory
immutable. See [`AGENT_BUILD_DIR_POLICY.md`](AGENT_BUILD_DIR_POLICY.md) /
`build_files_security.py`.

## Related

- [`MACHINE_PROJECT_SPINE.md`](MACHINE_PROJECT_SPINE.md) — revisions are immutable
- `src/hardware_splicer/artifact_retention.py`
- `src/hardware_splicer/project_artifact_api.py`
- `src/hardware_splicer/kicad_diff.py`
