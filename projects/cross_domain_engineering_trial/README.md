# Hardware Splicer: real cross-domain engineering flexibility trial (2026-10-21)

**Purpose:** prove whether one HS **software-engineering operator path** can work on unrelated real devices, not just a drone demo or a cyberdeck shell. The original [HS charter](../../docs/HARDWARE_SPLICER_MISSION_FREEZE.md) remains authoritative. No physical device was purchased, modified or powered during this trial.

## What actually ran

All three projects were created using the **same canonical HS project store, source ingestion API, content-hash verification, source-bundle analyzer, model-project session API and explicit-acceptance software action executor**. Project choice supplies only the user mission and real upstream files. Source formats select the corresponding engineering tool, rather than the project name selecting a fabricated demo build.

| Project | Actual registered source inputs | Real HS engineering output | Native AI action executed |
| --- | --- | --- | --- |
| **Cyberdeck** | `sector07-dev/RPI_DEV` complete KiCad project and binary STL; `therebelrobot/dinodeck-2026` public reference BOM | 26 components/47 nets, **43 ERC** findings, **16 DRC** findings, 5,180 STL triangles, source-BOM arithmetic contradiction | `inspect_registered_sources`, `run_erc`, then a second native-session **`generate_board_carrier_candidate`** |
| **Drone** | Holybro X500 V2 manufacturer STEP (24,624,144 B) and `colgecen/DroneSkeleton` S500 OpenSCAD arm data | **244 actual STEP BREP solids** imported by CadQuery/OpenCascade; donor arm **56,896** mesh points and source coordinate envelope | `inspect_registered_sources` (second model session after exact-source-alias fix) |
| **PSP-300x UMD repair** | The 709 KB original iFixit drive-replacement HTML guide, case-specific URL below | **42** real indexed repair steps, with battery isolation/fasteners/ribbon/display/drive-access references and source anchors | `inspect_registered_sources` |

The model sessions were run with tools-disabled GitHub Copilot as the model provider. They were **real provider calls**, not mocked responses. The AI proposed actions; only software analysis/CAD *candidate* operations were accepted by the supervising assistant under the user's instruction to test and fix HS. The model did not receive fabrication, electrical power, flashing or sales authority. The proposed tool action itself went through the native project decision/execution endpoints, and the hardware source content hashes were independently checked before execution.

## Real generated CAD artifact

In the second cyberdeck AI session, Copilot proposed `generate_board_carrier_candidate`. HS exported the exact registered board as a KiCad STEP model, measured its bounds using OpenCascade and generated a new **parametric PCB envelope-carrier** in two independently inspectable formats:

- [3D STEP candidate](./artifacts/cyberdeck/pcb_envelope_carrier_candidate.step)
- [STL candidate](./artifacts/cyberdeck/pcb_envelope_carrier_candidate.stl)
- [CAD numerical result and hashes](./artifacts/cyberdeck/carrier_candidate_report.json)

The board STEP bbox measured **90.9 × 61.3 × 1.51 mm**; proposed carrier bbox **97.9 × 68.3 × 7.5 mm**, 1.25 mm nominal XY gap. OCCT reported a valid solid. The carrier is *not* yet equipped with verified mounting-hole positions, board retention, actual component height clearance, material/screw selection or geometric mating to the unknown-unit front-case STL. It should **not** be represented as a ready-to-print finished enclosure or an independently tested fit.

## Engineering and integration bugs identified / addressed

