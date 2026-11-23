# Project live events and presence

Reviewers can watch a project without polling the snapshot. The live change
stream and presence records are **information only**. They never change a
snapshot, revision, review, thread, pin, or authority field, and nothing is
gated on who is present. Authority is never implicitly upgraded.

The `presence/` directory under a project is ephemeral collaboration state. It
is excluded from project byte-invariance: hashing or comparing a project tree
must skip `presence/`.

## Why filesystem-derived

Stores already write revisions (`revisions/NNNNNNNN.json`), review threads
(`threads/<id>/events/NNNNNNNN.json`), staged reviews
(`reviews/<id>/events/NNNNNNNN.json`), and artifact pins
(`artifact_pins/NNNNNNNN.json`). The change stream does not keep an in-process
pub/sub. Each poll lists those directories by **file name only** — it does not
read snapshot bytes — and diffs the resulting counters.

That stays correct across processes and workers: whoever wrote the durable
record, every API process sees the same tree. Partial writes, junk names, and
symlinks are ignored.

## Frames

`GET /v1/projects/{project_id}/events` is `text/event-stream`.

1. First frame: `event: hello` with `{project_id, revision, thread_count,
   review_count, server_time, poll_seconds}`.
2. Later: `event: change` with `{changes, server_time}` whenever the listing
   differs. Each change is `{type, id, seq}` where `type` is one of
   `revision.saved`, `thread.created`, `thread.event`, `review.opened`,
   `review.event`, `artifact.pinned`. Frames carry ids and counters only;
   clients re-fetch bodies through the existing project, thread, review, and
   artifact routes.
3. Comment `: keepalive` at least every 15 seconds (override with
   `HARDWARE_SPLICER_EVENT_KEEPALIVE_SECONDS`).

The generator ends after 30 minutes (`HARDWARE_SPLICER_EVENT_MAX_SECONDS`,
default 1800, clamp 0.2–1800) so clients reconnect and receive a fresh
`hello`. It also ends when the client disconnects.

Poll interval: `HARDWARE_SPLICER_EVENT_POLL_SECONDS` (default 1.0, clamp
0.05–10). Directory listings run in a worker thread so the event loop is not
blocked. Per-project concurrent stream cap:
`HARDWARE_SPLICER_EVENT_MAX_STREAMS` (default 50) returns 429
`{detail:{type:"too_many_streams", message}}`. Unknown projects are 404 like
the other project routes. Headers: `Cache-Control: no-cache`,
`X-Accel-Buffering: no`. No new auth.

## Presence

`POST /v1/projects/{project_id}/presence` upserts `presence/<client_id>.json`
via mkstemp, fsync, and `os.replace`. Body: `client_id`
(`^[A-Za-z0-9_-]{8,64}$`), optional `name` (≤80, no control chars), optional
`object_id` (≤200), optional `mode` in `review|compare|verify|bringup|other`.
Unknown keys and authority-ish keys (`authority`, `release`, `fabrication`,
`power_on`, `authorized…`) are 422 `invalid_request`.

A valid `X-HS-Operator-Token` stores the registry `{id, kind}`, `verified:
true`, and uses the registry id as `name` even when the body name conflicts.
An invalid token is 401; a registry error is 503 — same contract as review
threads. Without a token the name is self-declared and `verified` is false.
Self-declared names are not an identity.

`GET` lists participants seen within
`HARDWARE_SPLICER_PRESENCE_TTL_SECONDS` (default 45, clamp 5–600), sorted by
`client_id`, at most 100 rows. Entries older than 10× TTL are deleted
opportunistically on GET. `DELETE …/presence/{client_id}` is idempotent 200.
At most 200 presence files per project (429 `too_many_presence` beyond).
That file cap is a **soft bound across processes**: concurrent writers can
briefly exceed it. Presence is ephemeral information and gates nothing.
Symlinks are not followed.

Presence is not an audit log. It expires. It must not be used as evidence,
authorization, or a gate.

Filesystem checks for presence and the live stream refuse symlinks at check
time. They are not immune to a concurrent local swap by someone who can
already write the project directory — the same threat model as the rest of
the project store.

## Limits

| Limit | Default |
|-------|---------|
| Event poll | 1.0 s (0.05–10) |
| Keepalive | 15 s |
| Stream lifetime | 30 min |
| Concurrent streams / project | 50 |
| Presence TTL | 45 s (5–600) |
| Presence files / project | 200 |
| Presence list size | 100 |
