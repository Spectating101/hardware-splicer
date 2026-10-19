# Intact input-device reuse: a runnable software deliverable

This is the first non-catalog execution slice prompted by the document-only
[cold-agent mouse trial](status/COLD_SALVAGE_AGENT_TRIAL_2026-10-19.md). It makes
a concrete artifact rather than converting an unknown donor into a development
board. It does not complete arbitrary e-waste engineering or validate hardware.

## Agent workflow

Use the normal `salvage_fabrication` manifest, then:

1. Read `GET /v1/projects/{project_id}/missions/{mission_id}/intact-reuse-spec`.
   It returns a bounded schema, contextual donor/source IDs and a proposal
   example. The example's logical bindings/mechanics are not donor observations.
   Admit a source through the canonical source workflow if none is registered.
2. Propose the actual spec as a `candidate_proposed` event, retaining the real
   donor in `donors_used`. No `modules`/purchased controller is required.
3. Run `intact_reuse` through the normal candidate `/run` route. Human acceptance
   of the software budget is required; one recorded evaluation spends one job.
4. Read the returned hashed run artifact for checks, file hashes, source hashes,
   mission anchor, source-read revision, spec digest and unresolved questions.
5. Download the returned `bundle_download_path` (through MCP, use
   `response_mode: "base64"` when the ZIP bytes are actually needed). On resume,
   derive the download from the recorded run filename: `runs/{name}/bundle`.

The run records software success separately from unresolved physical warnings.
Failure to parse/verify/generate/test is recorded as a failed evaluation, with
no passing bundle link. A failed intact-spec check allows the normal bounded
repair path; the repair still cannot drop the donor, newly violate requirements
or exceed budget. Clean software plus physical unknowns is not a repair failure.

## Delivered files

- `adapter.py`: consumes newline-delimited normalized button events and emits
  symbolic one-shot actions to stdout. Standard-library Python only.
- `contract.json`: exact proposed design and logical binding, original mission
  anchor, canonical source-read revision, spec/source identities and questions.
- `test_adapter.py` and `offline-checks.json`: seven explicit synthetic scenarios
  and results, checking both action contents and the input steps emitting them.
- `example-events.jsonl`: a disconnected/armed/held input demonstration.
- `README.md`: execution instructions, scope and nonclaims.

Run `python test_adapter.py`, then
`python adapter.py < example-events.jsonl`. The example emits one symbolic
`activate` action. It does not press a real key or operate a real device.

The adapter starts disconnected. Connecting/reconnecting disarms it until a
release; a subsequent press emits one action and repeated held/press events do
not repeat. Other logical devices/buttons are ignored. A real host bridge must
provide reliable initial state/disconnect and button mapping. No time-based
debouncing or actual-device behavior is proven by normalized-event replay.

## What remains unimplemented/unproven

This slice does not enumerate devices, parse USB reports, supply an evdev/HID
bridge, inject OS input, execute action names, or supply measured dimensions,
forces, pinouts or wiring. The remote-contact approach keeps an additional
topology/contact question and never generates connections. Source byte identity
does not imply source correctness, applicability or independent review.

It is a **SOFTWARE REVIEW** bundle, not the mission's existing READY build
package. Catalog plan/review checks, inventory coverage, donor verification,
human review, firmware/physical approval and existing READY semantics remain
unchanged. No new authority state, evidence store or donor contract is created.
Recorded historical bundles remain bound to their recorded spec/revision; a
later repair does not turn an old bundle into evidence for the new spec.

## Verification and scope of demonstration

`tests/test_intact_reuse.py` exercises actual HTTP routes, download/replay,
deterministic ZIP output, source/run/ZIP tampering, malformed requests, budget
and acceptance gates, failed-check repairs and unchanged readiness. Four seeded
adapter faults must be caught: repeating held presses, accepting another
device, accepting another button, and arming immediately on connect. Their
tests exposed a count-only oracle blind spot; action-step checks close it.
This is a narrow regression set, not a broad mutation-score claim.

`scripts/smoke_intact_reuse_mcp.py --output <new-directory>` runs the actual
canonical MCP SDK/server, discovers the schema, proposes, executes, reads and
downloads the artifact, then independently replays the delivered tests. Host
setup uses a transient synthetic software-budget token, unavailable to the MCP
client. Its output is a real runnable ZIP and full tool trace. It is a
**scripted protocol control, not a new live-model usability score**. The frozen
earlier trial is not rewritten or counted as passing this new capability.
