# Circuit-AI Monetization Quickstart (API + MCP)

This repo supports **2-tier monetization** (free/paid) via **API keys + daily quotas**, designed for MCP and CI usage.

## 1) Enable API keys (backend)

Set an admin token and (optionally) require keys:

```bash
export CIRCUIT_AI_ADMIN_TOKEN="change_me_admin_token"
export CIRCUIT_AI_REQUIRE_API_KEY="true"
python3 api_server.py
```

Auth is accepted as:
- `Authorization: Bearer <API_KEY>`
- `X-API-Key: <API_KEY>`

## 2) Issue keys (free vs paid)

### Issue a free key

```bash
curl -sS -X POST http://localhost:5000/api/v2/admin/keys/issue \
  -H "Authorization: Bearer $CIRCUIT_AI_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan":"free","label":"demo-free"}'
```

### Issue a paid key

```bash
curl -sS -X POST http://localhost:5000/api/v2/admin/keys/issue \
  -H "Authorization: Bearer $CIRCUIT_AI_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan":"paid","label":"demo-paid"}'
```

The response returns `api_key` once. Store it somewhere safe.

### Default 2-tier quotas (per key / per day)

- `free`
  - `validate_kicad`: 10/day
  - `manufacture_bom`: 0/day
  - `manufacture_gerber`: 0/day
- `paid`
  - `validate_kicad`: 200/day
  - `manufacture_bom`: 50/day
  - `manufacture_gerber`: 25/day

You can also create fully custom quotas with `POST /api/v2/admin/keys` by passing a `quotas` object.

## 3) Use the key (API)

```bash
curl -sS http://localhost:5000/api/v2/usage \
  -H "Authorization: Bearer YOUR_API_KEY"
```

If you exceed quota, endpoints return `429` with `{"error":"quota_exceeded", ...}`.

## 4) Use the key (MCP)

Set these env vars for the MCP server:

- `CIRCUIT_AI_API_URL` (default `http://localhost:5000`)
- `CIRCUIT_AI_API_KEY` (the issued key)

Example:

```json
{
  "mcpServers": {
    "circuit-ai": {
      "command": "node",
      "args": ["/path/to/Circuit-AI/mcp_server/dist/index.js"],
      "env": {
        "CIRCUIT_AI_API_URL": "http://localhost:5000",
        "CIRCUIT_AI_API_KEY": "cai_..."
      }
    }
  }
}
```

## 5) Use the key (CAD demo UI)

The Next.js proxy routes support:
- `CIRCUIT_AI_API_URL`
- `CIRCUIT_AI_API_KEY`

For local dev:

```bash
export CIRCUIT_AI_API_URL="http://localhost:5000"
export CIRCUIT_AI_API_KEY="cai_..."
cd circuit-ai-frontend
npm run dev
```

Open `http://localhost:3000/cad`.

