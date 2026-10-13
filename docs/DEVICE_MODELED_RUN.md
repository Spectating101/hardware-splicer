# Run the generated device application off-hardware

> **A tested engineering-software system with modeled execution — not physically validated hardware.**
> It is suitable for an evaluator, developer or portfolio demonstration. It is not authorization to
> fabricate, flash or power hardware.

On **Build a device**, choose the ESP32/OLED/BME280 example, check the wiring,
then select **Run modeled tests**. Open scenario rows to see synthetic serial
readings, missing-device faults, stale data and recovery. Download the modeled
report and the application source ZIP; `proposal_sha256` binds them exactly.

This is generated C++ executed by a host compiler, not an ESP32 instruction
emulator, physical sensor readings or an electrical simulation. The core lane
tests `SensorApp` through a synthetic HAL. The optional vendor-host lane compiles
the generated Arduino adapter and pinned Adafruit code against register models.
These are distinct scopes. ESP32 target compilation remains `NOT_RUN` in this
interactive route; the existing compiler CLI/CI lane remains separate.

## Server configuration

Execution is disabled unless the server operator sets:

```sh
HS_DEVICE_RUNTIME_ENABLED=1
```

The host needs `g++`. A missing compiler is reported as unavailable with no
tests run, not mislabeled as a failing application scenario.

For vendor-host tests, first provision the pinned dependencies with the existing
`scripts/verify_device_application.py --platformio <pio>` command, then set
`HS_DEVICE_RUNTIME_VENDOR_LIBS` to that run's `project/.pio/libdeps/application`
directory. Requests cannot choose library paths, tools, code or authority flags.
Missing configuration produces `PARTIAL`, with vendor-host `NOT_RUN`, not a
vendor pass. Configured libraries must match the pinned version declarations of the part's
lane (five for the BME280, three for the BH1750, whose sensor is driven by the adapter's own code);
the report includes source-member SHA-256 hashes of the libraries used.
Libraries are copied into the private execution directory before hashing and
compiling, so later changes to the dependency cache cannot change the recorded
bytes. The declared versions/hashes identify inputs, not an independent attestation
of vendor origin.
Each supported part has its own vendor-host lane (a bus model and an eleven-scenario
harness, selected by the part descriptor) and each requires its sensor plus SSD1306.
A sensor-only export can run core scenarios but remains `PARTIAL`; its Arduino adapter
is not credited as tested by that fixture. The BME280 lane models the Bosch register map;
the BH1750 lane is a model written from the Rohm datasheet, with the datasheet's worked
examples as the oracle, and it does not model the resolution modes. See
[part descriptors](DEVICE_PART_DESCRIPTORS.md).

Set `HARDWARE_SPLICER_API_KEY` before exposing execution beyond loopback. The
Next proxy forwards this existing app credential; the execution route checks it.
Set the same key on the backend and frontend. The existing `CIRCUIT_AI_API_KEY`
is also accepted as a fallback when `HARDWARE_SPLICER_API_KEY` is not configured.
Without a configured key the API permits only a loopback caller. A publicly
exposed frontend must also be behind appropriate authentication; a loopback
reverse proxy by itself does not authenticate its external users. This app key
does not establish operator identity or grant engineering/physical authority.

## HTTP and limits

`POST /v1/devices/application/run` accepts only `{spec}`. The backend recomputes
the plan and generates its own source before any execution. Wiring warnings,
unsupported devices and malformed input are refused just like application export.
Request size is bounded to 64 KiB. One run per server process is admitted;
another receives 429 without queueing a compiler. This is not a cluster-wide
quota or a substitute for authenticated deployment limits.

The shared executor uses the existing HS bounded-process runner: 30 seconds for
compiler identification, 120 for compilation and 60 for harness execution, with
1 MiB captured output tails. It kills/reaps the process group, including remaining
forked harness children. This is controlled-template execution, not a general
untrusted-code sandbox. Temporary projects are removed after execution.

Results are `PASSED` only if both core and configured vendor lanes pass;
`PARTIAL` if only core passes and vendor tests are unavailable; `FAILED` if a
required executed lane fails. Incomplete/malformed scenario output cannot pass.
Disabled execution or invalid server dependencies are explicit availability
errors. These operations never create a project revision or persist bench facts.

The browser aborts and clears results when the checked specification changes.
Modeled serial traces are displayed separately from **Check a bench scan** and
are never automatically submitted as physical evidence.

All results retain `physical_correctness=UNPROVEN`, `firmware_authorized=false`
and `power_on_authorized=false`. No flashing, powering, fabrication or procurement
occurs in this workflow.

## Evidence

- [Adding a part](DEVICE_PART_DESCRIPTORS.md): the descriptor each supported sensor is generated from, and its limits.
- [Mutation benchmark of these tests](status/DEVICE_FAULT_MATRIX_BENCHMARK_2026-10-12.md): how many seeded bugs the
  boot-only, healthy-bus and fault scenarios catch, for the application logic and the Arduino adapter.
- [Running the compiled firmware in an emulator](status/DEVICE_EMULATOR_FEASIBILITY_2026-10-12.md): what is known,
  what was not run, and the protocol to finish it.

