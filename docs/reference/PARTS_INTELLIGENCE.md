# Parts intelligence for a retained schematic revision

`GET /v1/projects/{project_id}/revisions/{revision}/parts` lists the components
and BOM groups a **pinned** schematic actually carries. It never upgrades an
engineering claim, never guesses an MPN from Value or `lib_id`, and never
implies a part is in production or in stock beyond a provider record's
`source` + `as_of`.

Authority is never implicitly upgraded. A functional analogy does not inherit
an electrical contract. Availability is a time-sensitive claim.

## What is extracted, and from where

Reads go through `read_pinned_artifact` only. There is no live build-dir path
and no caller-supplied file.

| Field | Source |
|-------|--------|
| `ref`, `uuid`, `value`, `lib_id`, `footprint` | Placed schematic symbol (strict KiCad tokenizer in `kicad_diff`) |
| `dnp`, `in_bom`, `on_board` | Symbol flags as written (`dnp` default no, `in_bom`/`on_board` default yes) |
| `properties` | Every `property` on the instance, as written |
| `mpn` / `mpn_source` | Explicit property only (see below) |
| `manufacturer`, `lcsc` | Explicit property only |
| `datasheet` | Instance `Datasheet` if it is an `http(s)` URL or a file name; otherwise the matching `lib_symbols` definition in the same file, same rule. `~` is null. |

BOM groups are keyed by `(value, footprint, mpn, lcsc, dnp)`. Each group keeps
`manufacturer` when every member carries the same explicit property (never
guessed). Refs are sorted naturally (`R2` before `R10`). Groups excluded from
the BOM (`in_bom` no) are still listed and marked `not_in_bom`. Summary counts
components, groups, unique MPNs, missing-MPN groups, DNP components, and
excluded components.

## Why MPN is never guessed

Value and `lib_id` are labels, not manufacturer part numbers. Filling `mpn`
from them would invent identity. `mpn` is set only when a symbol property
matches one of these names (case-insensitive): `MPN`,
`Manufacturer_Part_Number`, `Mfr Part`, `Manufacturer Part Number`.
`mpn_source` is then `property:<name as written>`. Manufacturer accepts
`Manufacturer` / `MFR`. LCSC accepts `LCSC`, `LCSC Part`, `JLCPCB Part`.
A symbol without those properties has `mpn` null and the group
`missing_mpn: true`.

## Provider contract

`PartsProvider.lookup({mpn?, lcsc?, manufacturer?}, *, timeout_s)` returns a
record or `None`. A record always carries `source` and `as_of` (ISO UTC).
`lifecycle` is only `active` / `nrnd` / `obsolete` / `unknown` when the
provider says so. Stock, price breaks, datasheet URL, package, and
alternates are likewise copied, never invented.

Enabled providers, in order, from `parts_providers_from_env()`:

1. **OfflineCatalogProvider** (`hardware-splicer-catalog`) — repo
   `module_registry` / `engine_pcb_data.json` plus catalog recipes. A match
   requires an MPN or LCSC identity; manufacturer never identifies a part.
   A stated manufacturer on the query must equal a stated manufacturer on the
   catalog record; a catalog row with no manufacturer matches only when the
   query also omits manufacturer. Datasheet URLs, package hints, and
   same-family alternates only where that data states them. `source` is
   `hardware-splicer-catalog`; `as_of` is the UTC mtime of those catalog files.
2. **JlcEnrichProvider** (`jlcsearch`) — only when
   `HARDWARE_SPLICER_JLC_ENRICH` is exactly `1`, `true`, or `yes`
   (case-insensitive). Absent, empty, and `0` leave it disabled. Adapts the
   existing `enrich_bom_with_jlcsearch` path with a hard timeout. A
   `jlc_enriched=True` flag is not itself part data: the provider returns
   `None` (BOM status `no_data`) unless lifecycle, stock, price, datasheet,
   alternates, package, or LCSC/MPN was actually returned. LCSC and returned
   MPN are copied onto the provider record (`lcsc`, `mpn_returned`) and appear
   only under `availability.records` — they never overwrite the group's design
   `mpn`/`lcsc`. `source` is always `jlcsearch`; `as_of` is the lookup time.
   Any failure returns `None`.

`enrich_bom` consults providers per distinct `(mpn, lcsc, manufacturer)` and
ordered provider set (class name + declared source name) with a 15-minute
in-memory TTL cache and passes the design's explicit manufacturer in the query. A provider record without a non-empty `source` and a parseable
ISO-8601 `as_of` is dropped; if nothing remains, status is `lookup_failed`
with note `provider returned a record without source and date` — the provider
name and wall-clock time are never substituted. The first provider that
supplies a field wins that field; every consulted valid record is listed.
Failures never raise: status `lookup_failed` with a short path-free reason.
No identifier → `not_checked`. Beyond `max_lookups` (default 50) →
`not_checked` with note `lookup limit reached`. Statuses: `not_checked`,
`checked`, `lookup_failed`, `no_data`.

Lookups share one module-level executor (`max_workers=4`). Python cannot kill
a running provider thread, so that bound is concurrency, not lifetime;
not-yet-started futures are cancelled on timeout. After three consecutive
timeouts or exceptions a provider is skipped for 60 seconds (`lookup_failed`
with reason `provider temporarily skipped after repeated failures`).

## HTTP

`GET /v1/projects/{project_id}/revisions/{revision}/parts?enrich=false`

- No retained schematic: HTTP 200 `{ok:true, available:false, reason}` — not an error.
- Present: `{ok, project_id, revision, available:true, source:{relative, sha256, retention_basis}, summary, components, bom_groups, enrichment}`.
- `enrich=true` runs lookups **only** when at least one provider is enabled;
  otherwise `enrichment.performed` is false and a reason is set. Lookups run
  off the event loop.
- Malformed schematic: HTTP 422 `{detail:{type:"parts_extract_error"}}`.
- Other errors use the existing project error contract.

The handler does not write project bytes.

## Privacy

Enrichment sends MPN, LCSC, and manufacturer identifiers to a provider **only**
when `enrich=true` and a provider is enabled. `enrich=false` never calls a
provider. The offline catalog stays in-process. JLC/LCSC enrichment is
network-capable and is enabled only for `HARDWARE_SPLICER_JLC_ENRICH` of
`1`/`true`/`yes`.

## Limits

- Same schematic size cap as artifact retention (`max_kicad_content_bytes`).
- Provider timeout default 5s; lookup cap 50 distinct `(mpn, lcsc, manufacturer)` keys.
- Shared lookup executor: 4 worker threads (concurrency bound, not lifetime).
- Provider circuit breaker: 3 consecutive failures, 60s skip.
- Cache TTL 15 minutes, process-local.
- Availability never outlives `as_of`.

## Related

- [`ARTIFACT_RETENTION.md`](ARTIFACT_RETENTION.md) — pins and `read_pinned_artifact`
- [`MACHINE_PROJECT_SPINE.md`](MACHINE_PROJECT_SPINE.md) — revisions are immutable
- `src/hardware_splicer/parts_intel.py`
- `src/hardware_splicer/project_parts_api.py`
