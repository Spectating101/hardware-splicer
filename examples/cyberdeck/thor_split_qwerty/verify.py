"""HS Thor split QWERTY: independent native PCB DRC and release blockers.

Checks ACTUAL KiCad board footprints, 25 per-key diode intermediates, routing,
10 accessible row/column breakout pads, native KiCad DRC zero errors/unrouted,
and nominal scan-derived rectangular space. No physical Thor is connected.
"""
from __future__ import annotations

import argparse,hashlib,json,re,shutil,subprocess,tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCE=HERE/"generated/fit_report.json"
SCHEMA="hs.thor_split_qwerty_verification.v1"
PLANS=("flush_7mm","detachable_9mm")
SIDES=("left","right")

def sha256(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def require(pred,explain):
    if not pred:raise ValueError("Thor split-QWERTY verification failed: "+explain)

def inspect_board(board:Path,variant:dict,side:str)->dict:
    import pcbnew as p
    b=p.LoadBoard(str(board))
    require(b is not None, "KiCad 9 cannot open "+board.name)
    footprints={fp.GetReference():fp for fp in b.GetFootprints()}
    require(len(footprints)==60,"expected 25 switches +25 diodes +10 breakout pads")
    for r in range(5):
        for c in range(5):
            n=r*5+c
            sw=footprints.get(f"SW{n+1}")
            d=footprints.get(f"D{n+1}")
            require(sw is not None and d is not None, "missing switch or diode for key")
            require(len(list(sw.Pads()))==4,"KMR2 4-terminal footprint changed")
            require(len(list(d.Pads()))==2,"SOD123 diode contact count changed")
            # Validate *every* duplicated KMR2 contact independently. Dict
            # reduction silently masked one sabotaged pad during mutation test.
            sw_pads=list(sw.Pads())
            require(sum(pad.GetNumber()=="1" for pad in sw_pads)==2
                    and sum(pad.GetNumber()=="2" for pad in sw_pads)==2,
                    "KMR2 duplicate contact structure changed")
            require(all(pad.GetNetname()==f"COL{c}" for pad in sw_pads
                        if pad.GetNumber()=="1") and
                    all(pad.GetNetname()==f"KEY_{n:02d}" for pad in sw_pads
                        if pad.GetNumber()=="2"),
                    "column or intermediate key net incorrect")
            dn={pad.GetNumber():pad.GetNetname() for pad in d.Pads()}
            require(dn=={"1":f"ROW{r}","2":f"KEY_{n:02d}"},
                    "diode polarity/row/intermediate net incorrect")
    for c in range(5):
        tp=footprints.get(f"TPC{c}")
        require(tp is not None and len(list(tp.Pads()))==1
                and next(iter(tp.Pads())).GetNetname()==f"COL{c}",
                "column solder-testpad missing or miswired")
    for r in range(5):
        tp=footprints.get(f"TPR{r}")
        require(tp is not None and len(list(tp.Pads()))==1
                and next(iter(tp.Pads())).GetNetname()==f"ROW{r}",
                "row solder-testpad missing or miswired")
    shape=b.GetBoardEdgesBoundingBox()
    dims=[round(p.ToMM(shape.GetWidth())-.05,1),
          round(p.ToMM(shape.GetHeight())-.05,1)]
    require(dims==variant["pcb_mm"],f"PCB edge differs from declared key geometry: {dims}")
    tracks=list(b.GetTracks())
    vias=[t for t in tracks if isinstance(t,p.PCB_VIA)]
    require(len(vias)>=30 and len(tracks)>=280,
            "matrix copper routing or via count unexpectedly incomplete")
    # The BOM is exactly 25 switches +25 SOD123 diodes+10 testpads.
    # No on-board BLE MCU/battery, charger, mating connector or mounts exist.
    return {
       "source":str(board.relative_to(HERE) if board.is_relative_to(HERE) else board.name),
       "sha256":sha256(board),
       "board_size_mm":dims,
       "switches":25,"diodes":25,"breakout_solderpads":10,
       "smd_switch_footprint":"SW_Push_1P1T_NO_CK_KMR2",
       "diode_footprint":"D_SOD-123",
       "nets_col":5,"nets_row":5,"nets_per_key":25,
       "copper_segments_and_vias":len(tracks),"vias":len(vias),
       "route_source":"KiCad9 SWIG pad-to-net and copper trace objects",
       "external_mcu_and_battery_present":False,
       "schematic_ERC_or_parity_proven":False,
    }


def native_drc(board:Path)->dict:
    executable=shutil.which("kicad-cli")
    require(executable is not None,"native kicad-cli required, no fixture result accepted")
    with tempfile.TemporaryDirectory(prefix="hs-thor-drc-") as tmp:
        path=Path(tmp)/"checks.drc.txt"
        command=[executable,"pcb","drc","-o",str(path),str(board)]
        result=subprocess.run(command,timeout=60,capture_output=True,text=True)
        require(result.returncode==0,
                "KiCad CLI DRC exited failure: "+(result.stderr+result.stdout)[-700:])
        report=path.read_text()
    for p in ("** Found 0 DRC violations **","** Found 0 unconnected pads **",
              "** Found 0 Footprint errors **"):
        require(p in report,"KiCad CLI did not independently clear "+p)
    return {"native_kicad_cli_drc":"pass","violation_count":0,
            "unconnected_count":0,"footprint_error_count":0}


def evaluate_fit(doc:dict)->dict:
    require(doc.get("schema")=="hs.thor_split_qwerty_external_scan_retrofit.v1",
            "invalid input manifest")
    scan=doc["source"]
    require(scan["sha256"]==
            "42800c73d5e0523961f243e482732fcd2ba119c6e3aeae55659d7adee32e8402"
            and scan["triangle_count"]==1012267,"unverified community scan")
    require(scan["mesh_exterior_not_internal_cavity"] is True,
            "never claim actual internal Thor measurements")
    require(doc["full_keyboard_key_count"]==50
            and doc["original_controller_removal_tested"] is False
            and doc["tested_closed_lid"] is False
            and doc["tested_internal_cavities"] is False
            and doc["fabrication_approved"] is False,
            "geometry/mounting proof is not present")
    results={}
    for name in PLANS:
        candidate=doc["variants"][name]
        require(candidate["total_keys"]==50 and len(candidate["sides"])==2,
                "both keypads required")
        require(candidate["computed_2D_screen_overlap_pass"] is True,
                "keyboard overlaps lower touch panel")
        require(candidate["internal_mounting_clearance_verified"] is False
                and candidate["closed_lid_clearance_verified"] is False,
                "unearned physical geometry clearance")
        for side in candidate["sides"]:
            require(len(side["keys"])==25,"missing keys")
            require(len(set(k["id"] for k in side["keys"]))==25,"duplicate key identity")
        gap=candidate["min_screen_edge_gap_mm"]
        if name=="flush_7mm":
            require(gap<2 and not candidate["provisional_2mm_clearance_gate"],
                    "flush layout must disclose sub-2mm screen margin")
            require(all(v["lateral_extension_outside_case_mm"]==0 for v in candidate["sides"]),
                    "flush board must not silently exceed factory outline")
        else:
            require(candidate["provisional_2mm_clearance_gate"] is True,
                    "detachable variant must meet declared 2D margin")
            require(all(9<=v["lateral_extension_outside_case_mm"]<=11 for v in candidate["sides"]),
                    "wing must disclose 10mm protrusion beyond original casing")
        results[name]={"nominal_2D_no_screen_overlap":True,
            "nominal_2mm_buffer_in_outline":candidate["provisional_2mm_clearance_gate"],
            "minimum_screen_gap_mm":gap,
            "minimum_bottom_gap_mm":candidate["min_bottom_keepout_gap_mm"],
            "minimum_hinge_gap_mm":candidate["min_hinge_keepout_gap_mm"],
            "closed_lid_fit_proven":False,"real_internal_geometry_proven":False,
            "confirmed_unmodified_controller_clearance":False}
    return results


def run(out:Path):
    doc=json.loads(SOURCE.read_text())
    fits=evaluate_fit(doc)
    rows=[]
    for name in PLANS:
        variant=doc["variants"][name]
        # Case width data belong to the 2D proposed design, NOT measured
        # keyboard-controller pockets.
        mode={"flush_7mm":(36.0,57.0),"detachable_9mm":(47.0,58.0)}[name]
        for side in SIDES:
            b=HERE/f"generated/{name}/thor_{name}_{side}_25keys.kicad_pcb"
            inspected=inspect_board(b,{"pcb_mm":list(mode)},side)
            result=native_drc(b)
            rows.append({"variant":name,"side":side,**inspected,**result})
    verdict={
      "schema":SCHEMA,
      "date":"2026-11-09",
      "status":"FOUR_NATIVE_ROUTED_PCBS_DRC_PASS_PHYSICAL_RETROFIT_BLOCKED",
      "community_STL_sha256":doc["source"]["sha256"],
      "scan_triangles":doc["source"]["triangle_count"],
      "scan_use":"outer geometry fit proxy, not internal shell scan",
      "fit":fits,
      "board_results":rows,
      "native_drc_all_four":all(r["native_kicad_cli_drc"]=="pass" for r in rows),
      "sum_footprints":sum(r["switches"]+r["diodes"]+r["breakout_solderpads"] for r in rows),
      "sum_switches_across_two_profiles":100,
      "each_complete_option_keys":50,
      "suggested_first_prototype":"detachable_9mm",
      "external_BLE_controller_designed":False,
      "ZMK_firmware_compiled":False,
      "switch_keycap_actuation_tested":False,
      "schematic_nets_parity_tested":False,
      "physical_Thor_assembly_tested":False,
      "closed_lid_no_collision_proven":False,
      "harness_and_strain_relief_tested":False,
      "battery_and_protection_tested":False,
      "original_Thor_motherboard_modified":False,
      "fabrication_or_order_authorized":False,
      "human_typing_trial_tested":False,
      "next_gate":"Print 1:1 paper template or dummy keyplate; check thumb reach on real unit or same-size mock, then measure unmodified Thor internal cavity and lid before any permanent cutting",
      "provenance": {"input_report_sha256":sha256(SOURCE)},
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(verdict,indent=2)+"\n")
    return verdict

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=HERE/"evidence/verification.json")
    a=p.parse_args()
    v=run(a.out)
    print(json.dumps({"status":v["status"],
        "native_zero_drc":v["native_drc_all_four"],
        "boards":len(v["board_results"]),
        "recommended_first":v["suggested_first_prototype"],
        "physical_fabrication_authorized":v["fabrication_or_order_authorized"]},indent=2))

if __name__=="__main__":main()
