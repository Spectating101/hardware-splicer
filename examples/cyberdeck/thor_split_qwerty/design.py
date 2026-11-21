"""Parametric Thor twin-side QWERTY — reality-bounded engineering study.

Source is a 50MB external community STL, NOT an internal STEP:
https://handheldmodz.com/scans/  -> Thor Open.stl

The exported STL source SHA and dimensions MUST be verified. In particular,
the display cutout and 2D mounting target rectangles are *interpretations*;
they do not prove controller-board depth, glass edge, case clips, hinge travel,
switch clearance or a fabricable modified Thor.

Generates 50-key design manifests, two mechanically modeled configurations,
actual KiCad two-layer matrix PCBs and a vector overlay diagram.

Use: python design.py --scan /tmp/hs-thor-open-reference-20261109.stl
"""
from __future__ import annotations

import argparse,csv,hashlib,json,math,struct
from pathlib import Path
from typing import Any

import numpy as np

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/"generated"
SOURCE_URI="https://handheldmodz.com/content/files/2025/11/Thor-Open.stl"
EXPECTED_SHA="42800c73d5e0523961f243e482732fcd2ba119c6e3aeae55659d7adee32e8402"

# Projection of front surface, manually segmented from scan outline; values
# are not raw exact triangulated glass bounds.
FRONT={"lower_half_x_mm":[-74.66,77.75],
       "lower_half_y_mm":[-74.4,-1.0],
       "lower_screen_x_keepout_mm":[-35.25,39.0],
       "hinge_keepout_y_above_mm":-8.0,
       "bottom_recess_keepout_y_below_mm":-70.0,
       "measured_by":"segmentation of exterior open scan; provisional +-2mm",
       "internal_keepouts_known":False}
KEYS={
 "left":[["Q","W","E","R","T"],["A","S","D","F","G"],["Z","X","C","V","B"],
         ["1","2","3","4","5"],["SHIFT","CTRL","ALT","TAB","FN"]],
 "right":[["Y","U","I","O","P"],["H","J","K","L",";"],["N","M",",",".","/"],
          ["6","7","8","9","0"],["SYM","SPACE","ENTER","BSPC","ESC"]],
}
MODES={
  "flush_7mm":{
    "pitch_x":7.0,"pitch_y":10.5,"keycap_mm":[5.5,7.0],
    "pcb_mm":[36.0,57.0],"board_top_y":-10.0,
    "boards_x":{"left":-72.7,"right":40.0},
    "use":"in-body replacement if internal cavities and lid actually clear",
  },
  "detachable_9mm":{
    "pitch_x":9.0,"pitch_y":11.0,"keycap_mm":[8.0,8.0],
    "pcb_mm":[47.0,58.0],"board_top_y":-10.0,
    "boards_x":{"left":-84.5,"right":41.0},
    "use":"detachable external thumb wings, not closed-lid internal parts",
  },
}
# Board-local row0 y=6.0, row4 y=48/50mm. Diodes at y+4.0,
# row vias at y+6.5. Allows first keyboard boards to be laid out natively.
KEY_TOP_Y=6.0
SWITCH_FOOTPRINT="Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2"
DIODE_FOOTPRINT="Diode_SMD:D_SOD-123"
TEST_PAD_FOOTPRINT="TestPoint:TestPoint_Pad_D1.0mm"
DIODES="1N4148W in SOD-123 (tentative, BOM validation required)"


