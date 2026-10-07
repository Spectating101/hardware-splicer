# Review packet

A review packet is what a reviewer was shown for one revision of a project, in one document that can be handed to someone
else and checked. It is the artifact for an outside pilot, an audit, or a design review that should not rest on a
screenshot.

**It reports. It does not decide.** Building a packet reads the project and changes nothing. It never opens fabrication,
power-on or release, and it says so in the packet itself.

## What is in it

| Section | Contents |
|---------|----------|
| `project` | id, name, revision, when that revision was saved, and the SHA-256 of its snapshot |
| `retained_files` | the schematic and PCB the revision kept, with their SHA-256, or the reason there are none (`not_retained`, `unreadable`). Hashes are never invented |
| `findings` | every finding with how it was established (`kind`, `basis`, `source_ref`, `authority_ceiling`) and whether the server attested it, plus counts by category and by how established |
| `proposals` | proposals based on this revision: who proposed (and whether their identity was confirmed), why, what operations, the design-rule counts, and each decision with who made it |
| `discussion` | threads with their comments, and for each author whether the server confirmed who they were or it is a name someone typed |
| `not_established` | what this packet does not show, in plain words |
| `authority` | a statement that the packet opens and implies no fabrication, power-on or release authority |
| `integrity` | the SHA-256 of the canonical JSON of every other field |

## Properties

- **Deterministic.** The same project state gives the same bytes. There is no clock reading in it, so two people holding
  the same packet can tell they hold the same thing. A change to the project changes the hash.
- **Self-checking.** `verify_review_packet` recomputes the hash. The hash covers every field, including the statement of
  how it was computed; only the digest itself is left out. The `integrity` block must hold exactly an `algorithm` and a
  `packet_sha256`, and the algorithm must be the one this module states, so nothing in that block can be used to carry text.
- **Read-only.** It uses the plain project loader, so asking for a packet never repairs, renames or rewrites anything,
  even for a damaged store. It falls back to the newest valid revision.
- **Text people wrote is untrusted.** Names, notes, comments and finding text are escaped in the document so they read only
  as the words they are. A project name or comment cannot start a heading, forge an "Accepted" decision, add a link, inject
  HTML or pose as the document's hash. The JSON carries the text as written (after redaction).
- **Credentials and absolute paths are removed, best effort.** Bearer tokens, `sk-` and `ghp_` style keys, AWS and Slack key
  ids, JWTs, private key blocks, `key=value` secrets, and absolute paths (`/home/…`, `/tmp/…`, `C:\…`) in free text are
  replaced with `[redacted credential]` or `[redacted path]` **before** the hash is taken. `redactions` says how many were
  removed and of what kind. A pattern list cannot catch everything: do not write secrets in comments and rely on this.
  Operator tokens are not stored in the project and never appear.
- **Nothing is cut silently.** Every list that can be cut short says so in both forms, with how many there were and how
  many are shown: findings (1000), threads (100), entries per thread (50), operations per proposal (20) and proposals (100).
- **Bounded reads.** The discussion store re-checks every event file on every read, so a very large discussion is not
  read. Threads and events are counted by name first, and if there are more than 100 threads or 2000 events the packet
  says the discussion was left out, how large it was, and why.

## API

`GET /v1/projects/{id}/review-packet?revision=N&format=json|markdown`

- `revision` defaults to the latest valid revision; an unknown one is HTTP 404.
- `format=json` returns `{ok, packet}`. `format=markdown` returns the same content as a document to read, with a
  download file name `<project>-r<revision>-review-packet.md`.
- Any other `format` is HTTP 422 `invalid_request`.

## What a packet is not

- Not an approval. Accepting a proposal and recording a comment are recorded as what they are.
- Not proof about the physical board. The `not_established` section says so every time.
- Not a substitute for the project's own gates.
