"""Produce real authored STEP stand parts and a CADCLAW constraint assembly.

Only the dry reference stand, vendor housing EXTERNAL ENVELOPE and a conceptual
sampling vessel are authored. Actual bracket/port/pressure/seal joints are not
modeled and prevent release. This is NOT a manufactured filtration product.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from .product_ecosystem_bridge import load_product,canonical,require,sha


def author(root:Path,out:Path)->dict:
    import cadquery as cq
    import yaml

    product,receipt,render=load_product(root)
    out=Path(out).resolve()
    require(not out.exists() or not any(out.iterdir()),
            "do not overwrite previously authored CAD")
    out.mkdir(parents=True,exist_ok=True)
    parts=out/"parts"
    parts.mkdir()
    layout=product["layout"]
    tray=layout["tray"];panel=layout["back_panel"];housing=layout["filter_housing"];cup=layout["sample_cup"]
    # Geometries explicitly come from the pre-existing source revision.
    box=lambda dx,dy,dz:cq.Workplane("XY").box(dx,dy,dz,centered=False)
    solids={
       "tray":box(tray["width_mm"],tray["depth_mm"],tray["height_mm"]),
       "panel":box(panel["width_mm"],panel["thickness_mm"],panel["height_mm"]),
       "housing_envelope":cq.Workplane("XY").circle(housing["diameter_mm"]/2).extrude(housing["height_mm"]),
       "sample_concept":cq.Workplane("XY").circle(cup["diameter_mm"]/2).extrude(cup["height_mm"]),
    }
    extents={}
    for key,solid in solids.items():
        file=parts/(key+".step")
        cq.exporters.export(solid,str(file))
        check=cq.importers.importStep(str(file))
        bbox=check.val().BoundingBox()
        dims=(bbox.xlen,bbox.ylen,bbox.zlen)
        require(all(v>0 for v in dims),"native STEP part has nonpositive extent")
        extents[key]={"file":str(file.relative_to(out)),
                      "dims_mm":[round(v,3) for v in dims],
                      "sha256":sha(file.read_bytes()),
                      "status":"native_dry_concept_not_vendor_manufacturer_cad"}
    # CADCLAW connector frames are derived from *authored, rectangular* stand
    # STEP coordinates, not invented connector positions for Pentair hardware.
    connectors={
       "schema_version":"connector_metadata.v0.1",
       "components":[
         {"id":"tray","source_path":"parts/tray.step",
          "notes":"Analytic dry stand only. CAD frame verified against generated STEP box; no physical load tests.",
          "frames":[{"id":"back_top_seat","kind":"mount_face",
                     "origin_mm":[225.0,230.0,14.0],
                     "tags":["dry_concept","datum"],
                     "verified":True,
                     "notes":"Source tray z=14 and desired panel y=230; conceptual datum only."}]},
         {"id":"panel","source_path":"parts/panel.step",
          "notes":"Back panel only. No rated bracket mounts or screws.",
          "frames":[{"id":"front_bottom_seat","kind":"mount_face",
                     "origin_mm":[225.0,0.0,0.0],
                     "tags":["dry_concept","mating"],
                     "verified":True,
                     "notes":"Rectangular STEP part x-center, y-front, z-bottom."}]},
       ],
       "assumptions":[
          "Only tray/panel datum chain is constrained; this is a conceptual dry assembly.",
          "Housing cylinder is an external dimension proxy, not an imported Pentair STEP.",
          "Sampling vessel is shown at a design coordinate with no verified support connection.",
          "Exact housing bracket, fittings, pressure, and cartridges remain entirely unvalidated.",
       ],
    }
    spec={
       "schema_version":"assembly_spec.v0.1",
       "meta":{"project":"Hardware Splicer ClearBench S1 DIGITAL concept",
               "assembly_id":"clearbench_s1_dry_reference",
               "description":"Source-bound visual stand + unmounted housing envelope. Not product build ready."},
       "component_roots":[str(out)],
       "connector_metadata":str(out/"connectors.yaml"),
       "outputs":{"step":str(out/"clearbench_s1_dry_reference.step"),
                  "views_dir":str(out/"review_views")},
       "instances":[
          {"id":"tray","role":"dry_concept_tray",
           "source_path":"parts/tray.step",
           "transform":{"translate_mm":[0,0,0]},
           "notes":"450×260×14 mm conceptual non-pressurized support"},
          {"id":"panel","role":"dry_concept_panel",
           "source_path":"parts/panel.step",
           "place_relative_to":{"ref":"tray","parent_frame":"back_top_seat",
                                "frame":"front_bottom_seat","axis":"z",
                                "side":"positive","offset_mm":0.0,"lock":"frame"},
           "notes":"Constraint placed using actual authored STEP box frame (no known fasteners)"},
          {"id":"housing_envelope","role":"manufacturer_external_envelope_only",
           "source_path":"parts/housing_envelope.step",
           "transform":{"translate_mm":[160,130,228]},
           "notes":"Floating Pentair 158007 outer envelope, mounting entirely unqualified"},
          {"id":"sample_concept","role":"conceptual_sample_vessel",
           "source_path":"parts/sample_concept.step",
           "transform":{"translate_mm":[370,95,32]},
           "notes":"Visual cup, no measured fixture attachment"},
       ],
       "not_built_yet":[
           {"item":item,"reason":reason,"required_for_release":True}
           for item,reason in (
            ("verified_Pentair_mount","Exact 158007/244047 bracket hole pitch, load path and screw geometry missing"),
            ("rated_fluid_path","Actual pressure rated fittings, tubes, valve, O-rings, leak controls missing"),
            ("service_sweep","Manufacturer-accepted wrench/sump clearance and dry service measurements missing"),
            ("treatment_efficacy","No 0.5 L/min flow or 70-percent turbidity tests were performed"),
            ("source_STEP_authenticity","Vendor housing STEP not available; proxy outer envelope only"),
            ("instrumentation","Two pressure gauges are unqualified visual locations, not assembled parts"),
           )
       ],
       "assumptions":[
          "Dry parts are generated by CadQuery from the HS product source (not procured or structural-tested).",
          "No vendor mechanical mating, certified fluid pressure, or manufacturing readiness is asserted.",
          "Unknown mounting and seal interfaces remain unbuilt rather than filled with invented holes.",
       ],
    }
    for name,value in (("connectors.yaml",connectors),("assembly.yaml",spec)):
        (out/name).write_text(yaml.safe_dump(value,sort_keys=False))
    report={
       "schema_version":"hardware_splicer.cadclaw_dry_assembly_input.v1",
       "product_id":product["product_id"],
       "source_spec_sha256":receipt["product_spec_sha256"],
       "authored_step_parts":extents,
       "assembled_with_CADCLAW_yet":False,
       "native_vendor_step_authored":False,
       "fit_mating_verified":False,
       "hydraulic_pressure_safety_verified":False,
       "release_blockers_count":len(spec["not_built_yet"]),
       "physical_release_authorized":False,
    }
    (out/"CADCLAW_INPUT_RECEIPT.json").write_bytes(canonical(report))
    return report