def read_scan(path:Path)->dict[str,Any]:
    content_size=path.stat().st_size
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    sha=h.hexdigest()
    if sha!=EXPECTED_SHA:raise ValueError(f"unexpected/modified community scan SHA: {sha}")
    with path.open("rb") as f:
        header=f.read(84)
    count=struct.unpack("<I",header[80:84])[0]
    if count*50+84!=content_size:
        raise ValueError("STL byte length inconsistent with triangle count")
    dt=np.dtype([("normal","<f4",(3,)),("vertices","<f4",(3,3)),("flags","<u2")])
    tris=np.memmap(path,mode="r",offset=84,dtype=dt)
    coords=tris["vertices"].reshape(-1,3)
    minima=coords.min(axis=0).tolist()
    maxima=coords.max(axis=0).tolist()
    extent=(coords.max(axis=0)-coords.min(axis=0)).tolist()
    if not 145<extent[0]<160 or not 170<extent[1]<185 or not 30<extent[2]<36:
        raise ValueError("STL axis/scale cannot be matched to Thor exterior")
    return {"file":path.name,"sha256":sha,"source_url":SOURCE_URI,
        "triangle_count":count,"xyz_min_mm":[round(float(v),3) for v in minima],
        "xyz_max_mm":[round(float(v),3) for v in maxima],
        "xyz_extent_mm":[round(float(v),3) for v in extent],
        "mesh_exterior_not_internal_cavity":True,
        "maker_scan_no_mount_or_depth_certification":True}


def rectangles(mode:dict,side:str)->list[dict[str,Any]]:
    x0=mode["boards_x"][side]
    w,h=mode["pcb_mm"]
    row_y=KEY_TOP_Y
    x_center0=(w-4*mode["pitch_x"])/2
    return [{
       "id":f"{side[0].upper()}{r*5+c+1:02d}",
       "label":KEYS[side][r][c],"row":r,"col":c,
       "pcb_xy_mm":[round(x_center0+c*mode["pitch_x"],3),round(row_y+r*mode["pitch_y"],3)],
       "case_center_xyz_mm":[
          round(x0+x_center0+c*mode["pitch_x"],3),
          round(mode["board_top_y"]-row_y-r*mode["pitch_y"],3),None],
    } for r in range(5) for c in range(5)]


def rect_intersects(a,b)->bool:
    return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]


def measure_fit(modeid:str,mode:dict)->dict[str,Any]:
    capw,caph=mode["keycap_mm"]
    reported=[]
    critical=[]
    for side in ("left","right"):
        keys=rectangles(mode,side)
        x0=mode["boards_x"][side]
        w,h=mode["pcb_mm"]
        rect=[x0,mode["board_top_y"]-h,x0+w,mode["board_top_y"]]
        screen=[FRONT["lower_screen_x_keepout_mm"][0],-71.0,
                FRONT["lower_screen_x_keepout_mm"][1],-8.0]
        if rect_intersects(rect,screen):
            critical.append(side+": board crosses assumed lower-screen boundary")
        for k in keys:
            x,y,_=k["case_center_xyz_mm"]
            cr=[x-capw/2,y-caph/2,x+capw/2,y+caph/2]
            if rect_intersects(cr,screen):
                critical.append(k["id"]+": cap overlaps the screen keepout")
        edge_left=FRONT["lower_half_x_mm"][0]
        edge_right=FRONT["lower_half_x_mm"][1]
        external_left=max(0.0,edge_left-rect[0])
        external_right=max(0.0,rect[2]-edge_right)
        reported.append({
           "side":side,"pcb_rect_case_xy_mm":[round(x,3) for x in rect],
           "pcb_width_mm":w,"pcb_height_mm":h,
           "keycap_count":25,
           "keycap_pitch_mm":[mode["pitch_x"],mode["pitch_y"]],
           "lateral_extension_outside_case_mm":
             round(external_left if side=="left" else external_right,3),
           "screen_edge_gap_mm":round(screen[0]-rect[2] if side=="left" else rect[0]-screen[2],3),
           "outer_case_edge_gap_mm":round(rect[0]-edge_left if side=="left" else edge_right-rect[2],3),
           "proposed_board_near_hinge_gap_mm":round(-8.0-rect[3],3),
           "proposed_board_near_bottom_gap_mm":round(rect[1]+70.0,3),
           "keys":keys,
        })
    minimum_screen_gap=min(v["screen_edge_gap_mm"] for v in reported)
    minimum_lower_gap=min(v["proposed_board_near_bottom_gap_mm"] for v in reported)
    minimum_hinge_gap=min(v["proposed_board_near_hinge_gap_mm"] for v in reported)
    return {"variant":modeid,
      "min_screen_edge_gap_mm":minimum_screen_gap,
      "min_hinge_keepout_gap_mm":minimum_hinge_gap,
      "min_bottom_keepout_gap_mm":minimum_lower_gap,
      "provisional_2mm_clearance_gate": all(g>=2.0 for g in
          (minimum_screen_gap,minimum_lower_gap,minimum_hinge_gap)),
      "provisional_fit_status":"NO_SCREEN_OVERLAP_BUT_NOT_CLEARANCE_QUALIFIED",
      "layout":"5 columns x 5 rows on each side of existing lower screen",
      "total_keys":50,"layout_is_true_split_QWERTY":True,
      "original_two_screens_unchanged":True,"used_exterior_scan":True,
      "internal_mounting_clearance_verified":False,
      "closed_lid_clearance_verified":False,
      "controller_board_removal_verified":False,
      "battery_and_heat_shield_unmodified":True,
      "switch_footprint":"C&K KMR2 series; 4.6x2.8 mm body, 1.9mm height",
      "keycap_mounting_to_switch_verified":False,
      "keyboard_power_and_antenna_verified":False,
      "computed_2D_screen_overlap_pass":not critical,
      "2D_critical":critical,"sides":reported}


