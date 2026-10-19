# Intact reuse: first runnable non-catalog deliverable

Implementation frozen for the recorded control at
`aa715807fc6b355c0e46bbadbf0b5dac5d225fed`, on existing PR #138.
The earlier cold-agent trial remains unchanged; this is a new capability and a
scripted protocol demonstration, not a newly passed live-model trial.

## Actual artifact

The real canonical MCP server produced and returned
[intact-input-review.zip](generated/intact-reuse-2026-10-19/intact-input-review.zip)
(4,830 bytes):

`0751000fb19909800564e3a84c8bd9f0887abeda4e40392f43ba4b772ea7cc29`

Nine scripted MCP calls discovered the new schema, proposed the native design,
executed its software check, read back the hashed result and downloaded the
exact ZIP. Its delivered tests were then independently replayed from extraction.
All seven scenarios passed, checking action positions as well as counts.
The package contains a standard-library Python normalized-event adapter,
contract/design/source identities, replay tests/results, example events and
instructions. The example emits one symbolic `activate` action.

This uses a real donor reference and the frozen host-paraphrased document packet,
not an ESP32/Pico/module substitution. Source bytes are re-verified before the
bundle is made. The source packet SHA-256 is
`b98f9a76a04dc4a97addf69fb25d3e54255c03d5a6b01052ef2f5c2c8d4057c5`.
No actual donor is present or claimed. An external-actuator mechanism is a
proposal in the contract, not a measured construction.

## Verification

- Mission/store/executor/delivery/API/onboarding plus intact reuse: **181 passed**.
- Final intact reuse tests after fixing direct-script import shadowing:
  **25 passed** (overlapping subset plus one new entrypoint test; do not sum).
- Four seeded adapter faults are rejected. The first mutation run exposed a
  count-only blind spot for wrong-device activity. The delivered tests now
  require the expected action-emitting input indices, closing that gap.
- Actual MCP build/read/download and independent delivered replay: **passed**.
- ZIP output is byte-identical for identical frozen spec, source revision and
  mission identity. Different missions have different bound identities and may
  correctly produce different hashes.

Run the standalone bundle check with:

```bash
python docs/status/generated/intact-reuse-2026-10-19/VERIFY.py
```

[RESULT.json](generated/intact-reuse-2026-10-19/RESULT.json) preserves all nine
tool request/response payloads, the implementation commit/file hashes, exact
ZIP identity and its original run-artifact hash. No operator credential or
machine-specific path is included. Host setup accepted only a synthetic
software-check budget; the MCP client did not receive that credential. The
script closed its own server and removed its temporary project after retaining
the proof. Reproduce with `scripts/smoke_intact_reuse_mcp.py --output <new-dir>`
in the dedicated backend-MCP SDK2 environment.

## Boundary still outstanding

The adapter consumes normalized logical events. It does **not** enumerate a
mouse, decode a USB descriptor, provide an actual HID/evdev bridge, inject OS
keys, execute action names, or generate dimensioned CAD/wiring. Mechanical
force/travel/load, actual device mapping and application integration are still
unverified. No physical procedure was executed. Software replay cannot prove
signal behavior, debouncing, host timing, usability or device safety.

Software review bundles use the existing mission artifact/package store and are
available before READY, but cannot satisfy or bypass the existing READY build
package, inventory, donor-verification, staging or physical-authorization gates.
A failed native check permits a bounded repair; unresolved physical warnings
alone do not. No snapshot, donor contract or measurement is promoted.

This closes the specific “only a plan, no runnable artifact” gap for one bounded
reuse class. It does not complete arbitrary intact-device reuse, actual host
integration or the e-waste product demonstration. A fresh-agent usability
rerun against this version is **NOT RUN**.
