# Astra context-compression plan

The historical primary-source pass reported 414,976 input tokens. Offline trace profiling
found:

- 16 MCP calls;
- 10 discovery calls (`list` or `describe`);
- 176,623 serialized MCP-result bytes;
- 161,744 text characters in MCP results, roughly 40,436 tokens by a non-provider
  characters/4 estimate;
- a 41,703-byte final project readback;
- repeated identical canonical project reads.

The detailed, non-billing profile is stored in
`2026-09-12-primary-source-context-profile.json`. Reported provider usage remains the only
authoritative token count; the byte/character figures are attribution aids.

For blinded v2, `hs_backend_task_manifest("bounded_pre_fabrication")` replaces repeated broad
catalog searches and per-operation descriptions with one 12,556-byte manifest generated
from canonical OpenAPI. It currently contains the six exact project, plan, assurance,
delta, and package operations required by the case. Broad discovery remains available only
as a fallback.

This is an offline structural optimization, not a demonstrated token reduction. The target
for the next and only paid conflict run is at most 200,000 reported input tokens. No lower
token claim should be made until a fresh durable provider usage record exists.
