# KiCad hierarchical source-integrity challenge — 2026-10-24

**Objective:** Compete by reliably reusing real, existing KiCad engineering designs rather than reimplementing a schematic parser from scratch. Validate actual multi-sheet and repeated-subcircuit connectivity, component reference integrity, pin identities and separation from unproven visual geometry.

**Status:** Executed official KiCad 9.0.8 demo exports; accurate source-topology and instance-scope interoperability on **3 test projects**. **Not** PCB manufacture, physical repair, manufacturer sign-off or general KiCad compatibility.

## Real external source tests, not hand-authored synthetic schematics

Installed the official Ubuntu `kicad-demos` package alongside **KiCad CLI 9.0.8**, then invoked `kicad-cli sch export netlist --format kicadsexpr` directly on **KiCad's upstream-owned demo files**. The source schematics are part of KiCad's software distribution, not designed to flatter HS. No demo source files were copied into this repository.

| Original KiCad demo | Sheet instances | Original component refs | Original net documents | Connected nets | Connected REF.PIN memberships | Real recovered parity |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `complex_hierarchy/complex_hierarchy.kicad_sch` | 3 | 68 | 52 | **50** | **162** | Exact |
| `flat_hierarchy/flat_hierarchy.kicad_sch` | 3 | 64 | 117 | **34** | **161** | Exact |
| `multichannel/multichannel_mixer.kicad_sch` | 5 | 114 | 80 | **79** | **279** | Exact |
| **Total** | **11** | **246** | **249** | **163** | **602** | **Exact** |

Note: the flat-hierarchy netlist contains **77 ordinary single-pin NC nets and six special unnumbered mounting-hole contacts**, which are not electrical multi-pin connections. The complex-hierarchy export has 2 ordinary single-pin nets; the multi-channel export has 1. The exact-parity score is over **connected named multi-pin nets and their complete REF.PIN sets**. Unconnected and unnumbered contacts are preserved separately in source metadata and receipts; never counted as connected or invented as fake contacts. `source_numbered_pin_memberships` includes the single-pin ordinary NC nets (flat: 238) and not the six unnumbered mounting holes.

### Repeated schematic identity

KiCad's multichannel mixer repeats the same source `channel_strip.kicad_sch` in four independent sub-sheet instances `/CH1/`, `/CH2/`, `/CH3/`, `/CH4/`. Each instance has **26 independent reference-designated component instances**, with 10 components in the root design. The corrected HS KiCad parser now retains:
- `kicad_sheet_name` and `kicad_sheet_uuid_path` on each component from real KiCad `(sheetpath (names ...) (tstamps ...))` declarations,
- source symbol `(tstamps ...)` values for traceability, separate from sheet instance identifiers,
- source `(design (sheet ...))` declarations and child schematic filenames.

The recovery bridge maps a source sheet-instance name to Circuit JSON `subcircuit_id` for each **distinct exported reference**, then checks that the resulting HS-imported components preserve these scopes. It never merges separate components simply because they share the same KiCad library symbol or source sheet file. The measured per-channel component counts were `26/26/26/26`.

### Real failure and constrained repair: unnumbered disconnected pins

KiCad's flat-hierarchy demo exports six legitimate mounting-hole symbols such as `(node (ref "HOLE1") (pin "") (pinfunction "1") (pintype "passive+no_connect"))` on one-terminal disconnected nets. The earlier PR #209 importer rejected the whole real netlist as malformed.

The new parser only accepts an empty pin identifier if **all** conditions hold:
1. KiCad explicitly supplies an empty `(pin "")` field;
2. the `pintype` explicitly contains `no_connect`;
3. the net has exactly one `node`, and its name begins with `unconnected-`;
4. the reference belongs to an actual exported component (checked at recovery).

It preserves the raw source `net`, `ref`, empty pin, `pinfunction` and `pintype` in a separate `source_unnumbered_no_connect_nets` manifest. It never fabricates a physical pin number. Unknown references, blank pins on connected nets, ordinary passive pins with no number, multiple-node net aliases, or unrelated empty nets **fail closed**.

### Identity collision protection

Circuit JSON source-port IDs are stable deterministic ordinals over sorted source REF.PIN pairs, not an unescaped concatenation. `U_1.pin2` versus `U.pin1_2` cannot collide. Every component reference and its sheet-instance scope is checked after the full roundtrip.

### Actual API behavior

The generated source-authoritative Circuit JSON was also passed to the **real HS** `POST /v1/interchange/circuit-json/inspect` endpoint for each design:
- all three returned HTTP 200, `status=ready`, `compilable=true`,
- HS summaries contained 50, 34 and 79 imported nets respectively, with 0 reported unresolved source graph references,
- `authority=proposed`. **This means SOURCE INTERCHANGE readiness only**, not KiCad ERC/DRC approval or manufacturability.

No third-party converter visual geometry was merged. As established in PR #209, upstream `kicad-to-circuit-json` 0.0.144 can generate visual schematic traces but lacks actual `source_trace` connectivity on the single-sheet SPI-flash example. This PR checks KiCad's own electrical authority and refuses to elevate unmatched visual coordinates into real wires.

## Reproducibility and installed source requirements

From the HS repository:

```bash
sudo apt-get install kicad kicad-demos
pip install -e '.[dev]'
python benchmarks/kicad_hierarchy_20261024/run_official_demos.py \
    --demo-root /usr/share/kicad/demos \
    --out /tmp/hs_hierarchy_results.json
pytest -q tests/test_kicad_hierarchy_recovery.py
```

Actual measured summary saved in `benchmarks/kicad_hierarchy_20261024/actual_kicad9_demo_execution_receipt.json`, including source file hashes, count evidence and pass/fail gates. The full uncompressed execution output also includes *netlist export hashes*, which can change if KiCad inserts a fresh timestamp; the source schematic SHA256 is the reproducible identity anchor.

Demo-dependent tests deliberately **skip** when `kicad-demos` or `kicad-cli` is not installed (standard CI need not have these extra OS packages). Independent synthetic edge-case guards always execute.

**87 targeted tests passed** in an isolated environment with the demos installed, including existing Circuit JSON import and API, electrical interchange, netlist compile, source-bound repair evidence and new multi-sheet negative controls. Two existing warning classes appear (FastAPI TestClient deprecation and duplicate OpenAPI operation ID), neither claimed fixed in this scope. Full GitHub Actions CI is a separate merge gate.

## Competitive interpretation and remaining work

This constitutes **real improvements in source interoperability across independent open-source KiCad design examples**. It does **not** establish that HS is better than KiCad or Flux; we reused KiCad's official export and independently preserved the result. This test gives HS a stronger foundation for a future full engineering/repair workflow.

Further work:
- Trace the converter's visual `schematic_component` back to original symbol UUID/ref and each port to exact KiCad `REF.PIN`. The current converter does not export explicit KiCad symbol UUID or component designator in its `source_component` records; **do not merge unmatched geometry by order, approximate position or mere library name**.
- Extend the test corpus to hierarchical labels and buses on independently selected schematic families. Current tests cover three official KiCad projects, not every KiCad format feature.
- Independently confirm PCB routing, ERC/DRC, BOM, firmware, physical measurements and actual repair outcomes before any build-ready claim.
- Compare a genuinely finished HS deliverable with a competitor's authorized export under equal requirements, rather than claiming market leadership from import tests.

**Verdict:** topology and component-instance fidelity passed a much harder external-source challenge. Visual-geometry identity and physical engineering superiority remain unresolved.