def create_kicad(modeid:str,side:str,mode:dict):
    import pcbnew as p
    pcb=p.BOARD()
    # F/Cu and B/Cu matrix. Physical 5x5 keys with per-key diode.
    w,h=mode["pcb_mm"]
    folder=OUTPUT/modeid
    folder.mkdir(exist_ok=True,parents=True)
    # Add +50 mm offset in native .kicad_pcb: does not affect physical PCB.
    ox,oy=50.0,50.0
    def P(x,y):return p.VECTOR2I(p.FromMM(ox+x),p.FromMM(oy+y))
    nets={}
    for s in (["COL"+str(n) for n in range(5)] + ["ROW"+str(n) for n in range(5)] +
              [f"KEY_{i:02d}" for i in range(25)]):
        net=p.NETINFO_ITEM(pcb,s);pcb.Add(net);nets[s]=net
    def footprint(lib,name,x,y,ref,value,assigned):
        fp=p.FootprintLoad("/usr/share/kicad/footprints/"+lib+".pretty",name)
        if fp is None:raise RuntimeError("uninstalled KiCad native footprint "+name)
        fp.SetReference(ref);fp.SetValue(value)
        fp.SetPosition(P(x,y))
        pcb.Add(fp)
        for pad in fp.Pads():
            number=pad.GetNumber()
            if number in assigned:pad.SetNet(nets[assigned[number]])
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        return fp
    def track(points,net,layer,width=.20):
        for a,b in zip(points,points[1:]):
            seg=p.PCB_TRACK(pcb)
            seg.SetStart(P(*a));seg.SetEnd(P(*b))
            seg.SetLayer(layer);seg.SetWidth(p.FromMM(width))
            seg.SetNet(nets[net]);pcb.Add(seg)
    def via(x,y,net):
        v=p.PCB_VIA(pcb);v.SetPosition(P(x,y));v.SetWidth(p.F_Cu,p.FromMM(.6))
        v.SetDrill(p.FromMM(.3))
        v.SetViaType(p.VIATYPE_THROUGH)
        v.SetLayerPair(p.F_Cu,p.B_Cu)
        v.SetNet(nets[net]);pcb.Add(v)
    def pad(x,y,net,ref):
        # exposed PTHless solder pad, not a finished detachable connector.
        fp=footprint("TestPoint","TestPoint_Pad_D1.0mm",x,y,ref,net,{"1":net})
        fp.SetLayer(p.F_Cu if net.startswith("COL") else p.B_Cu)
        return fp
    # Board perimeter.
    corner=[(0,0),(w,0),(w,h),(0,h),(0,0)]
    for a,b in zip(corner,corner[1:]):
        edge=p.PCB_SHAPE(pcb);edge.SetShape(p.SHAPE_T_SEGMENT)
        edge.SetStart(P(*a));edge.SetEnd(P(*b));edge.SetLayer(p.Edge_Cuts)
        edge.SetWidth(p.FromMM(.05));pcb.Add(edge)
    first=(w-4*mode["pitch_x"])/2
    for r in range(5):
        row_y=KEY_TOP_Y + r*mode["pitch_y"]
        row_net="ROW"+str(r)
        col_xs=[]
        for c in range(5):
            n=r*5+c
            x=first + c*mode["pitch_x"]
            swkey=f"KEY_{n:02d}"
            col_net="COL"+str(c)
            # Switch duplicate pads 1 are internally short; duplicate 2 also.
            footprint("Button_Switch_SMD","SW_Push_1P1T_NO_CK_KMR2",
                x,row_y,f"SW{n+1}","KMR221NG LFS",{"1":col_net,"2":swkey})
            # Both physical terminal pads sharing the same KiCad pad number
            # must be copper-connected: the PCB DRC does not assume that
            # the unpowered switch internally bridges duplicated pads.
            track([(x-2.05,row_y-.8),(x-2.05,row_y-2.1),
                   (x+2.05,row_y-2.1),(x+2.05,row_y-.8)],col_net,p.F_Cu)
            track([(x-2.05,row_y+.8),(x-2.05,row_y+2.1),
                   (x+2.05,row_y+2.1),(x+2.05,row_y+.8)],swkey,p.F_Cu)
            # Anode pin 2 to switch pin 2; cathode pin 1 to ROW.
            footprint("Diode_SMD","D_SOD-123",
                x,row_y+4.0,f"D{n+1}","1N4148W candidate",{"1":row_net,"2":swkey})
            # native pad positions on D_SOD-123: verify with DRC, not guessed.
            # Real native placement is user-editable, but footprint pins are
            # exact from library rather than a drawn contact symbol.
            d=next(item for item in pcb.GetFootprints() if item.GetReference()==f"D{n+1}")
            sw=next(item for item in pcb.GetFootprints() if item.GetReference()==f"SW{n+1}")
            ps=next(pad for pad in sw.Pads() if pad.GetNumber()=="2" and
                    p.ToMM(pad.GetPosition().x)>ox+x)
            pd=next(pad for pad in d.Pads() if pad.GetNumber()=="2")
            pdx,pdy=p.ToMM(pd.GetPosition().x)-ox,p.ToMM(pd.GetPosition().y)-oy
            psx,psy=p.ToMM(ps.GetPosition().x)-ox,p.ToMM(ps.GetPosition().y)-oy
            # Routed short interconnect, may be conditional on pad orientation.
            track([(psx,psy),(psx,psy+1.3),(pdx,pdy)],swkey,p.F_Cu)
            d1=next(pad for pad in d.Pads() if pad.GetNumber()=="1")
            dx,dy=p.ToMM(d1.GetPosition().x)-ox,p.ToMM(d1.GetPosition().y)-oy
            via_x=x-1.4
            via_y=row_y+6.5
            track([(dx,dy),(via_x,via_y)],row_net,p.F_Cu)
            via(via_x,via_y,row_net)
            col_xs.append(via_x)
        # row bus on B.Cu and row test pad near outer/edge at this Y.
        bus_y=row_y+6.5
        track([(col_xs[0],bus_y),(w-1.75,bus_y)],row_net,p.B_Cu)
        pad(w-1.75,bus_y,row_net,f"TPR{r}")
        via(w-1.75,bus_y,row_net)
    for c in range(5):
        x=first+c*mode["pitch_x"]
        # Col F.Cu starts above the first switch, then into left pin 1.
        column_x=x-3.0
        pad(column_x,1.6,"COL"+str(c),f"TPC{c}")
        track([(column_x,1.6),(column_x,KEY_TOP_Y+4*mode["pitch_y"]-.8)],
              "COL"+str(c),p.F_Cu)
        for r in range(5):
            y=KEY_TOP_Y+r*mode["pitch_y"]-.8
            track([(column_x,y),(x-2.05,y)],"COL"+str(c),p.F_Cu)
    fname=folder/f"thor_{modeid}_{side}_25keys.kicad_pcb"
    p.SaveBoard(str(fname),pcb)
    return str(fname.relative_to(HERE))


