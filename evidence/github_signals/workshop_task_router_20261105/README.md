# Hardware Splicer GitHub-source-native task routing — actual executed evidence

Two open-source engineering tools were routed from their respective objectives
and executed against a real HS-designed SPI flash adapter.

**The selector uses transparent deterministic rules, NOT an autonomous LLM.**

| Objective | Tool selected | Actual output | Status |
| --- | --- | --- | --- |
| Schematic inspection | akcli | 27 heuristic findings | Real upstream tool execution |
| Compare PCB revisions | kdif | 92,043-byte HTML diff | Real KiCad 9 rendering, networkless Docker |

## Input provenance and controlled revision

Source: HS's existing SPI flash adapter PCB. The baseline was a byte-for-byte
copy of the original HS product. The second private commit added ONLY an
F.SilkS test annotation. This is NOT a production design revision.

- Original PCB SHA-256: 43a354a4624b69e8c26915680a69fea02b84e1b7e1e9816056522070c2269d24
- Controlled baseline SHA: 408da1c030b935d2e197b4db38c539c54623b1bb
- Controlled annotated SHA: 353d7b5756f900e7378d10527c7518c7b5f576e0
- kdif HTML SHA-256: 0c7a9ddb3c60f208b94c10239959904cd0958555a639c93a72a58fe5445939e7

### Regenerated 2026-11-15 for the legend-corrected board

The files in diff/ were first captured on 2026-11-05 against the SPI adapter
PCB with SHA-256 86c0e72840b058b5dc4b56a820e560b306b2f624724a818e092fd1d003fdefbd
(kdif HTML 16e9fed55618a70c46a3c7f979f04376271a0e9b0c0b49e2d485864adc447202,
92,459 bytes). The board's silkscreen was later brought within the fab's
legend limits, which changed the PCB bytes, so the comparison was run again
on 2026-11-15 with the same commands the hosted workflow uses
(`examples/github_signals/make_kdif_fixture.py`, then
`scripts/run_github_signal_task.py --fetch --sandbox docker` with the same
pinned kdif commit and digest-pinned KiCad image). The hashes above are from
that run. This run was local, not a hosted workflow run. The review/ files
are unchanged because the schematic did not change.

## Inspectable files

- review/: akcli task routing, source-pinned diagnostics, integrity verdict.
- diff/: kdif routing, interactive HTML, source-pinned execution provenance.
- HS_WORKSHOP_TWO_TASK_PROOF.json: normalized 2-task evidence and hashes.
- LICENSE-KDIF.txt: original kdif MIT license distributed with generated HTML.

Both upstream tools were pinned to reviewed commits and ran with networking
disabled and read-only engineering inputs. kdif was tested with real KiCad 9
both in bubblewrap and the digest-pinned official KiCad Docker image.

Unknown repositories, unreviewed commits and ambiguous objectives do not
execute. Physical authority and fabrication approval remain false.

Not demonstrated: autonomous LLM engineering reasoning, adoption of arbitrary
GitHub repositories, networked workshop scheduling, physical device control,
production PCB improvement, or a repaired physical product.
