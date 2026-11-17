"""Author the Fielddeck 7 device, not an HS backend feature.

Run in the existing native CadQuery environment from any working directory.
Manufacturer display geometry is MIT licensed; its license accompanies outputs.
Other purchased modules use explicitly identified nominal envelope models.
"""
from pathlib import Path
import json
import math
import hashlib
import itertools

import cadquery as cq
import numpy as np
import trimesh
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "cad"
SPEC = json.loads((ROOT / "design.json").read_text())
W, D, H = [SPEC["case_mm"][key] for key in ("width", "depth", "height")]
T = SPEC["case_mm"]["floor"]


def validate_fixed_geometry(spec):
    """Reject geometry changes this authored layout cannot safely rearrange.

    Study currents/targets may vary. Module relocation and size changes require
    an authored revision, rather than hashing new JSON over unchanged solids.
    """
    expected={
      'case_mm':{'width':310,'depth':285,'height':64,'floor':3,'wall':3,'lid':3,'split_x':155,'split_y':140,'seam_gap':.3},
      'display':{'mpn':'SC1635','centre_xy':[155,210],'front_z':62,'aperture_mm':[184.32,115.24],'native_front_z':5.02,'native_centre_y':2.935},
      'pi':{'mpn':'SC0193','ram_gb':2,'board_mm':[85,56,1.6],'rotation_deg':90,'origin_xy':[60,198],'pcb_bottom_z':7,
            'holes_local_xy':[[3.5,3.5],[61.5,3.5],[3.5,52.5],[61.5,52.5]]},
      'keyboard':{'mpn':'1736','dimensions_mm':[285,123,22],'centre_xy':[155,78],'top_z':62},
      'power_bank':{'mpn':'A1259','dimensions_mm':[104,52.3,26],'world_min':[16,25,4],'world_rotation_deg':90},
      'fan':{'mpn':'NF-A4x10 5V PWM','dimensions_mm':[40,40,10],'centre_xy':[32,230.5],'bottom_z':51,'mount_pitch_mm':32}}
    for section,fields in expected.items():
        for field,value in fields.items():
            if spec.get(section,{}).get(field)!=value:
                raise ValueError(f'Unsupported fixed-layout geometry change: {section}.{field}; author a new layout before regeneration')


def box(x, y, z, a, b, c):
    return cq.Workplane("XY").box(a,b,c,centered=(False,False,False)).translate((x,y,z)).val()


def cylinder(x,y,z,r,h):
    return cq.Workplane("XY").circle(r).extrude(h).translate((x,y,z)).val()


def hexhole(x,y,z,af,h):
    return cq.Workplane("XY").polygon(6,af/math.cos(math.pi/6)).extrude(h).translate((x,y,z)).val()


def pinut(x,y):
    return cylinder(x,y,-1,1.4,12).fuse(hexhole(x,y,0,5.2,2.2))


def world_pi(x,y):
    return (60-y,198+x)


def screen_xy(x,y):
    return (157.935-y,210+x)


def round_rect(x,y,z,a,b,c,r):
    result=cq.Workplane("XY").box(a,b,c,centered=(True,True,False))
    if r:
        result=result.edges("|Z").fillet(r)
    return result.translate((x,y,z)).val()


def joined(shapes):
    result=shapes[0]
    for shape in shapes[1:]:
        result=result.fuse(shape)
    return result.clean()


def mesh(shape):
    vertices,faces=shape.tessellate(.25,.2)
    return trimesh.Trimesh(np.array([[v.x,v.y,v.z] for v in vertices]),np.array(faces),process=True)


def exact_bounds(shape):
    # Ignore display/render triangulation deflection when locating exports.
    bounds=Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped,bounds,False,False)
    return cq.BoundBox(bounds)


def overlap_volume(a,b):
    # OCC may return coincident faces for seated parts. Shape.Volume() on a
    # face is not an intersection volume; count closed common solids only.
    return sum(s.Volume() for s in a.intersect(b).Solids())