def scad_model(name:str,mode:dict,fit:dict):
    # Native solids for one keyboard case/PCB/keycap fit-check; original scan
    # is linked but not redistributed. Import optional proprietary/community
    # source with the controlling variable at runtime.
    w,h=mode["pcb_mm"]
    contents=[
        "// Thor QWERTY retrofit conceptual solids, mm",
        "// Source scan and exact inner housing *not* redistributed or certified.",
        "// Two attachments are displayed OVER original control areas.",
        "// This is not a cutting template or closed-lid clearance proof.",
        "include_scan = false;",
        "source_scan = \"/tmp/hs-thor-open-reference-20261109.stl\";",
        "if (include_scan) color([0.55,0.55,0.58,0.4]) import(source_scan, convexity=3);",
        "pcb_thickness = 1.0;  // exploratory, not KiCad stackup qualified",
        "switch_height = 1.9; // C&K KMR2 spec over PCB",
        "cap_extra_height = 1.2; // unverified cap geometry",
        "module_z = 28.0; // placeholder: NOT qualified from internal scan",
        "module_mounts_known = false;",
        "module_lid_clearance_known = false;",
    ]
    for side in ("left","right"):
        item=next(x for x in fit["sides"] if x["side"]==side)
        x0=item["pcb_rect_case_xy_mm"][0]
        y0=item["pcb_rect_case_xy_mm"][1]
        contents+= [
          f"// {side}: original controls should be removed, but mounts unproven",
          f"color([0.12,0.36,0.48,0.76]) translate([{x0},{y0},module_z]) cube([{w},{h},pcb_thickness]);",
        ]
        for key in item["keys"]:
            x,y,_=key["case_center_xyz_mm"]
            cw,ch=mode["keycap_mm"]
            contents.append(
                f"color([0.81,0.92,0.78]) translate([{x-cw/2:.3f},{y-ch/2:.3f},module_z+pcb_thickness+switch_height]) cube([{cw},{ch},cap_extra_height]); // {key['label']}"
            )
    path=OUTPUT/name/f"thor_{name}_concept.scad"
    path.write_text("\n".join(contents)+"\n")
    return str(path.relative_to(HERE))


