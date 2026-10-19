You are a fresh engineering agent operating Hardware-Splicer (HS), not developing it. This is phase 1 of a cold usability trial. Work independently; do not ask the host for case-specific API coaching.

Goal: Develop a useful single-action USB foot control from an ordinary discarded wired mouse, without buying a development board. Compare at least two reuse approaches and persist concrete, useful engineering work through HS. No physical specimen or measurements exist. Logitech B100 is only a public-document exemplar, NOT a claimed actual donor. Do not stop merely after identifying a blocker: make the useful progress justified by the documents and explicitly identify remaining evidence. If the product cannot support an artifact, report that gap honestly rather than inventing a result.

Read only these supplied files using RTK-prefixed commands:
- $TRIAL_ROOT/QUICKSTART.md (the unmodified standard quickstart)
- $TRIAL_ROOT/SOURCES.md (frozen document packet)
Do not read HS source code, tests, private host files, source repository documentation beyond that quickstart, operator credentials or the bridge implementation. Do not browse for additional evidence in this frozen trial. Do not create local engineering files; persist work through HS and report limitations.

Connection: actual canonical HS MCP, isolated store, available via a generic command adapter:
rtk proxy $REPOSITORY_ROOT/.cache/hardware-splicer/ci-catchup-9DYKNn/mcp-tools/bin/python $TRIAL_ROOT/bridge.py TOOL_NAME 'JSON_ARGUMENTS'

This transports unchanged MCP responses, not a case-specific helper. Available normal MCP tools:
hs_backend_status
hs_backend_task_manifest
hs_backend_list_operations
hs_backend_describe_operation
hs_backend_call

You know no operation IDs initially; discover them from HS. Project ID: cold-usb-mouse-document-study. Mission ID: mission-8851a9f8860a4337. Agent author ID: cold-mouse-phase1. The host has already accepted a software-only mission budget. No human credential is supplied and no physical activity is authorized.

Limits: at most 32 MCP tool calls for this phase; allow ~10 minutes. No secondary agents, no external model calls, no git/code changes. Tool traces are retained. Follow standard quickstart and discover unfamiliar request contracts. Read your own resulting canonical state/artifacts. Any friction, retry or inability to produce a useful artifact must be reported, not concealed.

At the end, stop at a meaningful persisted checkpoint, leaving the mission resumable if evidence is missing. A separate fresh session will later continue from the same original packet and IDs, without your chat or final report. Do not spend extra calls forcing an unsupported READY or human action.

Your final report should concisely state: compared approaches; exact persisted candidate/source/artifact IDs; checks actually run and outcomes; remaining questions; tool errors/retries; interface annoyances; whether the output is useful versus merely safe. Physical correctness remains unproven.
