# Cold-agent salvage trial: useful planning, incomplete product loop

## Outcome

Two fresh sessions operated HS through real canonical Streamable HTTP MCP,
without case-specific API coaching or an operator credential and under explicit
instructions not to inspect source code. They developed a document-only wired-mouse foot-control
study rather than substituting an ESP32/Pico fixture.

**Useful canonical engineering progress and fresh-session recovery were
demonstrated. A smooth end-to-end engineering/build demo was not.** The run is
quota/deadline-interrupted, not an overall pass. No physical specimen exists.

Frozen implementation: `a0530015d523d0abca89d65704993e1e3053ef73` on existing
[PR #138](https://github.com/Spectating101/hardware-splicer/pull/138).
Manifest: `hardware_splicer.salvage_fabrication_manifest.v2`.
Both agents inherited the orchestrator model; exact child model ID and token
usage were not exposed. Do not label this an Astra run or infer token counts.

## What was actually produced

Canonical project `cold-usb-mouse-document-study` reached revision 4:

- Two persisted candidates: `intact_pedal`, a reversible load-bearing pedal
  operating an intact mouse button; and `remote_contact`, reuse of the mouse
  electronics with a conditional passive remote switch after topology evidence.
- `snapshot.preFabricationPlan` contains the comparison, requirements,
  selection rationale, mechanisms, actions and unresolved questions.
- The fresh second session recovered the candidates/source/check, then added a
  three-state behavioral contract, reconnect/held-button rules, proposed
  acceptance vectors, symbolic mechanical constraints and a durable plan handoff.
- All eight original mission events are unchanged. Candidates and the admitted
  source were not duplicated. The mission remains `EVIDENCE_REQUIRED`, event 8;
  no READY or other terminal outcome was recorded.

One real `device_plan` check ran and was read back from
`runs/device_plan-eb9b0ce4ebfff18f.json`. Its actual result is
`{"refused": "modules must be a list of 1 to 8"}`. HTTP 200 recorded a failed
engineering check; it is not a successful design evaluation. No new candidate
check ran in session 2. Assurance was read at revision 4, but that projection
does not validate the engineering proposal.

No executable adapter, CAD, schematic or build package was produced. No
acceptance vector was executed. Fabrication/power-on readiness and physical
authority stayed false; physical correctness remains **UNPROVEN**.

## Observed operating cost

| Recorded metric | Initial session | Fresh recovery session | Total |
|---|---:|---:|---:|
| MCP calls | 32 | 16 | 48 |
| Discovery calls | 16 | 9 | 25 |
| Backend HTTP 422 responses | 3 | 0 | 3 |
| Tool-response UTF-8 bytes | 367,959 | 238,309 | 606,268 |

There were 13 discovery calls before the first successful persistent action
(source admission, call 17). Call-span timing, exact requests/responses and
metric definitions are in the bundle; those timings exclude a later long
quota/user-resume gap and must not be called end-to-end elapsed time. Response
bytes are not model tokens or full model-context size.

Session 2 hit a provider usage limit before completing its report. Following
the user's continuation, the host requested resumption under the original
remaining call budget. Its final handoff-event attempt was stopped before MCP
by the frozen 1,800-second adapter deadline. This unlogged transport rejection
is explicitly retained in the agent report and host intervention record; it is
not one of the three backend 422 responses. No deadline extension or hidden
successful rerun occurred.

No case-specific payload rescue occurred. There was one planned fresh-session
transition and one administrative quota-resume instruction. A truncated save
response also caused a local parser error; the agent read back the successful
write rather than replaying it.

## Where HS helped, and where it got in the way

The backend retained useful designs and uncertainty, supported a source-bound
revisioned plan, and let another session recover it. That is more than an early
HOLD, but it does not yet satisfy the desired artifact-producing demo.

The concrete gaps are:

1. **Catalog-only execution coverage.** An ordinary intact-device reuse design
   cannot pass the device-module planner honestly. Next product work should
   support this design class explicitly, not require a fictional development
   board or add more governance gates.
2. **Discovery overhead and large replies.** More than half the calls were
   discovery. Related document manifests and whole-project writes/readbacks
   can overflow the client's display budget despite compact salvage onboarding.
3. **Avoidable contract friction.** Markdown admission does not imply PDF
   inspection eligibility. Even `physical_correctness: "UNPROVEN"` is forbidden
   inside candidate specs. The first session hit both conditions; its second
   candidate repeated the same rejected field before correction.
4. **Split projections.** The accepted mission freezes project revision 1 while
   the working project advances. Recovery needs separate reads. Likewise, the
   pre-fabrication response's `engineering_blockers: []` reflects the prior
   snapshot list, not the three declared blockers retained inside the plan.
   The retained blockers and false readiness flags must not be ignored.

The standard quickstart now states these existing operating limits. Its frozen
pre-run version remains in the bundle; the trial has not been rerun against the
clarifications, so no improved live score is claimed.

## Evidence limits and independent readback

This was a cooperative interface trial, not an OS-sandbox/security proof, an
independently graded reliability benchmark, or physical validation. Host
prepared acceptance was a synthetic software-budget fixture, not engineering
signoff. The agent saw host-transcribed public-document paraphrases, not raw
HTML. The captured Logitech and USB-IF HTML hashes identify source bytes; they
do not establish raw-document comprehension or independent EE adjudication.

The [proof bundle](generated/cold-usb-mouse-2026-10-19/PROOF_BUNDLE.json)
binds original and path-sanitized bytes for 31 captured artifacts, including
prompts, frozen quickstart/packet, full MCP tool transcript, agent reports,
host interventions, checkpoint, canonical revisions/events/source blob and the
actual refused-check artifact. Original manufacturer HTML is retained locally,
not republished. Tool transcript hashes refer to original producer bytes where
paths were sanitized; the bundle maps those to public bytes.

Run the read-only integrity/state checks with:

```bash
python docs/status/generated/cold-usb-mouse-2026-10-19/VERIFY.py
```

It verifies all 31 hash-mapped artifacts, recorded metrics, preserved event
prefix, source/run hashes, revision-4 additions and closed authority. Its
`proof_integrity: pass` explicitly coexists with
`product_end_to_end_pass: false`.

## Cleanup validation, separate from the live trial

Frozen code head `a0530015` completed all **18/18** GitHub checks. Its full Python
regression suite reported **4,321 passed, 206 skipped**. This evidence/quickstart
follow-up changes no runtime code and must not silently inherit an exact-head
CI claim; new-head CI status belongs to the PR's current check runs.

Main was not merged or changed. No new PR, provider contact, purchase, hardware
action, fabricated measurement or engineering authorization was performed.
