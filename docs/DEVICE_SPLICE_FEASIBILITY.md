# Hardware Splicer — whole-device splice feasibility v1

A bounded **paper engineering compatibility assessment** across power, signaling,
mechanical form factors, firmware, thermal estimates and preliminary PCB/enclosure
fit. It is not a general hardware simulator or a physical build/repair approval.

## Usage

Send a candidate to either the engine or product API:

```bash
curl -X POST http://localhost:8000/v1/splice/feasibility \
  -H "Content-Type: application/json" \
  --data-binary @eval/device_splice_feasibility/controller_display_demo.json
```

Or use the existing Python work-package compiler:

```python
package = compile_work_package(case, review, splice_candidate=candidate)
# package["device_splice_feasibility"] contains interfaces and required actions
```

## Reference cases

- `steamdeck_oled_ssd.json`: an actual named-device family, but only existing
  HS **source leads**, not authenticated technical specifications or a measured
  physical specimen. The matching declared 2230 form factor is a paper candidate;
  power, signaling, firmware, thermal and assembly work remain **unknown**.
- `controller_display_demo.json`: **entirely synthetic** 5V controller/display
  system. Nominal SPI/3.3V interfaces are declared, but a 5V-to-3.3V regulator
  candidate needs validation. Includes a preliminary synthetic envelope-fit
  result; not a real design or BOM.

The evaluator compares regulated supply voltage and load current, optionally
checks declared adapter input power against its output requirement, and aggregates
current from loads explicitly assigned to the same supply rail. This cannot
substitute for measurements, vendor documents, connector pinout mapping or
thermal/electrical safety testing.

## Decision statuses

| Status | Meaning |
| --- | --- |
| `compatible_on_paper` | Declared specifications match the tested interface, without physical verification. |
| `adaptable_pending_validation` | A declared adaptation plausibly addresses the modeled mismatch but has not been validated. |
| `unknown` | Missing specifications, evidence references, or entire required domains. |
| `blocked` | A known declared mismatch, exceeded rail budget, or reported enclosure interference. |

Whole-device priority is **blocked > unknown > adaptable > compatible_on_paper**.

Source references are not automatically authenticated. Preliminary fit results
are bounding-envelope screens, not exact 3D collision proofs. The evaluator
does not check wiring pin-by-pin, battery safety, connector mating, cable routing,
component authenticity, real firmware operation or physical assembly access.

All decisions preserve `power_on_authorized = false`,
`fabrication_authorized = false` and `release_authorized = false`.
A work package adds explicit unresolved tasks and verification gates; it does
not automatically execute them.