1. **Lost KiCad project settings caused 211 false-comparable DRC findings**, versus 16 with the real project; solved by hash-pinned sibling file staging. ERC/DRC are presented as findings, not certification.
2. **STEP imports were missing** and the 16 MiB upload cap excluded manufacturer CAD; source cap now 32 MiB and an isolated, pinned Python 3.12 CadQuery/OpenCascade CAD kernel can parse the X500 original STEP. Tool absence remains a failed source check, not silently a pass.
3. **Repair docs and donor OpenSCAD** were not routed through a common source analysis operation; now handled through bounded, hash-verified formats and no raw guide text transmitted to the model.
4. **AI couldn't execute relevant source checks** beyond guided-plan/compose; expanded action vocabulary and acceptance-gated executor with `inspect_registered_sources`, `run_erc`, `run_drc`, and `generate_board_carrier_candidate`.
5. **Model source identifier hallucinations** blocked an initial drone action, correctly. New source aliases `S1`, `S2` are bound exactly to registered IDs; unknown citations are surfaced, not fuzzily corrected or promoted.
6. **Alternative cyberdeck source BOM arithmetic** did not reconcile: six category figures sum to $193–270, contrary to its own advertised $140–230 excluding enclosure. These are vendor-*unverified* examples, not current purchase quotes.

## Key remaining limitations

| End-to-end engineering outcome | Result |
| --- | --- |
| Source interpretation across three different engineering domains | **Demonstrated** with actual upstream files |
| AI planning and actual safe software tool execution across all three | **Demonstrated**, still explicitly accepted rather than fully autonomous |
| Source-dependent generation of a new editable CAD part | **Demonstrated for the cyberdeck** (candidate only) |
| Source-verified complete hybrid cyberdeck/device design | **Not achieved** |
| Drone donor-to-frame interface solution with verified mounting and propulsion | **Not achieved** |
| Diagnosis/repair of a physically inspected PSP | **Not achieved** — guide indexing is not a diagnosis |
| Actual buy/repair/resale margin on an acquired device | **Not achieved** |
| Physical build, flight, power-on, sale or durability verification | **Not performed** |

**Do not claim this project passed overall autonomous engineering.** This is a real flexibility result at source/agent/software-tool level, and a verified new parametric design file, but the device-level finish gate is still blocked. The next project targets are actual measured mounting/connector interfaces, complete power BOM with current ratings and realistic vendor quotes, then source-specific repair or assembly validation on a real physical unit.

## Reproduction on authorized Optiplex

Provided the original upstream files are re-acquired and put at the paths in the runner manifest:

```bash
scripts/bootstrap_hs_cad_kernel.sh
for CASE in cyberdeck drone psp; do
  PYTHONPATH=src .venv/bin/python scripts/run_hs_cross_domain_engineering.py "$CASE" --out-root /tmp/hs-cross-domain-new-run
  HARDWARE_SPLICER_LLM_PROVIDER=copilot_cli PYTHONPATH=src .venv/bin/python scripts/run_hs_cross_domain_agent.py "$CASE" --root /tmp/hs-cross-domain-new-run
done
```

The source check can be replayed offline once the sources are retained, while the AI action step requires a configured, working model provider; output decisions may vary across model runs. Real external reference links: [X500 V2 frame](https://holybro.com/collections/multicopter-kit/products/x500-v2-kits), [DroneSkeleton](https://github.com/colgecen/DroneSkeleton), [RPI_DEV](https://github.com/sector07-dev/RPI_DEV), [DinoDeck](https://github.com/therebelrobot/dinodeck-2026), [PSP 300x UMD repair guide](https://www.ifixit.com/Guide/PSP+300x+UMD+Drive+Replacement/1586).

`run_summary.json` preserves the short derived evidence and action result summaries (without copying publisher files). Full original source bytes and raw model transcripts remain on the user's authorized Optiplex under `/tmp/hs-cross-domain-20261021/` and the project store.

### Cross-project budget correction

The source-BOM checker **does not assume US$250 globally**. A budget limit is read from each saved project's `constraints.max_cost_usd` (when present); otherwise the result reports no asserted cap. Changing the cap invalidates the corresponding cached economic review without changing the source hashes. The cyberdeck project's **provisional** cap was explicitly declared as $250 in its persisted trial input. A test independently verified that the same $400–650 source estimate evaluates differently under $250 and $800 ceilings, without importing either into the other project.

The CAD kernel is provisioned into a persistent user-managed Python 3.12 environment by [`scripts/bootstrap_hs_cad_kernel.sh`](../../scripts/bootstrap_hs_cad_kernel.sh); no publisher CAD is included in Git. Re-execution still requires the external source files and external software dependencies.
