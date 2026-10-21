"""Parametric SolidCraft FDM casing plus PartCAD mechanical identity handoff.

Uses a small tested SolidCraft command subset: shell, screw/board bosses,
USB opening, separate ventilated lid, and clearance skirt.
Input dimensions are explicitly declared prototype assumptions, not measured
donor data; no physical print / electrical release is authorized.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

SCHEMA="hardware_splicer.printed_enclosure_workbench.v1"


def _number(item: Mapping[str,Any], name:str, minimum:float, maximum:float)->float:
    v=item.get(name)
    if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not minimum<=v<=maximum:
        raise ValueError(f"{name} must be a finite numerical value within {minimum}..{maximum} mm")
    return round(float(v),3)


def prepare_printed_enclosure(spec:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(spec,Mapping):
        raise ValueError("spec must be an object")
    if spec.get("evidence_type")!="DECLARED_CONCEPT_FIXTURE":
        raise ValueError("An unverified donor must not be promoted to a measured casing; supply a declared concept fixture")
    item=spec.get("geometry_mm")
    if not isinstance(item,Mapping):
        raise ValueError("geometry_mm must be an object")
    W=_number(item,"outer_width",45,220)
    D=_number(item,"outer_depth",45,220)
    H=_number(item,"base_height",18,100)
    wall=_number(item,"wall",1.6,4.0)
    lid_t=_number(item,"lid_thickness",1.6,4.0)
    lip_h=_number(item,"lip_height",1.0,3.5)
    lip_t=_number(item,"lip_thickness",1.0,2.2)
    gap=_number(item,"lip_clearance_per_side",0.2,0.8)
    boss_d=_number(item,"lid_boss_outer_diameter",6,12)
    boss_hole=_number(item,"lid_boss_pilot_diameter",2.0,4.0)
    margin=_number(item,"lid_boss_edge_offset",7,18)
    portw=_number(item,"port_width",8,20)
    porth=_number(item,"port_height",4,12)
    ventd=_number(item,"lid_vent_diameter",3,6)
    if W-2*(wall+gap+lip_t)<=22 or D-2*(wall+gap+lip_t)<=22:
        raise ValueError("case lip would leave too little interior space")
    if H < 4*wall + lip_h + 6:
        raise ValueError("height too small for hollow case and lid hardware")
    if boss_hole>=boss_d-3:
        raise ValueError("insufficient screw boss radial wall thickness")
    if margin-boss_d/2<wall+1:
        raise ValueError("boss cylinder crosses or approaches wall")
    if 2*margin+boss_d+4>=min(W,D):
        raise ValueError("boss layout does not fit case footprint")
    if portw+6>=D-2*margin or porth+8>=H-2*wall:
        raise ValueError("port collides with rim or boss region")
    # Interior lip fit relative to base's measured-by-model cavity dimensions:
    base_cavity=[W-2*wall,D-2*wall]
    lip_out=[W-2*(wall+gap),D-2*(wall+gap)]
    lip_in=[x-2*lip_t for x in lip_out]
    if min(lip_in)<=0:
        raise ValueError("lip would be degenerate")

    # Layout both solids on a common print bed; the lid is spaced beyond X.
    separation=12.0
    x0=W+separation
    boss_coords=[(margin,margin),(W-margin,margin),(W-margin,D-margin),(margin,D-margin)]
    # LID screw holes are placed directly above four corresponding bosses
    # after the mathematical 180-degree assembly rotation about X.
    # Print coordinates in lid are (x0+x, D-y) for final y on assembled base.
    lid_holes=[(x0+x,D-y) for x,y in boss_coords]
    vent_x=[x0+W*0.4,x0+W*0.6]
    vent_y=[D*0.33,D*0.50,D*0.67]
    for vx in vent_x:
        for vy in vent_y:
            if any(math.hypot(vx-hx,vy-hy)<=0.5*(ventd+boss_d)+1 for hx,hy in lid_holes):
                raise ValueError("vent would overlap a screw/boss")

    # Tall bosses approach the underside of the lid, leaving a deliberate
    # engagement gap so a selected screw can potentially bridge it.
    boss_top=H-2.4
    boss_height=round(boss_top-wall,3)
    if boss_height <= 3:
        raise ValueError("boss too short")
    commands=[]
    def add(command:str,params:dict):
        commands.append({"command":command,"params":params})

    add("solid.box",{"length":W,"width":D,"height":H,"body_name":"HS_Casing_Base"})
    add("solid.shell",{"faces":[[W/2,D/2,H]],"thickness":wall,"body":"HS_Casing_Base"})
    for x,y in boss_coords:
        add("plastic.boss",{"position":[x,y,wall],"diameter":boss_d,
                             "height":boss_height,"hole_diameter":boss_hole,
                             "body":"HS_Casing_Base"})
    # A sample internal PCB footprint with two pairs of short board standoffs.
    # Mount pattern is NOT evidence of any actual donor PCB.
    board_x=[W*0.33,W*0.67]
    board_y=[D*0.30,D*0.70]
    for x in board_x:
        for y in board_y:
            if any(math.hypot(x-bx,y-by)<(boss_d+6)/2+1 for bx,by in boss_coords):
                raise ValueError("board boss would interfere with a lid boss")
            add("plastic.boss",{"position":[round(x,3),round(y,3),wall],
                                "diameter":6,"height":5,"hole_diameter":2.5,
                                "body":"HS_Casing_Base"})
    add("solid.box",{"length":W,"width":D,"height":lid_t,
                     "corner":[x0,0,0],"body_name":"HS_Casing_Lid","operation":"new"})
    add("sketch.create",{"plane":"XY","offset":lid_t,"name":"HS_Lid_Alignment_Skirt"})
    add("sketch.rectangle.two_point",{"p0":[x0+wall+gap,wall+gap],
                                     "p1":[x0+W-wall-gap,D-wall-gap]})
    add("sketch.rectangle.two_point",{"p0":[x0+wall+gap+lip_t,wall+gap+lip_t],
                                     "p1":[x0+W-wall-gap-lip_t,D-wall-gap-lip_t]})
    add("sketch.finish",{})
    add("solid.extrude",{"sketch":"HS_Lid_Alignment_Skirt","distance":lip_h,
                         "operation":"join","targets":["HS_Casing_Lid"],"name":"HS_Lid_Skirt"})
    # Deliberate controlled rectangular cable exit on +X side.
    add("sketch.create",{"plane":"YZ","offset":W,"name":"HS_Cable_Exit"})
    add("sketch.rectangle.center",{"center":[D/2,H/2],"corner":[D/2+portw/2,H/2+porth/2]})
    add("sketch.finish",{})
    add("solid.extrude",{"sketch":"HS_Cable_Exit","distance":wall+1.5,
                         "direction":"negative","operation":"cut",
                         "targets":["HS_Casing_Base"],"name":"HS_Cable_Cutout"})
    for x in vent_x:
        for y in vent_y:
            add("solid.hole",{"position":[x,y,lid_t],"diameter":ventd,
                              "depth":lid_t+0.5})
    for x,y in lid_holes:
        add("solid.hole",{"position":[x,y,lid_t],"diameter":boss_hole+0.5,
                          "depth":lid_t+0.5})
    assemble_transform={"translate":[-x0,D,H+lid_t],"axis":[1,0,0],"angle":180}
    # The assembled lid plate occupies H..H+lid_t; lip projects down to
    # H-lip_h; base has hollow volume below H.
    assert math.isclose(x0+assemble_transform["translate"][0],0,abs_tol=1e-9)
    record={
        "schema_version":SCHEMA,
        "case_id":spec.get("case_id") if isinstance(spec.get("case_id"),str) else "hs_printable_controller_case",
        "input_sha256":hashlib.sha256(json.dumps(spec,sort_keys=True,allow_nan=False).encode()).hexdigest(),
        "source_confidence":"DECLARED_SOFTWARE_TEST_DIMENSIONS_NOT_SPECIMEN_MEASUREMENTS",
        "solidcraft_print_layout_commands":{"commands":commands},
        "solidcraft_assembly_transform":assemble_transform,
        "solidcraft_assembly_transform_commands":{"commands":[{"command":"solid.move","params":{
            "bodies":["HS_Casing_Lid"],**assemble_transform}}]},
        "bodies":["HS_Casing_Base","HS_Casing_Lid"],
        "case_dimensions_mm":{"width":W,"depth":D,"base_height":H,"wall":wall,"lid_thickness":lid_t},
        "print_layout_mm":{"lid_offset_x":x0,"part_separation":separation,"print_bed_bbox":[2*W+separation,D]},
        "cavity_dimensions_xy_mm":base_cavity,
        "lid_alignment_mm":{"lip_outside_xy":lip_out,"lip_inside_xy":lip_in,
                            "nominal_xy_gap_per_side":gap,"lip_depth":lip_h},
        "lid_boss_centres_assembled_xy_mm":boss_coords,
        "lid_screw_centres_print_layout_xy_mm":lid_holes,
        "lid_vent_centres_print_layout_xy_mm":[[x,y] for x in vent_x for y in vent_y],
        "cable_port_mm":{"face":"+X","y_centre":D/2,"z_centre":H/2,
                         "width":portw,"height":porth},
        "sample_internal_board_mount_centres_mm":[[x,y] for x in board_x for y in board_y],
        "screw_boss_top_z_mm":boss_top,
        "unverified_fit_warnings":[
            "All dimensions are hypothetical design choices; donor components were not measured",
            "Screw pilot size and length must be selected and verified for material and printer",
            "No cable strain-relief, EMI, water ingress or thermal airflow validation",
            "No physical print or lid assembly fit check",
            "Supports, overhangs, printer bed and slicer material settings remain unverified",
            "No FDM machine profile; never issue ready-to-print G-code without verified printer and review",
        ],
        "real_printer_connected":False,
        "slicing_performed":False,
        "printed":False,
        "test_fitted":False,
        "mechanical_production_release":False,
        "physical_power_authorized":False,
    }
    return record
