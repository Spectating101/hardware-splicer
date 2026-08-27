# Stored Source Parser

Hardware Splicer can now execute bounded parsers against files already registered in a revisioned project.

The parser boundary does not trust filenames or caller-supplied digests. It reopens the project-scoped content-addressed blob, verifies SHA-256 again, applies only an explicitly registered parser route, and persists JSON output without placing raw file bytes in the project snapshot.

## Canonical routes

- `GET /v1/engineering/sources/parser/schema`
- `POST /v1/projects/{project_id}/sources/{source_id}/parse`
- `PATCH /v1/projects/{project_id}/sources/{source_id}/role`

The frontend proxies are:

- `POST /api/proxy/engineering/projects/{projectId}/sources/{sourceId}/parse`
- `PATCH /api/proxy/engineering/projects/{projectId}/sources/{sourceId}/role`

Both mutations require the current `expected_revision`. Stale writes return a conflict before parser execution or role mutation.

## Parser execution

### Robot models

Registered URDF, SDF and MJCF files use the existing bounded `robot_model_import` parser.

A successful run persists:

- parsed model identity and format;
- links, joints and declared actuators;
- a candidate robot topology;
- unresolved topology and calibration requirements;
- summary counts and parser limitations.

The parser output remains declared candidate design evidence. It does not prove:

- physical fit;
- calibration;
- actuator ratings;
- payload capacity;
- safe motion;
- fabrication or release readiness.

When a project plan is generated, a successfully parsed robot source is reopened and hash-verified again. Its XML is supplied ephemerally to the canonical planner and is not written into the saved project revision.

### Engineering source JSON

A valid JSON file may be parsed when it contains:

- one source descriptor;
- an array of source descriptors;
- an `engineering_sources` array;
- a `sources` array.

Nested source and claim authority is capped by the uploaded parent source. An uploaded file at `declared` authority cannot introduce `measured`, `verified` or `authorized` claims through JSON.

Derived descriptors are stored separately as `engineeringParsedSources` and join the project planning boundary on the next guided plan.

### STEP

STEP remains explicit hash-verified inventory in this build.

Although ingestion can identify a STEP file and assign the intended `step_geometry` route, no callable bounded STEP parser was found in the current codebase. Parser execution therefore returns `skipped` with `parser_available: false`. It does not invent geometry, envelope or BREP results.

### Inventory-only formats

PDF, image, video, archive, KiCad, firmware, CSV, text and unknown binary sources remain inventory-only unless a separate bounded parser is registered.

## Source role correction

A user may correct `source_type` and may preserve or reduce `authority_ceiling`.

The correction route cannot:

- increase authority;
- change `source_id`;
- change URI;
- change revision or content hash;
- change blob identity;
- authorize any physical action.

Every correction appends a role-history record and creates a new optimistic project revision.

## Source Lab

`/engineering/source-lab` provides an ordinary-user interface to:

- load a project and current revision;
- inspect registered source identities and parser routes;
- execute bounded parsers;
- inspect persisted parser output;
- correct source roles;
- reduce authority ceilings;
- move to project planning or Project inspector.

## Persisted project fields

This tranche adds or uses:

- `engineeringSources` — immutable registered source descriptors plus bounded role metadata;
- `engineeringSourceUploads` — upload and storage audit records;
- `engineeringSourceParserRuns` — parser status, output and limitations;
- `engineeringParsedSources` — authority-bounded descriptors derived from parsed source files.

Raw file content is not placed in any of these fields.

## Authority boundary

Parser execution and role correction never grant:

- fabrication authority;
- firmware flashing authority;
- power-on authority;
- motion authority;
- operational authority;
- release authority.

A successful parser run proves only that the registered bytes matched their stored hash and were accepted by one bounded software parser.

## Remaining work

- A real bounded STEP parser or explicit removal of the route label.
- Multipart or streaming transport instead of base64 JSON upload.
- Resumable sessions and aggregate upload ceilings.
- Orphan-blob reports and garbage collection.
- Browser tests against a running backend.
- Bounded parsers for selected KiCad, PDF or telemetry formats.
