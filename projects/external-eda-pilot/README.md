# External EDA engines × HS: a source-bound digital pilot

**20 November 2026.** This is a **real, executable integration test**, not a
general autonomous PCB generator and not a fabrication release. It exercises
external open-source EDA checkers on *actual* native KiCad source, then rebuilds
and verifies the dependent HS mechanical probe fixture. All external tools were
checked out at pinned commits and called from their local CLI wrappers; none
were installed into the host's global agent/plugin configuration.

## Evidence and observations

Specimen: the existing [HS SPI flash adapter](../../hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb),
a **90 × 50 mm** board with **18 exposed test pads on 16 nets**. The probe
fixture is the existing HS [bench-probe-fixture](../bench-probe-fixture/README.md).

| Case | KiSkill file parse | akcli schematic↔PCB | Native KiCad 9 DRC | Admission |
|---|---|---|---|---|
| Original source | Pass | Equivalent | 0 violations, 0 unconnected | **Pass** |
| TP12 +1 mm X, −1 mm Y with F.Cu repair trace | Pass | Equivalent | 0 violations, 0 unconnected | **Pass** |
| TP12 +2 mm X, without reroute | Pass | Equivalent | 4 violations, 1 unconnected | **Reject** |
| TP12 +2 mm X, direct F.Cu repair | Pass | Equivalent | 5 violations, 0 unconnected | **Reject** |
| TP12 deliberately changed to HOST_MISO net | Pass | **Not equivalent** | 4 violations, 1 unconnected | **Reject** |

**Important finding:** the previous purely mechanical TP12 +2 mm experiment
was **not a valid electrical source revision**. It made a correctly aligned
3D probe guide but broke PCB design rules. The independent KiCad DRC is the
necessary hard gate. Conversely, akcli detected a wrong-net assignment that
a file parser alone cannot detect.

The passing alternate board uses a short 0.25 mm-wide F.Cu trace from the
original TP12 junction to its new position. A bounded exploration checked
23 other candidate offsets/paths before finding this zero-DRC variant; see
[the exploration record](evidence/relocation-search.json). This is a single
engineering example, **not an optimization proof**.

Regeneration from the passing board produces two reopened STEP solids:
the **guide** moves exactly one bore, from **(60,12) mm to (61,13) mm**;
the **carrier** is geometrically identical (symmetric difference ≤1e−8 mm³).
All other 21 source locations, 18 contacts and 16 nets are preserved.
The [positive artifact](artifacts/passing_relocation.kicad_pcb) and
[probe-guide STEP](artifacts/probe-guide.step) can be inspected independently.

## Actual code and trust boundary

- [Verifier adapter](../../src/hardware_splicer/integrations/external_eda_verification.py):
  fixed, read-only KiSkill \`kx check\`, akcli \`verify\` and native \`kicad-cli pcb drc\`
  executed on exact **copied** input bytes. Commit and MIT LICENSE files are
  checked against [engine-lock.json](engine-lock.json) before execution.
  Outputs, hashes and verdicts go into separate per-case receipts.
- [Repeatable runner](run.py) generates both passing and fault controls with
  KiCad's native \`pcbnew\`, executes the adapter, generates STEP with the
  checked-in HS fixture builder, and audits STEP and layout consequences.
- [Independent STEP audit](verify_cad.py) re-opens CAD and compares actual
  bore geometry, carrier volume difference and input coordinates.
- [Unit tests](test_pilot.py) cover the decision gates, especially that
  CLI exit 0, parser success, or net-label equivalence alone cannot override
  nonzero DRC violations. **7/7 unit tests passed.**
- [Five-case evidence](evidence/pilot-summary.json) records the real
  engine executions and source hashes. External code is **not vendored**.
  See [Cite-Refinery candidate handoff](evidence/citerefinery-handoff.json).

The external processes are started under the current user. Copied input paths,
fixed command families, source-digest checks and pinned commits reduce risk,
**but this is not an OS-hardened sandbox**. Do not run unknown upstream
commits or private customer designs without stronger isolation and review.

## Reproduce on a machine with KiCad 9 and CadQuery

Review and clone the exact pinned versions of
[KiSkill](https://github.com/AvatarSD/KiSkill) and
[akcli](https://github.com/tipoLi5890/akcli). Do not run their installer scripts
for this pilot; the local bin wrappers suffice.

From the HS repository root, use an interpreter that imports KiCad \`pcbnew\`:

\`\`\`sh
/usr/bin/python3 projects/external-eda-pilot/run.py \
  --kiskill-repo /path/to/pinned/KiSkill \
  --akcli-repo /path/to/pinned/akcli \
  --cad-python /path/to/cadquery-venv/bin/python \
  --out /tmp/hs-external-eda-pilot
python3 projects/external-eda-pilot/test_pilot.py -v
\`\`\`

The pinned SHA-1 commit IDs are stored in \`engine-lock.json\`. The actual
verifier checks the Git commit, clean checkout and local LICENSE before using
external engines. The last run on the Optiplex used Python 3.13.5,
KiCad 9.0.2, CadQuery 2.6.1 and the pinned binaries.

**Not demonstrated:** autonomous prompt-to-PCB generation, a newly unseen PCB
case, physical pogo pin contact force or accuracy, toolhead assembly, actual
fabrication, powered electrical testing, manufacturing yield or a paid user.
A passing DRC does not prove circuit intent or safety. Cite-Refinery handoff is
a *candidate evidence packet*; it was not auto-ingested as an accepted graph edge.

## Integration decision

**ADAPT (pilot only)**: retain the lightweight read-only external checkers and
independent native KiCad authority as optional engine backends. Do not copy
upstream source into HS or claim functional superiority without held-out
comparisons and measured human effort. The next test should apply the same
runner to an **unseen board**, then a generator-kit measurement PCB or a
different mechanical assembly.