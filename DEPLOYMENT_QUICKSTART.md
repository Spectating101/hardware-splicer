# Circuit-AI Deployment Quickstart (Backend + MCP)

This is the simplest way to deploy Circuit-AI for **paid MCP access**:

- Backend (Flask): hosted (Railway/Render/Fly/any Docker host)
- MCP server: users run locally in Claude Desktop/VSCode and point to your backend URL

## 1) Deploy the backend (Docker)

### Required env vars

- `CIRCUIT_AI_ADMIN_TOKEN` (secret): enables admin key issuance endpoints
- `CIRCUIT_AI_REQUIRE_API_KEY=true`: require keys for usage endpoints
- `CIRCUIT_AI_USAGE_DB=/data/circuit-ai-usage.sqlite`: persist keys + daily usage

If your host supports persistent volumes, mount a volume at `/data`.

### Optional: automate fulfillment (Stripe + email)

If you want payments → keys → email to be automated:

Stripe:
- `CIRCUIT_AI_STRIPE_SECRET_KEY` (or `STRIPE_SECRET_KEY`)
- `CIRCUIT_AI_STRIPE_WEBHOOK_SECRET` (or `STRIPE_WEBHOOK_SECRET`)
- `CIRCUIT_AI_STRIPE_PRICE_HOBBY=price_...`
- `CIRCUIT_AI_STRIPE_PRICE_BUILDER=price_...`
- `CIRCUIT_AI_STRIPE_PRICE_PRO=price_...`

Email (SendGrid):
- `CIRCUIT_AI_SENDGRID_API_KEY`
- `CIRCUIT_AI_SUPPORT_FROM_EMAIL=you@yourdomain.com`
- (optional) `CIRCUIT_AI_SUPPORT_BCC_EMAIL=you@yourdomain.com` (archive all sends)

Webhook endpoint:
- `POST /api/v2/webhooks/stripe`

If Stripe/email env vars are not configured, payments won’t auto-issue keys; the system records a “pending manual” fulfillment instead.

### If Stripe isn’t available in your country

You can still run the business:
- Take payment via PayPal/Wise/bank transfer/invoice (whatever you can use).
- Fulfill by issuing a key manually (or via admin fulfillment endpoint).

Manual fulfillment (admin):
- `POST /api/v2/admin/fulfill` (issues a key, records fulfillment, optionally emails setup if SendGrid configured)

Example:

```bash
curl -sS -X POST https://YOUR_BACKEND/api/v2/admin/fulfill \
  -H "Authorization: Bearer $CIRCUIT_AI_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan":"pro","email":"buyer@example.com","payment_ref":"wise-INV-001"}'
```

### Health check

- `GET /api/health` should return `{"status":"ok", ...}`

## 2) Issue keys (operator flow)

Admin endpoints:
- `POST /api/v2/admin/keys/issue`
- `GET /api/v2/admin/keys`
- `POST /api/v2/admin/keys/<key_hash>/revoke`

Example (issue paid key):

```bash
curl -sS -X POST https://YOUR_BACKEND/api/v2/admin/keys/issue \
  -H "Authorization: Bearer $CIRCUIT_AI_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan":"paid","label":"buyer@example.com"}'
```

## 3) Buyer setup (MCP)

Buyer sets:
- `CIRCUIT_AI_API_URL=https://YOUR_BACKEND`
- `CIRCUIT_AI_API_KEY=cai_...`

Claude Desktop config example:

```json
{
  "mcpServers": {
    "circuit-ai": {
      "command": "node",
      "args": ["/ABS/PATH/TO/Circuit-AI/mcp_server/dist/index.js"],
      "env": {
        "CIRCUIT_AI_API_URL": "https://YOUR_BACKEND",
        "CIRCUIT_AI_API_KEY": "cai_..."
      }
    }
  }
}
```

## 4) Recommended pricing model (early)

Start **prepaid credits** using your key quotas:
- Hobby: validation-only
- Builder: validation + limited BOM
- Pro: validation + BOM + Gerbers

Subscriptions come later (after repeat buyers).