def author():
    validate_fixed_geometry(SPEC)
    OUT.mkdir(exist_ok=True)
    (OUT/"print").mkdir(exist_ok=True)
    parts=[]

    def add(name,shape,color,kind,notes="",printable=False):
        if not shape.isValid() or shape.Volume()<=0:
            raise ValueError("Invalid device solid: "+name)
        parts.append(dict(name=name,shape=shape,color=color,kind=kind,notes=notes,printable=printable))

    # Actual manufacturer STEP, rotated from portrait to landscape. Native
    # glass is at z=5.02; source origin is 2.935 mm off the glass centre.
    native=cq.importers.importStep(str(ROOT/"sources/touch_display2_7inch.step")).val()
    display=native.rotate((0,0,0),(0,0,1),90).translate((157.935,210,56.98))
    add("touch_display_2_manufacturer",display,(30,34,39,255),"manufacturer_step","Raspberry Pi MIT reference; approximate vendor geometry, not physical metrology.")

    # Keyboard and power bank are intentionally nominal envelopes. Render-only
    # keys are separate meshes; they are not used as invented fit data.
    keyboard=box(12.5,16.5,40,285,123,22)
    add("keyboard_nominal_envelope",keyboard,(28,31,37,255),"purchased_envelope","Adafruit 1736 published 285 x 123 x 22 mm.")
    bank=round_rect(42.15,77,4,52.3,104,26,6)
    add("power_bank_nominal_envelope",bank,(65,70,81,255),"purchased_envelope","Anker A1259; buttons/ports are not inferred from the envelope.")

    # Pi board coordinates come from the official mechanical drawing. Rotating
    # its 85 mm axis rearwards puts USB/Ethernet directly at the rear access slot.
    pi_local=round_rect(42.5,28,7,85,56,1.6,3)
    for x,y in SPEC["pi"]["holes_local_xy"]:
        pi_local=pi_local.cut(cylinder(x,y,6,1.375,4))
    pi=pi_local.rotate((0,0,0),(0,0,1),90).translate((60,198,0))
    add("pi4_board_envelope",pi,(36,111,70,255),"purchased_envelope","Board outline and mounting pattern from manufacturer; not a detailed electrical model.")
    pi_connectors=[("usb_a_lower",(69,-.3,8.6,18.7,15,16)),
                   ("usb_a_upper",(69,17.7,8.6,18.7,15,16)),
                   ("ethernet",(65,38,8.6,22.7,16,13.5)),
                   ("gpio",(7,50.5,8.6,51,5,8.5)),
                   ("usb_c",(7.5,-2,8.6,9,8,3)),
                   ("dsi",(.3,18,8.6,4,16,5.5)),
                   ("microsd",(0,20,5.0,14,16,2))]
    for name,args in pi_connectors:
        shape=box(*args).rotate((0,0,0),(0,0,1),90).translate((60,198,0))
        add("pi4_"+name,shape,(160,166,172,255),"purchased_envelope","Conservative connector proxy; exact plug/cable dimensions remain separate keep-outs.")
    cpu=box(23,18,8.6,19,19,2.4).rotate((0,0,0),(0,0,1),90).translate((60,198,0))
    add("pi4_soc_envelope",cpu,(56,60,65,255),"purchased_envelope")

    # Fan frame, motor and clearance envelope. USB adapter is supplied with
    # this precise 5 V PWM model; no custom regulator or control circuit.
    fan=box(12,210.5,51,40,40,10).cut(cylinder(32,230.5,50,17,12))
    fan=fan.fuse(cylinder(32,230.5,51,7,10))
    for x,y in itertools.product((16,48),(214.5,246.5)):
        fan=fan.cut(cylinder(x,y,50,1.6,12))
    add("fan_envelope",fan,(154,121,86,255),"purchased_envelope","Noctua NF-A4x10 5V PWM, 40 x 40 x 10; rotor details omitted.")

    # Source-measured positions, not hand-estimated holes in an imported mesh.
    outer_holes=[screen_xy(x,y) for x,y in itertools.product((-35.355,35.355),(-67.065,72.935))]
    pi_holes=[world_pi(*p) for p in SPEC["pi"]["holes_local_xy"]]
    lid_holes=[(x,y) for y in (7,146.5,278) for x in (7,147,163,303)]
    lid_holes=[(78,y) if x==7 and y==278 else (x,y) for x,y in lid_holes]
    lid_holes=[(140 if x==147 else 170 if x==163 else x,y) if y==146.5 else (x,y) for x,y in lid_holes]
    # Source photos show narrow edge margins. Under-keyboard hook-and-loop
    # retention avoids putting guessed retaining lips over working keys.
    clamp_holes=[]
    top_holes=lid_holes+clamp_holes

    tray=box(0,0,0,W,D,H-3).cut(box(3,3,3,W-6,D-6,H))
    # Display posts have an underside tool shaft and 3 mm seat. 6 mm screws
    # engage the display lugs without traversing the full ~50 mm post.
    for x,y in outer_holes:
        post=cylinder(x,y,3,5,49.54)
        post=post.cut(cylinder(x,y,-1,3,50.54)).cut(cylinder(x,y,49.54,1.4,5))
        tray=tray.fuse(post).cut(cylinder(x,y,-1,3,50.54))
    for x,y in pi_holes:
        tray=tray.fuse(cylinder(x,y,3,3.5,4)).cut(pinut(x,y))
    for x,y in top_holes:
        boss=cylinder(x,y,3,5,58).cut(cylinder(x,y,3,1.6,60))
        # The nut must pull against a printed roof to retain the face. An
        # open-top pocket would let the tightened face and nut lift together.
        direction=1 if x<W/4 or W/2<x<3*W/4 else -1
        pocket=hexhole(x,y,56.6,5.8,2.6)
        entry=box(x if direction>0 else x-6,y-2.9,56.6,6,5.8,2.6)
        boss=boss.cut(pocket.fuse(entry))  # 1.8 mm roof ends at Z61
        tray=tray.fuse(boss)

    # Columns end at z=38; 2 mm hook-and-loop pads support the z=40 underside.
    for x,y in itertools.product((28,110,210,282),(20,135)):
        tray=tray.fuse(box(x-5,y-5,3,10,10,35))
    # Open, removable bank nest; 1 mm radial allowance. Two 20 mm straps are
    # threaded through floor slots, keeping charging electronics unmodified.
    for x in (13,69.3):
        tray=tray.fuse(box(x,22,3,2,110,8))
    for y in (22,130):
        tray=tray.fuse(box(13,y,3,58.3,2,8))
    for x,y in itertools.product((10,74),(51,105)):
        tray=tray.cut(box(x-1.5,y-11,-1,3,22,6))

    # Rear I/O remains physically accessible; adjacent return window brings
    # the keyboard/fan leads back inside without crushing them at a seam.
    tray=tray.cut(box(3,281,5,73,6,25))
    # Right-side exhaust area exceeds the 36 mm inlet's open circular area.
    for y in range(181,262,10):
        tray=tray.cut(box(306,y,14,6,7.5,24))
    # The rotated Pi's microSD ejects towards -Y, into the enclosure. Service
    # it with the keyboard/rear face removed; do not claim a left-wall slot.

    # Six internal seam plates with actual through-fastener holes.
    join_centres=[(155,y,"x") for y in (35,110,185,260)]+[(x,140,"y") for x in (90,245)]
    join_holes=[]
    for index,(x,y,axis) in enumerate(join_centres):
        a,b=(40,20) if axis=="x" else (20,40)
        plate=box(x-a/2,y-b/2,3,a,b,3)
        offsets=list(itertools.product((-8,8),(-5,5))) if axis=="x" else list(itertools.product((-5,5),(-8,8)))
        for dx,dy in offsets:
            px,py=x+dx,y+dy; join_holes.append((px,py))
            plate=plate.cut(cylinder(px,py,2,1.6,5))
            tray=tray.cut(cylinder(px,py,-1,1.6,5))
        add("seam_plate_"+str(index+1),plate,(105,119,132,255),"custom","M3 x 10 with nuts above plate; heads below floor.",True)

    lid=box(0,0,61,W,D,3)
    lid=lid.cut(round_rect(155,78,60,287,125,5,3))
    lid=lid.cut(box(150,137,59,10,14,7))
    lid=lid.cut(round_rect(155,210,60,184.32,115.24,5,5))
    # A 0.3 mm glass clearance under the lip prevents the bezel from passing
    # through (or clamping directly onto) the sourced glass solid.
    lid=lid.cut(round_rect(155,210,60,190.52,121.44,2.3,8.6))
    lid=lid.cut(cylinder(32,230.5,60,18,6))
    for x,y in top_holes+list(itertools.product((16,48),(214.5,246.5))):
        lid=lid.cut(cylinder(x,y,60,1.6,6))

    # 0.30 mm assembly seams, four floor and four top pieces, all <220 mm.
    regions=[("front_left",0,155,0,140),("front_right",155,310,0,140),
             ("rear_left",0,155,140,285),("rear_right",155,310,140,285)]
    for name,x0,x1,y0,y1 in regions:
        eps=.15
        left=x0+(eps if x0 else 0); right=x1-(eps if x1<W else 0)
        front=y0+(eps if y0 else 0); rear=y1-(eps if y1<D else 0)
        region=box(left,front,-1,right-left,rear-front,H+3)
        add("tray_"+name,tray.intersect(region).clean(),(47,59,70,255),"custom","Print floor down; nut pockets and underside tool access included.",True)
        add("face_"+name,lid.intersect(region).clean(),(204,112,44,255),"custom","Flat underside on bed. Screen lip captures inactive bezel only.",True)

    for index,(x,y) in enumerate(clamp_holes):
        left=x<155
        clip=box(0 if left else 294,y-6,64,16,12,3).cut(cylinder(x,y,63,1.6,5))
        add("keyboard_retainer_"+str(index+1),clip,(204,112,44,255),"custom","3.5 mm nominal edge overlap; confirm outer-key/bezel clearance on physical keyboard. 2 mm vertical free play.",True)

    guard=box(10,208.5,64,44,44,2).cut(cylinder(32,230.5,63,18,5))
    for offset in (-12,-6,0,6,12):
        bar=box(14,230.5+offset-.7,64,36,1.4,2).intersect(cylinder(32,230.5,64,18,2))
        guard=guard.fuse(bar)
    for x,y in itertools.product((16,48),(214.5,246.5)):
        guard=guard.cut(cylinder(x,y,63,1.6,5))
    add("fan_guard",guard.clean(),(204,112,44,255),"custom","M3 x 25 screws clamp guard, face, fan and 2 mm duct flange; nuts below flange.",True)
    duct=box(10,208.5,25,44,44,28).cut(box(11.5,210,24,41,41,31))
    # A bolted flange carries the duct. The 2 mm sleeve overlap locates it;
    # adhesive alone is not the load path. Assemble on the loose face first.
    flange=box(10,208.5,49,44,44,2).cut(cylinder(32,230.5,48,18,4))
    for x,y in itertools.product((16,48),(214.5,246.5)):
        flange=flange.cut(cylinder(x,y,48,1.6,4))
    duct=duct.fuse(flange).clean()
    add("fan_duct",duct,(75,91,104,255),"custom","2 mm flange bolted below fan, 0.5 mm sleeve clearance; preassemble with rear-left face, no PCB contact.",True)
    for i,(x,y) in enumerate(((16,16),(294,16),(16,269),(294,269))):
        add("foot_"+str(i+1),cylinder(x,y,-6,8,6),(55,61,66,255),"custom","Adhesive transfer tape to floor; clears seam screw heads by 3 mm.",True)

    # Inventory and actual solid intersections. Intended fastener engagement,
    # source module self-contacts and zero-volume seating contacts are excluded.
    conflicts=[]
    custom=[p for p in parts if p["kind"]=="custom"]
    bought=[p for p in parts if p["kind"]!="custom"]
    for a,b in itertools.product(custom,bought):
        overlap=overlap_volume(a["shape"],b["shape"])
        if overlap>.05:
            conflicts.append({"custom":a["name"],"module":b["name"],"overlap_mm3":round(overlap,3)})
    for a,b in itertools.combinations(custom,2):
        overlap=overlap_volume(a["shape"],b["shape"])
        if overlap>.05:
            conflicts.append({"custom":a["name"],"custom_other":b["name"],"overlap_mm3":round(overlap,3)})
    for a,b in itertools.combinations(bought,2):
        if a['name'].startswith('pi4_') and b['name'].startswith('pi4_'):
            continue  # Intentional board/component seating within one module.
        overlap=overlap_volume(a['shape'],b['shape'])
        if overlap>.05:
            conflicts.append({'module':a['name'],'module_other':b['name'],'overlap_mm3':round(overlap,3)})
    part_rows=[]
    assembly=cq.Assembly(name="Fielddeck_7")
    scene=trimesh.Scene()
    for part in parts:
        name=part["name"];shape=part["shape"];color=part["color"]
        assembly.add(shape,name=name,color=cq.Color(*[v/255 for v in color]))
        m=mesh(shape);m.visual.face_colors=np.array(color,dtype=np.uint8)
        scene.add_geometry(m,node_name=name,geom_name=name)
        b=exact_bounds(shape)
        row={"name":name,"kind":part["kind"],"notes":part["notes"],"solids":len(shape.Solids()),
             "volume_mm3":round(shape.Volume(),3),"bounds_mm":[round(v,3) for v in (b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax)],
             "printable":part["printable"]}
        if part["printable"]:
            local=shape.translate((-b.xmin,-b.ymin,-b.zmin))
            step=OUT/"print"/(name+".step");stl=OUT/"print"/(name+".stl")
            cq.exporters.export(local,str(step));cq.exporters.export(local,str(stl),tolerance=.15,angularTolerance=.15)
            row.update(print_dimensions_mm=[round(v,3) for v in (b.xlen,b.ylen,b.zlen)],
                step_sha256=hashlib.sha256(step.read_bytes()).hexdigest(),stl_sha256=hashlib.sha256(stl.read_bytes()).hexdigest())
            if len(shape.Solids())!=1:
                conflicts.append({"part":name,"reason":"custom part contains disconnected solids","count":len(shape.Solids())})
            if b.xlen>220 or b.ylen>220:
                conflicts.append({"part":name,"reason":"print exceeds nominated 220 mm bed"})
        part_rows.append(row)
    assembly.save(str(OUT/"FIELDDECK_7.step"))
    scene.export(str(OUT/"FIELDDECK_7.glb"))
    expected={p["name"]+ext for p in parts if p["printable"] for ext in (".step",".stl")}
    for old in (OUT/"print").iterdir():
        if old.suffix in (".step",".stl") and old.name not in expected:
            old.unlink()
    report={"device_name":"Fielddeck 7","parts":part_rows,"collision_findings":conflicts,
            "display_case_mount_centres_mm":outer_holes,"pi_mount_centres_mm":pi_holes,
            "top_fastener_centres_mm":top_holes,"seam_fastener_centres_mm":join_holes,
            "manufacturer_display_step_used":True,"physical_fit_verified":False,
            "source_spec_sha256":hashlib.sha256((ROOT/"design.json").read_bytes()).hexdigest(),
            "source_author_sha256":hashlib.sha256((ROOT/"author_cad.py").read_bytes()).hexdigest(),
            "source_vendor_step_sha256":hashlib.sha256((ROOT/"sources/touch_display2_7inch.step").read_bytes()).hexdigest(),
            "face_nut_pockets":{"insertion":"side_loaded_before_faces","pocket_bottom_z_mm":56.6,"pocket_top_z_mm":59.2,"roof_thickness_mm":1.8},
            "fan_mount_stack_mm":{"guard":2,"face":3,"fan":10,"duct_flange":2,"nut":2.4,
                                  "screw_under_head_length":25,"tip_beyond_nut":5.6},
            "fastener_model_scope":"Nominal head, nut, shank and tool envelopes checked independently by verify_device.py; threads and flexible cables are not complete solid models."}
    (OUT/"geometry_report.json").write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({"parts":len(parts),"custom_parts":len(custom),"findings":conflicts}))
    return report


if __name__=="__main__":
    author()
