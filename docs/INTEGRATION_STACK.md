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
pytest -q \
  tests/test_integration_stack.py \
  tests/test_evidence_salvage_bridge.py \
  tests/test_evidence_bench_gates.py
```

## Frontend authority workbench

The Studio Verify stage now contains an evidence workbench for salvage projects. It is intentionally absent from greenfield projects.

The workbench presents:

- donor virtual module identity;
- known contacts and evidenced signals;
- reference-only catalog analogies;
- unresolved authority fields;
- firmware and power-on authorization;
- the required measurement sequence;
- tscircuit, PlatformIO, and KiBot backend readiness.

Older salvage packages receive a conservative client-side fallback. A legacy donor-bound `l298n` row is shown as blocked and never interpreted as an inherited electrical contract.

The UI links directly into the existing Bench stage. It does not duplicate bench measurement storage or create a second authority system.

## Bench integration

Canonical interface contracts are translated into the existing splice Bench session:

- recipe measurements become measurable Bench gates;
- structural contract fields become explicit authority gates;
- structural gates cannot be closed by submitting an arbitrary scalar value;
- power-on remains blocked until both contract structure and required measurements are resolved.

## Authority invariants

1. A functional analogy never inherits an electrical contract.
2. Firmware generation requires accepted signal voltage, polarity, and controller-pin evidence.
3. `InterfaceContract.recompute_status()` promotes a contract only from authoritative signal facts; it does not depend circularly on an already-verified status.
4. tscircuit is a projection, not the canonical truth store.
5. PlatformIO is blocked until every active donor signal is firmware-authorized.
6. KiBot readiness means a manufacturing backend is available, not that fabrication has been authorized.
7. Physical power-on remains a separate Bench authority transition.
8. Legacy catalog modules remain available only as a compatibility graph projection; `authority_resolved_modules` contains canonical `donor:*` identities.

## Plugged-in tools (registry)

`src/hardware_splicer/data/external_tools.json` (`hs_external_tools`, `python -m hardware_splicer.external_tools`) lists
every outside tool and dataset HS plugs in: role (routing, checking, CAD, interface, fab, data, direction), licence, how
HS uses it (copied in, run as a separate program, or read only), status (integrated, measuring, installing, candidate,
reference) and what it measured, with the record that holds the numbers. Copyleft tools run only as separate programs;
a project with no licence is read and cited, never copied. Routing now tries FreeRouting, then KiCadRoutingTools with
the board's net-class widths (`krt_route`), then Copper (`copper_route`); each result is judged by HS's own finish, DRC
and track-current check, never by the router's report.

Agents on other machines reach the toolbelt over MCP through SSH: `ssh optiplex
/home/phyrexian/.local/share/hardware-splicer/hs-mcp.sh` runs the MCP server from a clean copy of `main` with the
routers configured (set up 28 Nov 2026 for Backplane on the laptop).
