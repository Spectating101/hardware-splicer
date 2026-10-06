# Candidate proposals

Hardware Splicer can apply a bounded list of KiCad edit operations to a
**retained** revision and open the result as a staged review. The edit is never
a write to a revision. The only durable writes are a candidate build directory,
a candidate record, and a review opened through the existing review store.

**Authority is never implicitly upgraded.** A candidate is a proposal. Accepting
its review promotes a snapshot to a revision the same way any other review
does. It does not mark anything verified, fabrication-ready, or release-ready.

## What is proposed, and from which bytes

`POST /v1/projects/{id}/candidates` loads the requested revision (or the latest
when `base_revision` is null), then reads the pinned schematic or PCB through
`read_pinned_artifact`. A revision with no pin for that kind is HTTP 409
`artifact_not_retained`. The service never falls back to the mutable build
directory.

`apply_edit_ops` transforms the pinned text. `KicadEditError` is HTTP 422
`invalid_edit` and never echoes file content. A structurally empty
`kicad_diff` is HTTP 422 `no_effective_change`.

The candidate snapshot is a deep copy of the base revision snapshot with every
build-dir key that `derive_snapshot_build_dir` reads pointed at the new
directory (`buildDir` and `build_dir` always; nested keys only where they were
already present). `ProjectReviewStore.create` then opens a pending review
against that snapshot.

## Identity

`author` is always required (string, 1–80 characters), including when the
caller presents a valid operator token. The token only overrides the stored
identity: `created_by` becomes the registry `id` with `verified: true`.
`Authorization` is ordinary app auth and is never treated as an operator token.
An invalid token is HTTP 401 `operator_token_invalid` with the same error shape
the thread API uses; the service never falls back to the self-declared name.

JSON bodies larger than 256 KiB are HTTP 413 `request_too_large` (Content-Length
and the streamed body are both capped). Each op string value is capped at 4096
characters. Edited and copied KiCad bytes are checked against
`max_kicad_content_bytes` before any candidate directory is created (HTTP 422
`artifact_too_large`).

## Layout

```text
<output_root>/candidates/<project_id>/<cand-xxxxxxxxxxxx>/
  <sanitised basename of the pin relative path>
projects/<id>/candidates/<cand-xxxxxxxxxxxx>.json
```

`candidate_id` is `cand-` plus 12 lowercase hex digits (`secrets.token_hex(6)`).
The pin relative is sanitised to a single basename: characters outside
`[A-Za-z0-9._-]` become `_`, the KiCad suffix is kept, the name is at most 120
characters, and two files that collapse to the same name are disambiguated.
Writes are create-only (`O_EXCL` + `O_NOFOLLOW` with a directory fd), mode
0600/0700. Intermediate directories are created one component at a time with
`os.mkdir` (never `parents=True`). Any symlink on the path from the output root
to the candidate directory is refused. `assert_build_dir_allowed` runs before
the directory is created.

The candidate directory path is recorded for cleanup before `os.mkdir`. Cleanup
removes that directory only when this call created it (`created=True` after a
successful `os.mkdir`). A pre-existing directory is never deleted;
`FileExistsError` retries with a new `candidate_id` (up to 5 times).

Orphan candidate directories (on disk, no record) older than one hour are
deleted at the start of a proposal. Remaining orphans count toward the 50 cap.
Proposals for one project are serialised with a process-wide refcounted lock
table around count + reserve + record write.

Any failure after the directory is created removes that directory and leaves no
record or review.

## Record

Schema `hardware_splicer.candidate.v1`:

| Field | Role |
|-------|------|
| `base_revision`, `kind`, `review_id` | Trace to the retained revision and the opened review |
| `created_by`, `verified` | Operator identity flag only |
| `note` | The proposer's stated reason, at most 500 characters; empty when none was given |
| `applied`, `warnings` | From `apply_edit_ops` |
| `edited_sha256`, `base_sha256` | Content hashes of the edited kind |
| `diff` | Structural `kicad_diff` of base vs edited |
| `checks` | Optional kicad-cli DRC/ERC counts |
| `authority` | Always `{state: proposal, note: …}` |

A project may retain at most 50 candidate records (HTTP 429
`too_many_candidates`). Stored records are capped at 512 KiB:
`applied[].detail` is truncated to 200 characters and `diff.changes` to 500
entries with `limits.truncated: true`.

## Reads

| Method | Path | Result |
|--------|------|--------|
| `GET` | `/v1/projects/{id}/candidates` | Records, newest first, cap 100 |
| `GET` | `/v1/projects/{id}/candidates/{candidate_id}` | One record, or 404 `not_found` |
| `GET` | `/v1/projects/{id}/candidates/{candidate_id}/files/{kind}` | `text/plain` bytes |

`candidate_id` must match `^cand-[0-9a-f]{12}$` before any path is built.
Served bytes are size-capped by `max_kicad_content_bytes`, re-hashed against
the record (mismatch → 500 `integrity_error`), and advertised with an ETag
from that sha256. Nothing outside the candidate directory is readable.

## Optional checks