def save_figure(fits:dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig,axes=plt.subplots(1,2,figsize=(13,7),sharex=True,sharey=True)
    for ax,(name,fit) in zip(axes,fits.items()):
        mode=MODES[name]
        ax.add_patch(Rectangle((-74.66,-74.4),152.41,73.4,
                    ec="#5b7990",fc="#e8eef2",lw=2,zorder=0))
        ax.add_patch(Rectangle((-35.25,-71),74.25,63,
                    ec="#3f8182",fc="#cee9e2",lw=2,zorder=1))
        ax.text(1.8,-41,"THOR\nLOWER\nSCREEN",ha="center",va="center",
                color="#386e66",weight="bold")
        for row in fit["sides"]:
            x0,y0,x1,y1=row["pcb_rect_case_xy_mm"]
            ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,
                   ec="#214f74",fc="#5796c4",alpha=.32,lw=1.5,zorder=2))
            for key in row["keys"]:
                x,y,_=key["case_center_xyz_mm"]
                kw,kh=mode["keycap_mm"]
                ax.add_patch(Rectangle((x-kw/2,y-kh/2),kw,kh,
                    ec="#142538",fc="#dfeef9",lw=.5,zorder=3))
                label=key["label"]
                if len(label)>3: label={"SHIFT":"Sh","CTRL":"Ct","ALT":"Alt",
                         "SPACE":"Sp","ENTER":"En","BSPC":"Bk","ESC":"Esc"}.get(label,label[:2])
                ax.text(x,y,label,ha="center",va="center",
                        fontsize=6.5 if mode["pitch_x"]<=7 else 7.5,zorder=4)
        ax.set_xlim(-91,94);ax.set_ylim(-79,8)
        ax.set_title(name+" — "+("IN-BODY PROPOSAL" if "flush" in name else "EXTERNAL WINGS"))
        ax.set_aspect("equal");ax.grid(alpha=.15)
        ax.set_xlabel("Thor scan X (mm)");ax.set_ylabel("Thor scan Y (mm)")
        ax.text(0,5.5,"HINGE SIDE (do not assume lid clearance)",ha="center",fontsize=8)
    fig.suptitle("HS Thor Split-QWERTY 2D fit: screen cutout and shell envelope are provisional")
    fig.tight_layout()
    path=OUTPUT/"thor_two_keyboard_options.png"
    fig.savefig(path,dpi=175)
    plt.close(fig)
    return str(path.relative_to(HERE))


