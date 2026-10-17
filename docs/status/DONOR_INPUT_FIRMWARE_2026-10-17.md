# Passive donor input firmware — backend handover, 2026-10-17

Branch: `agent/mission-donor-firmware`, based on `agent/mission-donor-planning` at `94d785de`.
Implementation: `45482b655dd0287a607f3c03fe80e0371a0bb8d0`.
Nothing pushed or merged. Main, #122/#123/#124, Step 4, P4/P5 and the previous donor-planning branch remain unchanged.

## Delivered

Native passive-switch donors now have an actual generated input adapter alongside the existing sensor monitor.
The existing backend/generator/runtime were extended without introducing a new service or evidence store.

- Bindings come from frozen measured donor facts and canonical planned GPIO connections, not embedded caller maps.
- `DONOR_INPUTS.json` retains signal/contact/controller identity, evidence IDs, frozen-reading hash and assumptions.
- The generated Arduino header proposes internal pull-ups, active-low reads and independent 20 ms sampled debounce.
  Initial released/held states, changes, reinitialization and 32-bit rollover are handled without debounce sleeps.
- A separate `donor_host` phase compiles that same header against a GPIO/clock shim. All ten named scenarios must
  appear exactly once and pass. A donor failure makes the overall runtime fail even when both sensor phases pass.
- The mission's existing application generation/runtime operations and budget are reused. READY packages include
  the actual input proposal rather than a misleading library-only sketch. Source generation and recorded test
  results remain separate; a generated proposal initially says `donor_behaviour_tests: NOT_RUN`.
- Standalone application/runtime HTTP calls still cannot resolve donor IDs or inject their context. No project
  revision or evidence record is written by generation/execution, and physical authority remains closed.

Behavior, boundaries and artifact format: [DONOR_INPUT_FIRMWARE.md](../DONOR_INPUT_FIRMWARE.md).

## Verification performed

Three local focused runs covered **728 distinct test identities**. All passed on their latest run, with zero
outstanding skips in that union. This is a deduplicated union of focused runs, not a single full-suite result:

| Run | Result |
|---|---|
| Existing application/firmware and mission executor/delivery/feedback/donor checks | 217 passed, 11 skipped, 14 warnings in 104.75 s |
| Final donor application/planner, device planner/engineering/case checks | 363 passed, 8 warnings in 76.21 s |
| Remaining mission store/gate/API/concurrency and cached-library Pico/runtime checks | 175 passed, 9 warnings in 88.06 s |

The third run overlaps the first. All eleven skips in the first run were cached vendor-library tests; each was
rerun and passed after explicitly setting `HS_VENDOR_LIBS` to the existing pinned cache. They are not counted as
passes merely because they skipped.

The new application test file contains 25 cases. Actual generated adapters were compiled/run for one and four
inputs on both controller models. The combined two-input application passed all host, donor-host and vendor-host
phases for BME280 and BH1750 on both ESP32 and Pico. The real pinned sensor/display library sources were compiled
with generated `main.cpp` against the existing bus shims; no physical GPIO driver or silicon was tested.

Four deliberately broken adapters (polarity, pin, input mode and rollover) were all rejected by the input harness.
These are targeted negative controls, not an independent mutation benchmark or reliability estimate. Additional
tests reject missing/duplicate scenarios, string-valued pass claims and findings; propagate input failure through
the runtime/mission; preserve frozen mappings after source edits; refuse context injection; and exercise real
mission generation, execution and repeated deterministic packaging with synthetic temporary-project evidence.

The initial test-first run failed seven cases: five reached missing implementation and two had a malformed
multi-signal fixture. A later run passed 17 cases and rejected two BH1750 fixtures with the wrong catalogue ID.
Those fixtures were corrected using the real schema/IDs; they are not claimed as product defects. The existing
topology/package test now requires the actual input source and explicit NOT_RUN test/false-authority fields,
replacing its historical unsupported-firmware expectation.

Two existing library-only application packages were independently regenerated on the parent and new branch and
remain byte-identical:

| Example | ZIP SHA-256 on both branches |
|---|---|
| `esp32_oled_bme280_usb` | `c79cf04f5f5f6e1958665548635a1bb1420decfe531c607c873b9090d0e42861` |
| `pico_oled_bme280_usb` | `9c0f28582b3f001bf43c28c75745de6e0720a93c653bd5776565a9d6e26b4405` |

`git diff --check` passed. All execution was headless and sequential; no other agent's process was stopped.

## Reproduce

Use `PYTHONPATH=src` with the shared root `.venv/bin/python`, not a global Python. Commands ran with `rtk proxy env`.
Set `HS_VENDOR_LIBS` for the second and third runs to an existing pinned library directory; the verified cache here
was `<root>/.cache/hardware-splicer/device-application/device-application-tzspjcwu/project/.pio/libdeps/application`.
The tests set opt-in runtime configuration only within their own test process.

```text
python -m pytest -q -p no:cacheprovider tests/test_device_application.py tests/test_device_application_pico.py tests/test_device_application_runtime.py tests/test_device_application_verifier.py tests/test_device_firmware.py tests/test_device_firmware_pico.py tests/test_mission_executor.py tests/test_mission_delivery.py tests/test_mission_feedback.py tests/test_mission_donors.py --tb=short --junitxml=.cache/donor-input-compatibility.xml

python -m pytest -q -p no:cacheprovider tests/test_donor_device_application.py tests/test_donor_device_plan.py tests/test_device_engineering.py tests/test_device_plan.py tests/test_device_case.py --tb=short --junitxml=.cache/donor-input-final.xml

python -m pytest -q -p no:cacheprovider tests/test_device_application_pico.py tests/test_device_application_runtime.py tests/test_mission_store.py tests/test_mission_gate.py tests/test_mission_api.py tests/test_mission_concurrency.py --tb=short --junitxml=.cache/donor-input-mission-and-vendor.xml
```

JUnit reports are ignored local scratch artifacts, not published CI evidence:

| Report under `.cache/` | SHA-256 |
|---|---|
| `donor-input-compatibility.xml` | `3365a5d4da20a89de0b1083d039e7750bf04cf0020e0136ca394a25970def8fc` |
| `donor-input-final.xml` | `3960d084bcb35e369e1c13320ad49376a1e99e5f52f2d7e9079b0f529ee7a1be` |
| `donor-input-mission-and-vendor.xml` | `bcbc66a4d8b0aad2a2224feb0ad55f4d1fb456ba750a14a404a21e665d0d3d9f` |

## Not established

No full repository suite, new CI, browser suite, target-board PlatformIO compilation or accepted live-agent trial
was run for this adapter. The previous branch's full result (4,243 passed, 56 skipped, two pre-existing intake
failures) predates this implementation and must not be presented as its full-suite result.

This supports the existing sensor application plus passive switch inputs, not donor-only applications, arbitrary
donor protocols, active outputs or external donor supplies. Pull-up suitability/strength, physical debounce,
electrical thresholds, leakage/transients, contact life, actuation and mounting remain unverified. Source generation
does not imply compilation for a target board, successful runtime tests or human permission.

No real operator token was used, real mission accepted, external provider contacted, hardware purchased, fabrication
authorized, firmware flashed or board powered. Test human/measurement records are synthetic fixtures only.
`physical_correctness` remains `UNPROVEN`; `firmware_authorized` and `power_on_authorized` remain false. The existing
trusted snapshot/filesystem writer boundary is unchanged, and the pending independently accepted live trials are
still pending. Review this isolated branch before integrating it; no physical readiness claim is warranted.
