# Hardware Splicer GitHub-source-native task routing — actual executed evidence

Two open-source engineering tools were routed from their respective objectives
and executed against a real HS-designed SPI flash adapter.

**The selector uses transparent deterministic rules, NOT an autonomous LLM.**

| Objective | Tool selected | Actual output | Status |
| --- | --- | --- | --- |
| Schematic inspection | akcli | 27 heuristic findings | Real upstream tool execution |
| Compare PCB revisions | kdif | 92,459-byte HTML diff | Real KiCad 9 rendering, networkless Docker |

## Input provenance and controlled revision

Source: HS's existing SPI flash adapter PCB. The baseline was a byte-for-byte
copy of the original HS product. The second private commit added ONLY an
F.SilkS test annotation. This is NOT a production design revision.

- Original PCB SHA-256: 86c0e72840b058b5dc4b56a820e560b306b2f624724a818e092fd1d003fdefbd
- Controlled baseline SHA: 460c147f5ccd1736060ca397642877625720e5a2
- Controlled annotated SHA: 552f7adfaeadde7b2e41d00fa4344989c3457c64
- kdif HTML SHA-256: 16e9fed55618a70c46a3c7f979f04376271a0e9b0c0b49e2d485864adc447202

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