def run(scan:Path)->dict:
    OUTPUT.mkdir(parents=True,exist_ok=True)
    scaninfo=read_scan(scan)
    fits={}
    for name,mode in MODES.items():
        fit=measure_fit(name,mode)
        assert fit["computed_2D_screen_overlap_pass"],fit["2D_critical"]
        fits[name]=fit
        folder=OUTPUT/name
        folder.mkdir(exist_ok=True)
        for side in ("left","right"):
            with (folder/f"{side}_25_key_locations.csv").open("w",newline="") as fd:
                writer=csv.DictWriter(fd,fieldnames=[
                    "id","label","row","col","pcb_x_mm","pcb_y_mm","scan_x_mm","scan_y_mm"],lineterminator="\n")
                writer.writeheader()
                for key in next(row["keys"] for row in fit["sides"] if row["side"]==side):
                    writer.writerow({k:key[k] for k in ("id","label","row","col")}|
                        {"pcb_x_mm":key["pcb_xy_mm"][0],"pcb_y_mm":key["pcb_xy_mm"][1],
                         "scan_x_mm":key["case_center_xyz_mm"][0],
                         "scan_y_mm":key["case_center_xyz_mm"][1]})
        scad_model(name,mode,fit)
        for side in ("left","right"):
            create_kicad(name,side,mode)
    illustration=save_figure(fits)
    report={"schema":"hs.thor_split_qwerty_external_scan_retrofit.v1",
       "source":scaninfo,"research_date":"2026-11-09",
       "assembly":"AYN Thor original 6in upper screen and 3.92in lower screen retained",
       "scope":"keyboard PCB geometry, exploratory switch matrices, external-geometry-only fit",
       "nominal_Thor_body_width_mm":150,
       "manual_scan_keepouts":FRONT,
       "switch_native_kicad_footprint":SWITCH_FOOTPRINT,
       "diode_native_kicad_footprint":DIODE_FOOTPRINT,
       "diode_candidate":DIODES,
       "firmware_candidate":"ZMK split BLE central/peripheral; custom shields unimplemented",
       "electrical_validation":"separately run kicad-cli pcb drc on generated boards",
       "keyboard_board_count":4,"full_keyboard_key_count":50,
       "original_controller_removal_tested":False,
       "actual_Thor_available_for_test":False,
       "tested_closed_lid":False,
       "tested_internal_cavities":False,
       "tested_touchscreen_shielding":False,
       "tested_Bluetooth_HID":False,
       "fabrication_approved":False,
       "variants":fits,"diagram":illustration}
    (OUTPUT/"fit_report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--scan",required=True,type=Path)
    a=parser.parse_args()
    result=run(a.scan)
    print(json.dumps({"scan_sha":result["source"]["sha256"],
                      "triangles":result["source"]["triangle_count"],
                      "fit":[{"id":k,"overlap":v["computed_2D_screen_overlap_pass"],
                             "side_extensions":[x["lateral_extension_outside_case_mm"]
                                 for x in v["sides"]]} for k,v in result["variants"].items()],
                      "all_electrical_and_fit_validated":False},indent=2))
