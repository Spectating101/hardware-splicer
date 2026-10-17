# Native donor planning — backend handover, 2026-10-17

Branch: `agent/mission-donor-planning`, based on `agent/mission-donors` at `5cb6c23c`.
Nothing pushed or merged. Main, #122/#123/#124, Step 4 and the completed P4/P5 branch remain unchanged.

## Delivered

The existing device planner can place and wire project-scoped donor modules, not merely retain donor references.
The first implementation is passive switch/button contacts with measured top-header geometry and explicit measured
`switch_to_ground`/`ground_reference` protocols. No new controller or sensor was added to the library.

- Optional `InterfaceContract.planner_geometry` round-trips through the existing contract store and freezes into
  the system donor reading. Default/absent geometry does not change legacy contract serialization.
- The mission executor builds private per-call module context from frozen electrical/dimensional evidence.
  Standalone device JSON cannot inject context or inherit a library analogy's electrical or mechanical properties.
- Native modules participate in placement, case sizing, contact coordinates, wiring curves, ground paths, GPIO
  restrictions, engineering coverage and assembly-step proposals. Missing connections and malformed geometry fail.
- Repairs cannot downgrade implemented donor modules into tracking-only references. Native usage is one-to-one
  with donors_used, with intake membership and duplicate physical-block checks.
- A deterministic package includes the actual donor plan, frozen donor reading, scope limits and generated
  enclosure STL/OpenSCAD. Donor firmware/runtime explicitly refuse; a library-only sketch is never mislabeled as
  implementing the donor. Existing legacy tracking-only P4 specs retain their prior semantics.

Implementation and format: [DONOR_DEVICE_PLANNING.md](../DONOR_DEVICE_PLANNING.md).

Source commits:

- `b4bf5fb6` — Plan passive donor modules from frozen mission evidence
- `33f785d0` — Document native donor planner scope and authority limits

## Verification actually performed

Final committed-source run, using the shared root .venv and worktree PYTHONPATH:

```text
PYTHONPATH=src <root>/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_donor_device_plan.py tests/test_device_plan.py tests/test_device_engineering.py tests/test_device_case.py tests/test_mission_*.py tests/test_device_agent_surface.py tests/test_mcp_backend_gateway.py tests/test_interface_contract_provenance.py tests/test_integration_stack.py tests/test_evidence_salvage_bridge.py tests/test_evidence_bench_gates.py --tb=short --junitxml=.cache/donor-planning-focused-final.xml
643 passed, 16 warnings in 62.94s (0:01:02)
```

There are 40 new donor-planning cases, including both ESP32 and Pico wiring, a real executor/review/case/package
flow and real HTTP calls. Test measurements are synthetic fixtures in temporary projects, not bench results. The
end-to-end case builds the package repeatedly, matches its SHA-256, checks ZIP integrity, finds the actual donor
module in the recorded plan and verifies firmware is blocked while enclosure output is generated.

Initial test-first run: `3 failed, 1 warning in 2.73s` (missing module projection and dropped geometry). Subsequent
isolated failing regressions preceded fixes for three connector geometry/unit checks, a huge-integer overflow,
three silently discarded malformed contract row cases, and a missing donor placement step. Compatibility testing
also caught two existing one-argument callback tests broken by unnecessary None kwargs; the legacy calling
convention was preserved. A test incorrectly called the ESP32 serial pin IO1; it was corrected to its actual TX
label, without adding an alias or weakening pin checks. Supplementary tests are not claimed as independent bugs.

Canonical JSON hashes of all four library example plans were independently recomputed on both the previous branch
and this implementation and match exactly:

| Example | SHA-256 |
|---|---|
| esp32_oled_usb | a57a449012ddbfe13e14053e7e9e36819912c87fa22da75abb6d22ea357dcff7 |
| esp32_oled_bme280_usb | 39473be90a6a53acd1e81c0e32a33d6479ac5df1a2427a43bfae26b29b5f608c |
| pico_oled_usb | 44080ce2d506fca5c15d10eb1e45041ac7d43101c6ebfc44fa1eb2d9cb4b951a |
| pico_oled_bme280_usb | 93171ab40d0a6cabe7c8e4edd273974687ac57adf9f64fa001c7005dc89f8cf2 |

`git diff --check` passed. Local XML: `.cache/donor-planning-focused-final.xml`.

## Verification not performed

The remote health probe reported zero healthy workers, below the required minimum of two: all three workers were
SSH-unreachable or unauthenticated. That offload path was stopped and reported; only focused local checks were run.
The full Python suite was **not rerun** for these commits. The previous P4/P5 full result is historical evidence,
not a full-suite result for this branch. No new remote CI, browser suite, accepted live agent rerun or physical trial
was performed. No operator token was retrieved or real mission accepted. No external service, fabrication,
procurement, flashing or power-on action occurred.

The old frozen plan's prerequisite live reruns remain outstanding. User-directed development here does not imply
that those trials passed. Do not merge or advertise the whole stack as fully validated on the strength of this run.

## Remaining boundary

This is nominal-3.3-V passive topology and measured-geometry projection, not a complete donor hardware implementation.
Donor firmware, pull-up configuration, debounce, actuation mechanics, mounting strength, leakage, transients,
rail tolerances and physical performance remain unverified. General active drivers and external power domains are
unsupported. The existing snapshot/filesystem writer trust boundary is unchanged: envelope hashes do not prove
instrument truth, authentic human review or correct transcription. No new contract geometry import/promotion API
was added; those records remain owned by the existing reviewed evidence workflow.

Physical correctness remains UNPROVEN and mission firmware/power flags remain false. The next functional boundary
is a bounded donor input firmware adapter and its modeled runtime, not a claim of physical validation.
