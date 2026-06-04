# Copilot Integration

Circuit-AI can use the local GitHub Copilot CLI as a text reasoning provider
for engine testing. This uses the machine's existing GitHub/Copilot OAuth state
through the installed `copilot` command.

## Backend Circuit Reasoning

Primary backend path:

```text
POST /circuit/reasoning/assess
GET  /circuit/reasoning/model-status
```

Select Copilot with:

```bash
LLM_PROVIDER=copilot
LLM_MODEL=gpt-4.1
COPILOT_MODEL=gpt-4.1
COPILOT_NODE_RUNNER="npx -y node@20"
COPILOT_TIMEOUT_SECONDS=90
```

Why `COPILOT_NODE_RUNNER` exists: the installed Copilot CLI requires Node 20 or
newer. This machine's system Node is currently Node 18, but `npx node@20` works
without changing the system install.

The provider runs Copilot with:

```text
--stream off
--no-custom-instructions
--disable-builtin-mcps
```

That keeps the provider text-only and prevents Copilot engine calls from using
repo tools/MCP servers. Model claims remain advisory and still pass through the
deterministic circuit verifier.

Run a safe smoke test without printing tokens:

```bash
python3 scripts/copilot_circuit_reasoning_smoke.py
```

## Frontend Jarvis

Jarvis text and image-evidence flows can use Copilot:

```bash
JARVIS_TEXT_PROVIDER=copilot
JARVIS_VISION_PROVIDER=copilot
COPILOT_MODEL=gpt-4.1
COPILOT_NODE_RUNNER="npx -y node@20"
```

If the FastAPI analyzer requires auth, the frontend also needs:

```bash
CIRCUIT_AI_API_KEY=...
```

Covered flows:

```text
chat
identify
salvage
project
```

The local Copilot CLI still does not expose raw image attachments in prompt
mode. For `identify` and `salvage`, the Next routes build a
`COPILOT_IMAGE_EVIDENCE_JSON` packet first:

1. image metadata and hash
2. local FastAPI CV/OCR analyzer results when available
3. detected component candidates, markings, topology, certainty, and missing
   evidence

Copilot then reasons over that image-derived evidence and returns the same JSON
contracts as the older vision flows. Treat this as an evidence-mediated vision
bridge, not native multimodal image input to the Copilot CLI.

Image-evidence responses are cached only after the local analyzer succeeds, so
temporary analyzer outages produce conservative unknown/caution output without
poisoning later scans.

For local smoke testing only, the backend can be started with a matching
temporary test key:

```bash
TEST_API_KEYS=circuit-local-test uvicorn src.api.v1.main:app --host 127.0.0.1 --port 8000
CIRCUIT_AI_API_KEY=circuit-local-test npm run dev -- --port 3016
```

Safe status endpoints:

```text
GET /api/jarvis/status
GET /api/proxy/circuit/reasoning/model-status
POST /api/proxy/circuit/reasoning/assess
```

These endpoints report readiness and selected models without returning OAuth
tokens, GitHub tokens, or API key values.
