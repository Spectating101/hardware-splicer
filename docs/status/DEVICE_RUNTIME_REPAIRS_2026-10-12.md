# Device runtime and verification repairs — 2026-10-12

Final code revision: `87e02878` on `agent/hs-competitive-integration`.
This follow-up does not modify the earlier frozen release or experiment bundles.

## Repairs

- Harness acceptance requires successful process exit, every expected scenario
  exactly once, literal boolean passes, and no findings. Malformed, partial,
  duplicate, crashed and timed-out executions fail closed. Host and vendor-host
  execution have a 60-second wall-clock limit.
- Serial comparison retains historical counts but uses the latest application
  state. Faults and stale readings cannot inherit boot success, recovery can
  replace a fault, and a disagreement with a scan prevents a consistent summary.
  Invalid application line shapes are not accepted as readings. The latest 50
  scans are retained instead of the first 50. Initialization failure is distinct
  from a missing ACK: a chip may answer but fail calibration.
- The mock browser CI lane installs KiCad itself, not just symbol/footprint
  libraries, and checks the version and GLB command before testing.
- A bounded BME280 adapter replaces the application's call into the upstream
  unbounded initializer. It checks identity/reset/status transactions, bounds
  calibration polling, reuses vendor calibration/compensation code, and rejects
  a failed rebind. Vendor source files are not modified. A stuck calibration
  scenario must fault without readings, remain bounded during retries and recover
  once the modeled condition clears. Removing the timeout is a caught mutation.
- Relative vendor-library paths are resolved before entering the extracted
  project's compile directory, so the supported CLI path does not become a
  spurious missing-library failure.

Repair commits: `22582d75`, `b0849f90`, `5e885cf1`, `c69835e0`, `5217e65e`, `87e02878`.

## Verification

- Focused application/vendor/verifier/observation/device/firmware/source-tracking
  tests: 345 passed, no skips. This includes all six vendor mutations and the
  22 core mutations.
- Final verifier/observation/CI setup regression check: 63 passed.
- Tracked-only export: 60 verifier/observation tests passed; 15 host and 11
  vendor-host scenarios passed.
- Real-backend, isolated production UI: 13 headless Chromium tests passed.
- Broad browser regression at `c69835e0`: 108 passed, including both previously
  failing 3D checks. After the final initialization-status refinement, the six
  real-backend observation browser checks passed again.
- Full Python regression collected at `c69835e0`: 3632 passed, 13 skipped,
  106 deprecation warnings, zero failures (840.47 seconds). The last two narrow
  refinements were verified separately by the 63 final targeted tests and six
  real-backend browser checks, not credited to this earlier full-suite result.
  A redundant second full run was interrupted after those final checks; it is
  not counted as a completed pass.
- Final application: actual PlatformIO Core 6.1.18 ESP32 compile passed, with
  ELF and BIN emitted; all 15 host and 11 vendor-host scenarios passed, zero
  findings. Library properties confirm BME280 2.3.0, SSD1306 2.5.17, GFX 1.12.6,
  BusIO 1.17.4 and Unified Sensor 1.1.15.

The tracked-only export and final compiled source ZIP are byte-identical:

`60a17cfc23fce78cbb5777e5465e414b322e4c5823c39e08b65ebe3814acbd6c`

Local execution artifacts are ignored, under:

- `.cache/hardware-splicer/device-application/device-application-euadmriv/`
- `.cache/hardware-splicer/tracked-repair-qDX0u9/execution/`
- `.cache/hardware-splicer/frontend-verify-DLw6wf/` (real backend)
- `.cache/hardware-splicer/frontend-verify-a1FSan/` (mock backend)
- `.cache/hardware-splicer/frontend-verify-eUR6vj/` (final real observation checks)

Source ZIP determinism is established here, not reproducible ELF/BIN bytes.
Browser tests run in isolated build/output directories on dedicated test ports;
existing services and their builds were not restarted or replaced.

## Limits

This is compiler and modeled software evidence, not silicon or bench validation.
The 50 ms calibration deadline and Wire transaction timeout are software choices,
not verified physical timing. The adapter still blocks briefly during successful
initialization; the host's 250 ms loop budget does not guarantee a real bus bound.
Failed initialization cannot establish absence of a physical sensor.

Every emitted result retains `physical_correctness=UNPROVEN`,
`firmware_authorized=false` and `power_on_authorized=false`.
No flashing, powering, procurement, provider contact or physical authorization
was performed. These repair commits have not been pushed; no new GitHub CI pass
is claimed. The old head's aggregate workflow finished green, but its separate
device-browser workflow failed the two missing-CLI 3D checks.
