# DeepSeek Integration

DeepSeek is a first-class text reasoning provider for Circuit-AI, but it is not
the full vision stack. Treat it as the advisory model behind circuit reasoning
and Jarvis text flows, with deterministic verifier gates deciding whether any
splice or reuse claim is allowed.

## Backend Circuit Reasoning

Primary backend path:

```text
POST /circuit/reasoning/assess
GET  /circuit/reasoning/model-status
```

DeepSeek is selected with:

```bash
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-flash
LLM_API_BASE=https://api.deepseek.com
DEEPSEEK_API_KEY=...
```

The backend also accepts DeepSeek-specific aliases:

```bash
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_THINKING=disabled
DEEPSEEK_REASONING_EFFORT=
```

When `LLM_PROVIDER=deepseek`, generic placeholder models such as `command-r`
are replaced by `DEEPSEEK_MODEL` when set, otherwise by the backend default.

The live model call uses DeepSeek's OpenAI-compatible chat completions API with
JSON output requested. The response is parsed into model hypotheses and proposed
splices, then passed through deterministic verification. Model claims remain
advisory.

Run the backend smoke without printing secrets:

```bash
python3 scripts/deepseek_circuit_reasoning_smoke.py
```

## Frontend Jarvis

Frontend Jarvis text flows can use DeepSeek:

```bash
JARVIS_TEXT_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_THINKING=disabled
```

DeepSeek currently covers text-only Jarvis flows:

```text
chat
project
```

Vision flows still require a vision-capable provider:

```text
identify
salvage
```

If `JARVIS_TEXT_PROVIDER=deepseek` is explicitly set without
`DEEPSEEK_API_KEY`, Jarvis fails clearly instead of silently using another text
provider.

Safe status endpoints:

```text
GET /api/jarvis/status
GET /api/proxy/circuit/reasoning/model-status
POST /api/proxy/circuit/reasoning/assess
```

These endpoints report provider readiness and selected models without returning
API key values.
