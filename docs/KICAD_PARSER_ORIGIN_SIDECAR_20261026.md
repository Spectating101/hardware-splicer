# HS: parser-origin UUID transport prototype (2026-10-26)

## Exact intervention

Upstream dependency: `tscircuit/kicad-to-circuit-json`, pinned in HS at npm version `0.0.144`. The source-reviewed insertion point is `lib/stages/schematic/CollectLibrarySymbolsStage.ts`. Unlike earlier proof-by-position, this stage receives `symbol.uuid` from the original `kicadts` parse and sees the generated component and port record IDs while they are made.

`patch_upstream_origin_stage.py` applies signature-checked modifications to an upstream **source checkout**, not the installed compiled npm package. It records source UUID → generated component/port IDs in a separate in-memory parser-origin sidecar. The converter receives a `getNativeOriginSidecar()` access method. A separate `convert_with_origin.mjs` runner refuses an unpatched converter and refuses incomplete/double-counted component/port mappings.

The standalone Circuit JSON documents remain unchanged so standard output schema validation isn't bypassed with invented fields.

## Reproduction once upstream source checkout and build tools are available

1. Check out the upstream converter at the reviewed commit `65774ff199155916554538fe0f495557c6747b91`.
2. Run `python examples/integrations/kicad-circuit-json/patch_upstream_origin_stage.py /path/to/upstream` from HS. The tool rejects changed stage signatures rather than guessing.
3. Build that instrumented upstream package with its documented tooling. Install/link **that local build**, not the unmodified npm package, into the HS example environment.
4. Run `node examples/integrations/kicad-circuit-json/convert_with_origin.mjs source.kicad_sch output.json origin.json`.
5. Test `pytest -q tests/test_kicad_parser_origin_stage_patch.py` independently.

## What is and is not proven

This captures authentic native **symbol UUIDs at the parser conversion boundary** and relates them to generated IDs. But KiCad hierarchical sheet instance paths are **not** yet available in the captured contract, so the field is intentionally `null`. It must never be reconstructed from screen coordinates or source-component order. The converter's multiple-sheet input behavior remains insufficiently validated; sheet-path provenance and independent source-vs-export comparison are required before the earlier #216 contract can authenticate full identities.

The full upstream fork's compilation and real conversion tests have **not been executed** from this environment. The limited regression suite tests patch mechanics only. Keep this draft. Reject any claim that this is a production-ready converter patch or a release/fabrication authority.