When `kicad-cli` is available (`resolve_kicad_cli` / `capability_probe` from
`model3d.py`), the service runs `kicad-cli pcb drc --format json` or
`kicad-cli sch erc --format json` on the base bytes and the edited bytes.
`--exit-code-violations` is omitted, so a violations-found exit is not used;
any other nonzero status is a tool failure even if a JSON report file exists.
Each side is a mode-700 temp directory, `HOME` set to that directory, PATH-only
environment, and a bounded subprocess runner (reader threads keep an 8 KiB tail,
`killpg` on timeout, always reaped) with a 60s timeout. The JSON report is a
file the tool writes and is read with `max_kicad_content_bytes`. Counts come
from `violations`, `sheets[].violations`, `unconnected_items`, and
`schematic_parity` (the last two use those names as the type prefix when a row
has no `type`):

```text
{errors, warnings, total, by_type}
new_violations = sum over types of max(0, after[t] - before[t])
```

`checks.reason` is from a fixed vocabulary (`kicad-cli is not available`,
`kicad-cli timed out`, `kicad-cli failed`, `report could not be read`,
`report was too large`) with at most the exit code appended. Tool stdout/stderr
is never stored. A fixed violation cannot mask a new one. If `kicad-cli` is
missing or fails, `ran` is false with a reason and nothing is raised. Checks
never block, pass, or fail a candidate.

## Autoroute as a proposal

`POST /v1/projects/{id}/candidates` also accepts `{"kind": "pcb", "autoroute": {...}}` **instead of** `ops`
(the two cannot be combined, and autoroute applies to the PCB only). Options:

| Field | Default | Rule |
|-------|---------|------|
| `max_passes` | 20 | integer 1 to 50 |
| `keep_existing_tracks` | `true` | boolean; `false` lets the router remove existing tracks |

The router is [`routing_engine.py`](ROUTING_ENGINE.md). Its output goes through the same path as an edit: structural
diff, optional DRC counts, a new candidate directory and a pending review. The routing engine's own guards refuse a
result that changes anything but copper (placement, board setup, zone settings), and that refusal is HTTP 422
`routing_failed`. A server without FreeRouting answers HTTP 409 `routing_unavailable` with the text that says what to
install; nothing is created. A routed board is a proposal: it is not DRC-clean, verified or fabrication-ready until a
reviewer says so.

`GET /v1/projects/{id}/routing` reports whether routing can run here: `{available, reason, components}` with a version
per component and no filesystem paths.

## Previewing a draft

`POST /v1/projects/{id}/candidates/preview` takes the same `{base_revision, kind, ops}` as a proposal and returns
`{base_revision, kind, text, applied, warnings, diff}`: the edited file and its structural diff, computed by the same
read, edit and diff a proposal uses, so the answer matches what a proposal would hold.

It keeps nothing. No directory, record or review is created, no design-rule check runs, the proposal cap is untouched
and no token is needed. It refuses what a proposal would refuse (unknown reference, no effective change, no retained
file). Autoroute is not previewed, because routing is slow and a draft preview is meant to follow typing.

## Deciding a proposal

`POST /v1/projects/{id}/candidates/{candidate_id}/decision` with `{"decision": "accepted" | "rejected", "note": "..."}`
accepts or rejects the proposal's review through the existing review store.

- **A server-verified identity is required.** The `X-HS-Operator-Token` header must resolve to an operator. A missing
  token is HTTP 401 `operator_token_required`, an unknown one `operator_token_invalid`. A typed name is not enough, and
  an `actor` in the body is ignored: the decision is recorded under the operator's id. (The older
  `/reviews/{id}/decision` route still takes a self-declared actor; use the candidate route for proposals.)
- **Accepting is not approval of anything else.** It promotes the proposal's snapshot to the next revision exactly as
  any accepted review does, and the product API pins the proposed bytes to that revision. It marks nothing verified,
  fabrication-ready or release-ready. The candidate record is never rewritten by a decision.
- **A stale proposal cannot be accepted.** If a newer revision has landed since the proposal's base, the review is
  refused with HTTP 409 `revision_conflict`; propose again from the newer revision. A decision can be made only once
  (`review_conflict`).

`GET /v1/projects/{id}/candidates` and `.../candidates/{candidate_id}` also return `review_state`, read live from the
review store: `{status, decided_by, decided_at, note, accepted_revision, stale}`. `stale` is true for a pending proposal
whose base revision is no longer the latest.

## Request handling

Applying edits, routing and the design-rule checks take seconds. The create handler runs them on a worker thread so
the server keeps answering other requests and live event streams while a proposal is being built.

## What this service does not do

- write a revision, pin, thread, or review decision
- accept a review on its own: only a verified operator's explicit decision does
- talk to the network
- add a dependency
- use the words passed / approved about the candidate; `verified` is only the
  operator-identity flag

## Related

- [`MACHINE_PROJECT_SPINE.md`](MACHINE_PROJECT_SPINE.md) — staged review
- [`ARTIFACT_RETENTION.md`](ARTIFACT_RETENTION.md) — pinned bytes this service reads
- `src/hardware_splicer/project_candidates.py`
- `src/hardware_splicer/project_candidates_api.py`

## Authority invariants

1. A candidate is a proposal, not a revision.
2. Edits read retained pins only; they never fall back to a mutable build dir.
3. Opening a review does not accept it and does not upgrade a claim. Deciding it needs a verified operator.
4. Accepting that review later is the existing review-store decision; the
   candidate record is left unchanged.
5. Optional DRC/ERC counts are evidence for a reviewer, never a gate.
