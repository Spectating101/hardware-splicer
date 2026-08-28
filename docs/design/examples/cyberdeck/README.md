# Cyberdeck Design Fixtures

**Status: synthetic only. No physical cyberdeck has been built or verified by these files.**

Start here:

- `WORKED_EXAMPLE_DECK001.md` — canonical end-to-end dry run for one plausible modular Linux cyberdeck.
- `MULTI_OBJECTIVE_SORTING_EXPERIMENT.md` — same candidate resource pool re-ranked under lowest-cost, performance, reuse, portability, serviceability and minimum-risk objectives while preserving identical evidence/safety gates.
- `machine_project.example.json` — machine-readable synthetic `MachineProject` with intentionally unresolved interfaces and planned verification.

## Frozen conclusion

The first real cyberdeck benchmark should favor evidence-backed reuse over maximum reuse:

- reuse donor compute/cooling/input when identity and interfaces close;
- prefer manufacturer-validated native HDMI/USB/PCIe paths over novel high-speed redesign;
- reject or defer ambiguous raw display and battery hardware when the verification burden is not rational;
- let HS own system traceability, donor provenance, interface contracts, bounded glue electronics, mechanical fit gates, bench evidence, and release authority;
- keep battery/USB-C-PD, thermal, rich enclosure geometry, and novel high-speed-link work explicitly bounded until generic HS capability matures.

The sorting experiment adds one architectural conclusion: **the objective policy may change the preferred machine, but it may not weaken evidence or authority.** Current `resource_strategy.v1` already proves policy-swappable constrained/open/hybrid selection; a future generic extension should add richer objective vectors and Pareto alternatives rather than cyberdeck-specific ranking code.

No further cyberdeck implementation is authorized by this fixture. The next material step should be a real donor-backed physical project, not more synthetic expansion.
