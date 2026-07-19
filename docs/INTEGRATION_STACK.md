# Evidence-first external integration stack

This package introduces a narrow integration boundary between Hardware Splicer's
own evidence/authority logic and optional specialist tools.

## Ownership boundary

Hardware Splicer owns:

- donor identity and provenance;
- observations and measurements;
- interface contracts;
- uncertainty and blockers;
- authority transitions;
- projection orchestration.

External tools own execution details such as firmware compilation, Circuit JSON
visualization, KiCad release generation and instrument communication.

External tools never promote a hypothesis into an authoritative fact.

## Donor virtual modules

Unknown donor blocks receive stable identifiers such as:

```text
donor:enabot-mainboard:dual-hbridge-01
```

A familiar catalog module may be recorded as a functional analogy, but its pins,
voltage limits and control semantics are not inherited.

## Integration path

1. Convert `functional_salvage.reusable_blocks` into partial interface contracts.
2. Emit a bench recipe for unresolved contacts and signal properties.
3. Record accepted observations and measurements in the evidence graph.
4. Mark an interface verified only when all firmware-critical properties are authoritative.
5. Generate PlatformIO, tscircuit and manufacturing projections from the verified contract.

## Verification

```bash
PYTHONPATH=src python scripts/verify_integration_stack.py
pytest -q tests/test_integration_stack.py
```
