# Passive donor input firmware proposals

This extends the existing device-application generator, not the canonical evidence store or authorization model.
Native passive-switch donors may accompany a supported sensor-monitor application on the ESP32-DevKitC V4 or
Raspberry Pi Pico. Donor-only applications, active outputs, powered donor domains and arbitrary user code are not
added here. The planner's electrical and geometry gates still apply before export.

## Frozen bindings, not a second contract

The mission executor obtains its private donor module context from the accepted mission's frozen `donor_read`.
Application generation recomputes the canonical plan with that context and refuses every wiring error or warning.
Only the plan's direct controller connections become numeric GPIO bindings. The normal standalone application and
runtime HTTP endpoints still cannot resolve donor IDs or accept embedded donor module maps.

`DONOR_INPUTS.json` maps stable input indices to the placed instance, donor ID, signal, contact, exact controller pin,
accepted evidence IDs and a SHA-256 of the frozen donor reading. That file is an artifact projection, not a new
claim/evidence store. No contract, project snapshot, revision or evidence grade is changed by generation or execution.

## Proposed behavior

The generated `src/donor_inputs.h` configures the mapped pins as `INPUT_PULLUP`, samples active-low contacts, and
prints `DONOR_INPUT index=<n> pressed=<0|1>` after an observed state has remained unchanged across samples for at
least 20 ms. It reports both initial states (including a button held at startup), then only debounced changes.
Each input has independent state. `begin()` resets the state and requires a fresh settle interval. Unsigned 32-bit
subtraction handles a millisecond-counter rollover. Polling is nonblocking and runs before the existing sensor
application's loop; sensor work may delay the next poll.

Internal pull-up selection and 20 ms are **software design proposals**, not properties established by the donor
measurements. Arduino's documented [pinMode](https://docs.arduino.cc/language-reference/en/functions/digital-io/pinMode/),
[digitalRead](https://docs.arduino.cc/language-reference/en/functions/digital-io/digitalread/) and
[millis](https://docs.arduino.cc/language-reference/en/functions/time/millis/) APIs define the interface used by the
adapter; they do not establish suitability for a particular donor or physical timing guarantees.

Short pulses between polls may be missed. Sampled stability does not establish continuous electrical stability.
An open wire and a released switch both read high; no continuity, stuck-switch or safe-actuation diagnosis is claimed.
No behavior is connected to a motor, relay or actuator. The existing sensor/display behavior is retained.

## Execution and packaging

The same generated header included by `src/main.cpp` is compiled and run against an HS-owned digital GPIO/clock shim
in `test/donor_host`. Ten scenarios check input-only pull-up configuration, released and held startup, press/release
bounce, held-state non-repetition, input isolation, rollover, short pulses and reinitialization. This does not test
real pin registers, electrical thresholds, pull-up strength, contact resistance, real-time scheduling or silicon.

The existing opt-in runtime (`HS_DEVICE_RUNTIME_ENABLED=1`) runs a separate `donor_host` phase. The existing bounded
compiler/process runner and single runtime slot are reused. Every named scenario must occur exactly once with
literal `pass: true`, no finding and a successful exit. A failed donor phase makes the overall result `FAILED`,
even if both sensor phases pass. Missing pinned sensor/display libraries still yield `PARTIAL`, not a clean pass.
With those libraries configured, the vendor-host phase also compiles the combined `main.cpp`; that bus model is
not a substitute for the dedicated input scenarios.

`device_application` and `device_application_run` use their existing mission operations and budget. Runtime reports
remain hashed mission run artifacts. The READY package includes the actual generated input source, its manifest,
the existing sensor application, frozen donor reading and recorded software evaluations. A source export says
`donor_behaviour_tests: NOT_RUN`; a later runtime result does not rewrite the proposal to claim it ran itself.
The package's firmware test status comes from the recorded runtime evaluation. Unsupported combinations retain a
`BLOCKED.md`. The plan's topology-only `donor_scope` remains separate from the package's input-firmware scope.

The standalone diagnostic generator remains library-only. Legacy tracking-only `donors_used` records do not acquire
implemented input firmware. No browser/UI change or new public evidence-writing endpoint is introduced.

## Authority and trust limits

`firmware_authorized` and `power_on_authorized` remain false; `physical_correctness` remains `UNPROVEN`. This path
generates source and executes off-hardware host models only. It never uploads, flashes, powers or measures a board.
Production permission checks and the separate canonical donor PlatformIO authorization gate are unchanged.

Tests use synthetic project/evidence fixtures. The existing trusted snapshot-PUT/filesystem-writer boundary also
remains: hashes bind identities, not instrument truth, genuine review or accurate transcription. No live-agent
reliability trial, independent EE review or physical validation is implied by these software tests.
