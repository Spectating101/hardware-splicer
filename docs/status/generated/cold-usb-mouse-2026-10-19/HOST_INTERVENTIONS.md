# Host interventions and trial limits

- Phase 1 and phase 2 were separate collaboration agents, each forked with no parent chat. The exact prompts and unmodified quickstart are preserved.
- Host supplied only the original source packet, IDs, generic MCP adapter, goal and budgets. No case-specific API payload rescue, solution, hidden source-code access or operator credential was supplied.
- Host prepared acceptance of a software-check budget using a synthetic trial-only operator, not independent human engineering signoff. Its transient random token was removed from the server environment and never published.
- Phase 2 reached canonical revision 4 and then hit a provider model usage limit. Following the user's "continue", host requested continuation of the same phase under its remaining four-call budget. That administrative resume is one intervention; it supplied the remaining call count, not engineering or payload coaching.
- The resumed agent reported that its final event attempt was stopped by the frozen 1,800-second transport deadline. This rejection happened before an MCP request and is not in trace.jsonl. It is recorded by the agent report, separately from the three logged backend 422 responses. The deadline was not extended. No final handoff event was accepted.
- Recovery of existing canonical state and an additive plan update are demonstrated; uninterrupted end-to-end completion is NOT demonstrated. The run is quota/deadline-interrupted, not an overall clean pass.
- A local response-parser error after output truncation was reported by phase 2, not a backend rejection. The successful write was read back, not replayed.
- The agent's tool/source restriction was cooperative instruction, not an OS sandbox. This is an interface trial, not proof of hostile-agent containment.
- Only host-transcribed paraphrases were model-visible, not the original HTML. The original HTML hashes bind captured bytes but do not establish raw-document comprehension or independent EE adjudication.
- Exact per-child model ID and token usage were not exposed by the orchestration tool. Do not infer or estimate these from response bytes.
- Host independently compared all eight phase-1 event records against their checkpoint hashes; none changed in phase 2. Canonical candidates and the admitted source were not duplicated.
- Host terminated only this trial's MCP server after both agents stopped. No ordinary project, main branch, provider or physical system was changed by the trial.
