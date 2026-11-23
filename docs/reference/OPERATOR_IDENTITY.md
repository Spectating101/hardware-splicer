# Operator identity for review threads

Review-thread authors may present a server-issued operator token. A verified
event means only that the author held a token issued by whoever controls the
local registry. It is still a comment. Authority is never upgraded.

This is not the HMAC file attestation in `physical_evidence_attestation.py`.
That attestation proves the service observed file bytes. `PhysicalEvidenceRecord.operator`
is unauthenticated text. Neither is an operator identity.

## What verification means

- The caller presented a token whose SHA-256 hash is in the registry.
- The stored author `{id, kind}` comes from that registry entry.
- The event records `author_verified: true` and `verified_by: "operator-token"`.
- The token and its hash are never stored on the event.

## What it does not mean

- Not a public-key identity, certificate, or signed statement.
- Not proof of a person, device, or lab session beyond possession of the token.
- Not an authority, release, review-accept, or fabrication grant.
- A missing token keeps today's client-declared author and `author_verified: false`.
- A supplied but unknown token fails closed (401). It never becomes unverified.

## Building the registry

Store only hashes. Never store the token. Registry hashes are only as strong as
the token's entropy: use `generate-token`. Do not hash passwords or short
secrets. A leaked registry file must be treated as exposing any guessable
low-entropy tokens that were hashed into it.

```bash
PYTHONPATH=src python -m hardware_splicer.operator_identity generate-token
```

That prints the token on the first line and `sha256:<64 hex>` on the second.
Stderr says `store the token with the operator; put only the hash in the registry`.

To hash an existing high-entropy token, pipe it to `hash-token`. The command
strips only one trailing newline (`\n` or `\r\n`) and nothing else — not spaces,
tabs, or further newlines.

```bash
printf '%s' "$TOKEN" | PYTHONPATH=src python -m hardware_splicer.operator_identity hash-token
```

Put the mapping in `HARDWARE_SPLICER_OPERATOR_TOKENS` (JSON object). The file
named by `HARDWARE_SPLICER_OPERATOR_TOKENS_FILE` is used only when that env
var is absent (the key is not in the environment). If the key is present but
empty or whitespace, the registry is not configured — fail closed; a
misconfigured environment must not activate stale file credentials. A valid
JSON env value takes precedence over the file.

```json
{
  "sha256:0123…64 hex…": {"id": "alice", "kind": "human"}
}
```

`id` is 1–120 characters with no leading or trailing whitespace and no control
characters. `kind` must be exactly `human` or `agent` — it is not stripped or
case-folded.

## Using the token

On `POST /v1/projects/{id}/threads` and `POST …/events`:

- Header `X-HS-Operator-Token: <token>` only. `Authorization` is app auth
  (the Next.js UI proxy forwards `Authorization: Bearer <app API key>`) and is
  ignored for operator identity.
- Absent `X-HS-Operator-Token`: client-declared author, unverified.
- Valid token: registry author wins. A conflicting body author is 422
  `invalid_request`. An absent or matching author is accepted.
- Unknown token: 401 `operator_token_invalid`. Nothing is written.
- Missing or corrupt registry: 503 `operator_registry_error`.

## Rotation

Remove the hash from the registry to revoke that token. Add a new hash to issue
a replacement. Overlapping hashes are allowed during a hand-off.

## Limits

- Tokens are compared as SHA-256 hex with `hmac.compare_digest`.
- The registry is local configuration, not a directory service.
- Position anchors (`x_mm`, `y_mm`) are a LOCATION, never an object identity,
  and may only accompany an artifact.
- A pin is drawn only while the viewer is showing the exact revision recorded
  by its anchor. Threads from other revisions remain visible in the discussion
  history, but their coordinates are not projected onto the current artifact.
