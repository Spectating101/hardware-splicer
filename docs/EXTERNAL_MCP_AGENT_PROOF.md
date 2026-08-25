# External MCP Agent Proof

## Purpose

Hardware-Splicer should be able to serve as a model-neutral engineering/evidence substrate.
The reasoning model is outside HS; HS owns canonical project state, deterministic checks,
evidence handling, revision truth, and physical-authority gates.

This tranche tests that boundary without changing the frozen unseen SPI corpus or silently
turning model prose into physical evidence.

```text
external model / agent
        |
        | MCP
        v
hs-backend-mcp
        |
        v
canonical product_api handlers
        |
        +-- project + revision state
        +-- evidence + deterministic verification
        +-- physical-authority gates
        |
        v
Engineering Package / bounded next actions
```

The canonical MCP gateway remains four stable tools:

1. `hs_backend_status`
2. `hs_backend_list_operations`
3. `hs_backend_describe_operation`
4. `hs_backend_call`

The model discovers the actual current product API through those tools. There is no second
hand-maintained engineering implementation.

## Claim boundary

A successful remote-agent run can prove that an external model genuinely operated HS through
the MCP boundary and produced a persisted tool trace. It does **not**, by itself, prove:

- that the model's engineering result is correct;
- physical correctness of the proposed adapter;
- fabrication readiness or power-on readiness;
- independent human-operator success;
- production deployment security;
- physical authority.

The frozen evaluator must adjudicate model competence separately. Revision-bound real bench
measurements must adjudicate physical correctness separately.

## 1. Install the canonical MCP surface

```bash
python -m pip install -e '.[dev,backend-mcp]'
```

The existing stdio contract remains the default:

```bash
hs-backend-mcp
```

## 2. Prove Streamable HTTP locally first

No model key is needed for this leg.

```bash
python scripts/smoke_backend_mcp_http.py
```

The smoke launches `hs-backend-mcp` on an ephemeral localhost port with a temporary isolated
`HARDWARE_SPLICER_PROJECT_ROOT`, connects with a real MCP v2 HTTP client, discovers the gateway,
describes a canonical project operation, performs a project write/read/delete cycle, and checks
that MCP itself grants no physical authority.

This leg is also part of `.github/workflows/mcp-backend-contract.yml`.

## 3. Run a guarded local experiment endpoint

Remote-capable mode is intentionally opt-in. Do not point it at a normal development project
store.

```bash
export HARDWARE_SPLICER_PROJECT_ROOT="$PWD/.proof-state/external-mcp"
export HS_MCP_TRANSPORT=streamable-http
export HS_MCP_REMOTE_EXPERIMENT=1
export HS_MCP_HOST=127.0.0.1
export HS_MCP_PORT=8000
hs-backend-mcp
```

The private local endpoint is then:

```text
http://127.0.0.1:8000/mcp
```

Keep HS bound to loopback unless there is a concrete reason not to. The preferred OpenAI reachability
path is **Secure MCP Tunnel** when it is available to the Platform organization: the customer-run
`tunnel-client` makes an outbound connection to OpenAI and forwards requests to the localhost/private
MCP server, so HS itself does not need public ingress.

Secure MCP Tunnel availability and permissions are organization/account dependent. If it is not
available, use an authenticated HTTPS tunnel/reverse proxy as the fallback; never publish the bare
mutable MCP endpoint directly to the Internet.

For a direct non-local bind or a reverse proxy that preserves a public Host header, explicitly allow
only the expected hostname:

```bash
export HS_MCP_ALLOWED_HOSTS='mcp.example.com,mcp.example.com:*'
```

Browser origins, if ever required, are separately allowlisted:

```bash
export HS_MCP_ALLOWED_ORIGINS='https://app.example.com'
```

A direct non-local bind is refused unless `HS_MCP_ALLOWED_HOSTS` is configured.

## 4. Run the external OpenAI agent

The experiment harness uses the OpenAI Responses API MCP tool. It sends the model only:

- the frozen product-visible unseen SPI snapshot;
- the experiment project id;
- operating rules that preserve unresolved evidence and physical authority;
- the four canonical HS MCP gateway tools.

It does **not** provide HS source code or evaluator internals.

### Preferred: OpenAI Secure MCP Tunnel

After a Secure MCP Tunnel has been provisioned and its `tunnel-client` is connected to the local HS
MCP endpoint, give the Responses API the tunnel id directly:

```bash
export OPENAI_API_KEY='...'
export HS_MCP_TUNNEL_ID='tunnel_...'
python scripts/run_external_mcp_agent_proof.py \
  --model gpt-5.6
```

The harness sends `tunnel_id` in the MCP tool definition and stores only a SHA-256 of the tunnel id
in the proof manifest.

### Fallback: authenticated HTTPS MCP endpoint

```bash
export OPENAI_API_KEY='...'
export HS_MCP_SERVER_URL='https://mcp.example.com/mcp'
python scripts/run_external_mcp_agent_proof.py \
  --model gpt-5.6
```

If the authenticated endpoint expects HTTP headers, read them from environment variables so the
proof artifacts contain only header names and value sources, never secret values:

```bash
export MCP_CLIENT_ID='...'
export MCP_CLIENT_SECRET='...'
python scripts/run_external_mcp_agent_proof.py \
  --server-url 'https://mcp.example.com/mcp' \
  --header-env 'CF-Access-Client-Id=MCP_CLIENT_ID' \
  --header-env 'CF-Access-Client-Secret=MCP_CLIENT_SECRET'
```

Provide exactly one locator: `--tunnel-id`/`HS_MCP_TUNNEL_ID` or
`--server-url`/`HS_MCP_SERVER_URL`.

The script sets `store=false` on the Responses API request and does not persist the OpenAI API key,
Secure MCP Tunnel id in clear text, or MCP header values.

## 5. Persisted evidence

Each run creates a timestamped directory under `artifacts/external-mcp-agent/` containing:

- `MISSION.json` — exact product-visible unseen snapshot;
- `REQUEST_MANIFEST.json` — HS git head, requested model, project id, hashes, MCP tool allowlist,
  redacted locator metadata, and header provenance;
- `OPENAI_RESPONSE.json` — exact Responses API result including MCP calls/tool outputs returned by
  the provider;
- `RUN_SUMMARY.json` — transport/gateway traversal summary and explicit nonclaims.

The summary deliberately leaves `live_unseen_competence` as `UNADJUDICATED`. A model using all
four gateway tools without transport failure proves external MCP operation, not engineering
correctness.

## 6. Frozen proof sequence

Use this order:

1. freeze exact HS/evaluator/corpus SHA;
2. run and preserve the no-key Streamable HTTP contract proof;
3. expose only the isolated experiment store through Secure MCP Tunnel when available, otherwise an
   authenticated remote endpoint;
4. run one external model against the unchanged mission;
5. persist the complete response/MCP trace;
6. run the frozen unseen evaluator without changing the case after seeing the result;
7. physicalize the exact resulting candidate if appropriate;
8. collect revision-bound real measurements and failure/repair history;
9. run an independent human operator;
10. update paper/product/gauntlet claims only from those canonical artifacts.

A failure in steps 4-9 is evidence. Do not alter the unseen case merely to obtain a passing run.
