# Canonical Hardware-Splicer backend over MCP

**Status:** isolated integration experiment based on frozen HS head `8d687da6e29e110bdc969d9632385f3f31239e5c`.

This surface exists to answer a simple product question:

> Can an arbitrary MCP-capable agent discover and exercise the same canonical Hardware-Splicer backend that the product UI and HTTP clients use, without a second hand-maintained backend or a weaker authority model?

## Why a second MCP entrypoint exists

The historical `hs-mcp` / `hardware_splicer.mcp_server` surface predates the current canonical product backend. It exposes a large set of compile-engine and salvage wrappers directly through `hardware_splicer.sdk`.

That is useful compatibility surface, but it is no longer a complete description of Hardware-Splicer. The canonical `product_api` now mounts durable project state, source ingestion/storage/parsing, project planning, AI orchestration and repair, source-blind cleanroom evaluation, capability reuse/economics, manufacturing/mechanical closure, revision/status/review, and revision-bound physical-evidence surfaces in addition to the older engine routes.

A hand-maintained MCP list can therefore become stale even while the HTTP backend remains healthy.

## Canonical approach

`hs-backend-mcp` derives discovery from the actual FastAPI OpenAPI document produced by `hardware_splicer.product_api`.

The MCP surface intentionally stays small:

- `hs_backend_status` — report the canonical backend contract and operation counts;
- `hs_backend_list_operations` — discover operations by method, tag, path prefix, or text;
- `hs_backend_describe_operation` — return one exact OpenAPI operation plus all referenced schemas;
- `hs_backend_call` — invoke that operation through the same in-process ASGI application.

The gateway is not an arbitrary HTTP proxy. `hs_backend_call` accepts only an `operation_id` currently present in canonical OpenAPI.

## Agent workflow

A generic agent should be able to operate without repository-specific Python imports:

```text
initialize MCP
    ↓
hs_backend_status
    ↓
hs_backend_list_operations
    ↓
hs_backend_describe_operation
    ↓
hs_backend_call
    ↓
inspect returned canonical state/evidence
    ↓
repeat
```

The server creates one canonical FastAPI application for the lifetime of the MCP process so sequential calls share the same backend/store context.

## Install and run

```bash
python -m pip install -e '.[mcp]'
hs-backend-mcp
```

Equivalent module invocation:

```bash
python -m hardware_splicer.backend_mcp_server
```

Example MCP client configuration:

```json
{
  "mcpServers": {
    "hardware-splicer-backend": {
      "command": "hs-backend-mcp",
      "args": []
    }
  }
}
```

## Request mapping

`hs_backend_call` supports:

- path parameters;
- query parameters;
- JSON bodies;
- form bodies;
- multipart uploads using base64-encoded file bytes.

Multipart file object:

```json
{
  "field": "files",
  "filename": "datasheet.pdf",
  "content_base64": "...",
  "content_type": "application/pdf"
}
```

For responses:

- JSON is returned as JSON;
- text is returned as text;
- binary responses default to metadata (`byte_length`, SHA-256, content type) so a large artifact is not dumped into model context accidentally;
- set `response_mode=base64` when binary bytes are actually required;
- set `response_mode=metadata` to suppress all response bodies.

## Truth and authority boundary

MCP owns no engineering truth.

The gateway does not duplicate or override:

- project/revision identity;
- evidence provenance;
- deterministic verification;
- source authority;
- physical evidence;
- fabrication/flashing/power/motion/operation/release gates;
- human authorization.

Every invocation re-enters the canonical FastAPI handler. If the backend requires a revision, evidence packet, explicit `simulated:false`, physical envelope, or human authorization decision, MCP must satisfy the same requirement. The adapter cannot promote an MCP model response into physical truth.

## Contract test

`tests/test_mcp_backend_gateway.py` requires the gateway catalog to equal the complete canonical OpenAPI `{method, path}` set. This prevents a newly added backend route from silently remaining invisible to MCP.

`.github/workflows/mcp-backend-contract.yml` then performs a real protocol smoke test:

1. install package + MCP SDK;
2. verify OpenAPI/MCP coverage;
3. launch the backend MCP server over stdio;
4. initialize an MCP client session;
5. discover the four gateway tools;
6. discover a real canonical route;
7. describe its request contract;
8. invoke it through MCP;
9. assert no MCP authority grant.

## What this test proves if green

It proves that the canonical backend is mechanically discoverable and callable through MCP and that MCP coverage tracks canonical OpenAPI.

It does **not** prove:

- every business workflow is usable by a naive model;
- live provider competence;
- physical correctness;
- independent-operator success;
- commercial usability;
- remote authentication/deployment security;
- that every possible multipart/binary workflow has been independently exercised.

Those are separate evidence layers.

## Stronger future agent gauntlet

After the protocol contract is green, a stronger black-box agent test can give an agent only the MCP server plus a mission and score whether it can:

1. discover the relevant backend operations;
2. create/resume project state;
3. ingest/inspect evidence;
4. obtain a bounded proposal;
5. preserve unresolved identity;
6. observe deterministic failures;
7. request repair without bypassing review;
8. inspect status/authority;
9. export a package;
10. refuse to claim physical authority without required evidence.

That should be treated as an agent-usability experiment, not as a reason to add MCP-specific golden routes.
