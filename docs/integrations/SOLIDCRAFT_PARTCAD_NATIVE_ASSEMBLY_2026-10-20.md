# Real Hardware Splicer / SolidCraft / PartCAD integration

Executed October 20, 2026 on connected Linux Optiplex.
This is an actual external CAD and assembly package operation, NOT a
physically assembled device or a completed multi-donor repair.

## External executable versions

- Official SolidCraft v0.16.2 (mechanical CAD GUI, CLI, MCP).
- Published PartCAD 0.8.220 in a disposable /tmp virtual environment.
- Latest PartCAD repository checkout was 0.8.224; that version was NOT
  published to the configured Python index, so testing pinned 0.8.220.
- PartCAD first STEP export installed CadQuery in a separate sandbox
  and took around 104 seconds; subsequent cached end-to-end run was
  approximately 10 seconds.

## Actual round-trip

The existing SolidCraft demo produced a genuine native editable
SolidCraft document and a STEP source file representing a 120 x 80 x 25
millimeter box. The dimensions are explicitly invented SOFTWARE TEST
dimensions and DO NOT come from any salvaged scanner/printer/NAS.

PartCAD imported the STEP in a local PartCAD package with:
- one named part, concept_envelope
- one named assembly, conceptual_station
- one part link, concept_envelope_instance

The actual PartCAD BOM command reported exactly one part, count 1,
no supplier and no SKU. The source hash stayed unchanged during
copy/import. Physical specimen ID was null, usable quantity 0.
PartCAD exported a NEW STEP (15,444 bytes vs 5,074-byte input).

SolidCraft independently opened the exported STEP and confirmed:

| Property | Source | PartCAD export |
| --- | --- | --- |
| Solid bodies | 1 | 1 |
| Extents, mm | 120 x 80 x 25 | same |
| Solid volume, cubic mm | 240000 | 240000 |
| Surface area, square mm | 29200 | 29200 |
| Center of mass, mm | 60,40,12.5 | same |
| Faces | 6 | 6 |
| Edges | 12 | 12 |

Important semantic loss: PartCAD STEP exporter changed the body
name to a generic STEP translator body name. It did NOT recreate
SolidCraft parametric sketch/extrude timeline. Thus preserve original
editable SolidCraft document and HS / PartCAD stable component IDs.
Do not claim feature-history roundtrip.

## Actual SolidCraft desktop trial

Launched the real official SolidCraft Linux GUI in a separately
contained virtual graphical display (Xvfb). Loaded the editable
native document. The browser, body tree, sketch and feature timeline
rendered. Captured an authentic desktop screenshot:
examples/partcad/native_trial/SOLIDCRAFT_DESKTOP_LIVE.png.
Vulkan logged a DRI3 warning; nonetheless the GUI loaded and
captured correctly. The temporary GUI process was terminated after
capture and was not left running.

This establishes that the existing CAD user interface is viable,
not that our HS-specific side panels are already inside it.

## Reproduce

Install PartCAD in isolated environment:

    uv venv --python 3.13 /tmp/hs-partcad-venv
    uv pip install --python /tmp/hs-partcad-venv/bin/python partcad==0.8.220

From HS repo root:

    PYTHONPATH=src python -m scripts.run_solidcraft_partcad_bridge --out /tmp/new-hs-partcad-case --pc /tmp/hs-partcad-venv/bin/pc --solidcraft-cli /path/to/solidcraft-cli

Runner checks STEP header and source hash; writes PartCAD YAML
and native ASSY; executes real PartCAD lists/BOM/export; then
invokes SolidCraft to evaluate the exported solid. A native CLI
failure is not converted to a passing answer.

Without --pc the script only creates file package and evidence.
Without --solidcraft-cli it does not claim roundtrip geometry verified.
The native export is expensive on first use.

## Integration ownership

SolidCraft GUI: viewport, native editable CAD, mechanical assembly.
PartCAD: versioned components/assembly relationships and design BOM.
HS: source identity, provenance, salvaged-part confidence, measured
interface contracts, electrical/SPICE/firmware/bench authority gates.
InvenTree may supply actual physical inventory records in a later
strictly observed integration, not fake stock from seller URLs.

The user could retire most custom mechanical viewport development.
However the HS evidence and electrical/bench workflows must remain
accessible. At present there is NOT a single unified SolidCraft/HS/
PartCAD app window; integration is through tested CLI, MCP and files.

No donor was acquired or measured; no electrical compatibility,
mechanical fit, manufacturing authority or functioning novel device
was established. Next target is a measured multi-part assembly and
cross-referenced HS evidence/PartCAD part IDs in the SolidCraft UI.

Proof: docs/evaluations/SOLIDCRAFT_PARTCAD_NATIVE_ROUNDTRIP_2026-10-20.json
Files: examples/partcad/native_trial/
