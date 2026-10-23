# KiCad native UUID transport contract (2026-10-24)

## Scope and trust boundary

This is the *next integration gate* following PR #213's 36 component centers and 79 native pin locations. It does **not** patch the third-party converter. Instead it enforces a fail-closed contract that any converter emitting native instance provenance must meet. The existing converter output is expected to fail the contract.

The verifier reads native .kicad_sch placed-symbol UUIDs, authenticates those UUIDs against an independent `kicad-cli` exported netlist, and compares each converter `source_component` and `source_port` with that native identity and the official exported sheet UUID path.

Required fields on **every** converter `source_component` and `source_port`:
- `native_kicad_symbol_uuid`: original native symbol instance UUID, not a freshly generated converter ID.
- `native_kicad_sheet_uuid_path`: exact sheet UUID path from KiCad's official netlist export.

Record relationships and port-number sets must remain complete. The gate fails closed if any record is missing an identity value, a value differs, an expected port is absent, or a component cannot be correlated.

## Negative controls

- The real unmodified upstream output lacks the required fields and must **not** pass.
- Synthetic fields copied from the source can satisfy the **consistency** contract, but **cannot** establish that the converter emitted them.
- Swapped UUID values, a removed port path, or a forged component sheet path fail the check.
- Manufacturing, visual-electrical geometry merge, and provenance authentication remain disabled even if the consistency contract passes.

## Next required implementation

Modify or wrap the *upstream parser boundary* (before component identity is lost) so that original source UUID and hierarchy path travel with the converter's initial component and port records. Do **not** assign them using a post-conversion position or reference join. Capture reproducible source/converter hashes and parser version; then test record permutations, duplicated symbols, hierarchical sheets, and modification of UUIDs **before** conversion. Only an independently validated upstream emission test can promote `original_converter_emission_proven` beyond false.

Run after installing genuine `kicad-cli` and the example's converter npm dependencies:

```bash
pytest -q tests/test_kicad_native_uuid_transport_contract.py
```

These tests have been committed but **not run from this session** because remote execution quota was unavailable. Full CI and dependency-stack review are outstanding. PR must remain draft.
