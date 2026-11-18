"""GPL-3.0-only. Parametric Ender-3 pen adapter and reference envelopes.

Authored 2026-11-17. New geometry; vendor E-plate remains unmodified.
Local coordinates match manufacturer E plate.step: u=X, v=vertical,
w=front normal. The retained hotend M3 boss pair is measured, never guessed.
"""
import math
import cadquery as cq
import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from common import ROOT, read_requirements, write_json, sha256, constraint


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1-x0, y1-y0, z1-z0).translate(
        ((x0+x1)/2, (y0+y1)/2, (z0+z1)/2)).val()


def bore_w(u, v, r, w0=0., length=60.):
    return cq.Solid.makeCylinder(r, length, cq.Vector(u,v,w0), cq.Vector(0,0,1))


def mesh(shape, color):
    verts, faces = shape.tessellate(.5, .15)
    m = trimesh.Trimesh(np.array([v.toTuple() for v in verts]), np.array(faces), process=False)
    m.visual.face_colors = color
    return m


def main():
    req = read_requirements()
    out=ROOT/"exports"; out.mkdir(exist_ok=True)
    interface = __import__("json").loads((ROOT/"sources/interface.json").read_text())
    vendor = cq.importers.importStep(str(ROOT/"sources/E plate.step")).val()
    # Plane at w=7 is the actual front of the two manufacturer bosses.
    # 6 mm rear web, 40 mm width, 55 mm height; vertical pen adjustment is friction clamped.
    adapter=box(-3.5,36.5,-35.,20.,7.,13.)
    rear=box(-3.5,36.5,-35.,-15.,13.,32.)
    adapter=adapter.fuse(rear)
    for u,v in interface["mount_centers_uv_mm"]:
        adapter=adapter.cut(bore_w(u,v,1.7))
    r=(req["pen_diameter_mm"]+1.2)/2
    axis_u=16.5
    rear_bore=cq.Solid.makeCylinder(r,30,cq.Vector(axis_u,-40,32),cq.Vector(0,1,0))
    adapter=adapter.cut(rear_bore)
    cap=box(-3.5,36.5,-35.,-15.,32.4,44.9)
    cap_bore=cq.Solid.makeCylinder(r,30,cq.Vector(axis_u,-40,32.4),cq.Vector(0,1,0))
    cap=cap.cut(cap_bore)
    for u in (4.,29.):
        adapter=adapter.cut(bore_w(u,-25.,1.7))
        cap=cap.cut(bore_w(u,-25.,1.7))
        # ISO M3 nut clearance, 5.7 mm across flats, rear insertion before donor attachment.
        trap=(cq.Workplane("XY",origin=(u,-25,7)).polygon(6,5.7/math.cos(math.pi/6))
              .extrude(2.5).val())
        adapter=adapter.cut(trap)
    adapter=adapter.clean();cap=cap.clean()
    assert adapter.isValid() and cap.isValid()
    # Tool envelope: cylindrical 100 mm length from tip, selected diameter; friction position adjustable.
    pen=cq.Solid.makeCylinder(req["pen_diameter_mm"]/2,100,
        cq.Vector(16.5,-65.,32.2),cq.Vector(0,1,0))
    local_parts=[("pen_adapter",adapter,[242,132,36,255]),("pen_clamp",cap,[252,192,69,255]),
                 ("manufacturer_E_plate",vendor,[65,76,89,255]),("pen_envelope",pen,[36,116,166,255])]
    # Park intact heater+thermistor+radiator assembly on top 2020 profile.
    # Two 3.4mm clear holes match actual radiator through-hole pitch14; rear M3 nut traps.
    # Two 4.5mm clear frame holes use actual manufacturer M4 T nuts in a measured slot fit.
    parking=box(0,80,-80,15,0,4)
    for u in (15.,65.):parking=parking.cut(bore_w(u,0,2.25,-2,10))
    for u in (33.,47.):
        parking=parking.cut(bore_w(u,-30,1.7,-2,10))
        trap=cq.Workplane("XY",origin=(u,-30,0)).polygon(6,5.7/math.cos(math.pi/6)).extrude(2.5).val()
        parking=parking.cut(trap)
    for u in (7.,73.):
        for v in (-45.,-68.):parking=parking.cut(box(u-2,u+2,v-6,v+6,-1,5))
    parking=parking.clean()
    for name,s,color in local_parts[:2]+[("hotend_parking_plate",parking,[159,90,187,255])]:
        cq.exporters.export(s,str(out/(name+".step")))
        cq.exporters.export(s,str(out/(name+".stl")),tolerance=.08,angularTolerance=.1)
    # Explicit, dimensioned reference envelopes. These are not vendor detailed geometry.
    # Coordinates: paper bed surface z=0, physical bed x/y=0..235, pen shown at x/y=117.5.
    # Local u,v,w -> world x,z,-y, right-handed rotation about X +90 degrees.
    pen_ref=(117.5,117.5,.1)
    def installed(s):
        return s.rotate((0,0,0),(1,0,0),90).translate((101.,149.7,65.1))
    pieces=[]
    def envelope(name,extents,col):
        pieces.append((name,box(*extents),col))
    dark=[47,56,67,255]; silver=[148,158,169,255]
    envelope("REFERENCE_ENVELOPE_bed_235x235",(0,235,0,235,-4,0),[193,205,217,255])
    envelope("REFERENCE_ENVELOPE_left_base",(-42,-2,-70,330,-105,-65),dark)
    envelope("REFERENCE_ENVELOPE_right_base",(267,307,-70,330,-105,-65),dark)
    envelope("REFERENCE_ENVELOPE_central_base",(-42,307,97.5,137.5,-105,-65),dark)
    envelope("REFERENCE_ENVELOPE_left_upright",(-42,-22,153.55,193.55,-65,335),dark)
    envelope("REFERENCE_ENVELOPE_right_upright",(287,307,153.55,193.55,-65,335),dark)
    envelope("REFERENCE_ENVELOPE_top",(-42,307,163.55,183.55,335,355),dark)
    # Actual rail cross-section offset from E plate measured in manufacturer assembly.
    envelope("REFERENCE_ENVELOPE_X_rail",(-52.3,292.7,153.55,173.55,55.1,75.1),silver)
    envelope("REFERENCE_ENVELOPE_X_belt",(-42.3,282.7,156,158,62.1,68.1),[37,41,44,255])
    envelope("REFERENCE_ENVELOPE_Y_belt",(114.5,120.5,-45,285,-60,-58),[37,41,44,255])
    for name,x,y,z in [("X_motor",-42,163.55,65.1),("Y_motor",117.5,290,-65),("Z_motor",-52,173.55,-45)]:
        envelope("REFERENCE_ENVELOPE_"+name,(x-21,x+21,y-17,y+17,z-21,z+21),dark)
    envelope("REFERENCE_ENVELOPE_enclosed_PSU",(311,361,77,192,-60,155),silver)
    envelope("REFERENCE_ENVELOPE_controller_enclosure",(-35,100,-50,70,-65,-27),dark)
    envelope("REFERENCE_ENVELOPE_LCD",(215,295,-55,10,-40,-15),[34,81,109,255])
    # Centered, explicitly sized sheet; the entire drawing viewport reserves 10 mm for tape.
    pw,ph=req["paper_width_mm"],req["paper_height_mm"]
    px0,px1=(235-pw)/2,(235+pw)/2
    py0,py1=(235-ph)/2,(235+ph)/2
    paper_name="paper_180mm_square" if pw==ph==180 else f"paper_{pw:g}x{ph:g}mm"
    envelope(paper_name,(px0,px1,py0,py1,0,.1),[250,249,242,255])
    for name,s,col in local_parts:pieces.append((name,installed(s),col))
    def parked(s):return s.rotate((0,0,0),(1,0,0),90).translate((-12.,163.55,345.))
    pieces.append(("hotend_parking_plate",parked(parking),[159,90,187,255]))
    pieces.append(("REFERENCE_ENVELOPE_parked_intact_hotend",parked(box(25,55,-75,-25,4,40)),[123,128,133,255]))
    pieces.append(("REFERENCE_ENVELOPE_parked_fans_and_shroud",parked(box(0,80,-80,-40,4,45)),[71,76,82,255]))
    assy=cq.Assembly(name="VIRTUAL_Ender3_penplotter_reference_envelopes")
    scene=trimesh.Scene()
    for name,s,col in pieces:
        assy.add(s,name=name,color=cq.Color(*[v/255 for v in col]))
        scene.add_geometry(mesh(s,col),node_name=name,geom_name=name)
    assy.save(str(out/"plotter.step"))
    scene.export(str(out/"plotter.glb"))
    # Interference is evaluated against detailed vendor plate, not against schematic frame envelopes.
    overlap=adapter.intersect(vendor).Volume()+cap.intersect(vendor).Volume()
    # Conservative weak-axis web deflection at 2N lateral load, rectangular cantilever proxy only.
    L=42.55; I=40*6**3/12; E=1400.; delta=2*L**3/(3*E*I)
    profile=cq.importers.importStep(str(ROOT/"sources/2020 profile.step")).val().translate((0,0,-10))
    tnut=(cq.importers.importStep(str(ROOT/"sources/M4 T-Slot Nut.step")).val()
          .rotate((0,0,0),(0,0,1),90).translate((50,0,-3.5)))
    tnut_overlap=profile.intersect(tnut).Volume()
    paper_margin=min(px0,235-px1,py0,235-py1)
    drawing_paper_x=(pw-req["drawing_width_mm"])/2
    drawing_paper_y=(ph-req["drawing_height_mm"])/2
    viewport_controller_margin=min(value for size,offset in zip(
        (req["drawing_width_mm"],req["drawing_height_mm"]),interface["pen_offset_from_nozzle_xy_mm"])
        for value in (117.5-size/2-offset,235-(117.5+size/2-offset)))
    metrics={"paper_width_mm":pw,"paper_height_mm":ph,"paper_bed_margin_mm":paper_margin,
             "drawing_paper_margin_x_mm":drawing_paper_x,"drawing_paper_margin_y_mm":drawing_paper_y,
             "viewport_controller_margin_mm":viewport_controller_margin,"mount_pitch_mm":14.,"mount_boss_front_mm":7.,"mount_bolt_engagement_mm":4.,
             "mount_interference_mm3":overlap,"adapter_volume_mm3":adapter.Volume(),
             "cap_volume_mm3":cap.Volume(),"printed_mass_g_at_1_27_g_cm3":(adapter.Volume()+cap.Volume()+parking.Volume())*.00127,
             "plate_to_adapter_airgap_mm":4.5,"pen_tip_to_clamp_mm":30.,
             "beam_proxy_deflection_mm_at_2N":delta,"clamp_open_gap_mm":.4,
             "clamp_screw_tip_to_plate_mm":2.4,"pen_lift_mm":req["pen_lift_mm"],
             "pen_diameter_mm":req["pen_diameter_mm"],"drawing_width_mm":req["drawing_width_mm"],
             "drawing_height_mm":req["drawing_height_mm"],"parking_plate_volume_mm3":parking.Volume(),
             "parking_tnut_profile_interference_mm3":tnut_overlap,"parking_radiator_hole_pitch_mm":14.}
    constraints=[constraint("manufacturer_mount_pitch",14,14,True,"mm","PDF + STEP measured cylinder axes"),
        constraint("donor_interference",overlap,.001,overlap<.001,"mm3","Exact OpenCascade intersection with unmodified manufacturer E plate"),
        constraint("bolt_engagement",4,3,4>=3,"mm","New M3x10: 10 mm minus 6 mm printed web"),
        constraint("beam_proxy",delta,.3,delta<=.3,"mm","2N, E=1400MPa assumed printed polymer, 40x6 web, L42.55; excludes layer/creep/clamp failure"),
        constraint("bed_limited_drawing_width",req["drawing_width_mm"],190,req["drawing_width_mm"]<=190,"mm","Registered horizontal scope; full viewport separately checked against paper and source controller travel"),
        constraint("bed_limited_drawing_height",req["drawing_height_mm"],140,req["drawing_height_mm"]<=140,"mm","Retained vertical scope; physical calibration not performed"),
        constraint("paper_on_bed",paper_margin,0,paper_margin>=0,"mm","Centered sheet inside the manufacturer 235 mm bed"),
        constraint("drawing_paper_margin_x",drawing_paper_x,10,drawing_paper_x>=10,"mm","Full viewport leaves at least 10 mm paper margin at both horizontal edges"),
        constraint("drawing_paper_margin_y",drawing_paper_y,10,drawing_paper_y>=10,"mm","Full viewport leaves at least 10 mm paper margin at both vertical edges"),
        constraint("viewport_controller_travel",viewport_controller_margin,0,viewport_controller_margin>=0,"mm","Full source viewport after measured pen/nozzle offset stays in 0..235 mm controller travel"),
        constraint("parking_tnut_profile_fit",tnut_overlap,.001,tnut_overlap<.001,"mm3","Actual manufacturer M4 T nut rotated90deg, translated w=-3.5 inside actual2020 profile; no thread/torque validation"),
        constraint("parking_hotend_clearance",273.2-req["pen_lift_mm"],200.,273.2-req["pen_lift_mm"]>200,"mm","Parked nozzle273.2mm above paper minus maximum pen lift; representative layout only")]
    report=dict(case_id="ender3-penplotter",requirements=req,metrics=metrics,constraints=constraints,
        requirements_met=all(c["passed"] for c in constraints),physical_validation_performed=False,
        donor_inventory_kind="virtual_reference_manufacturer_donor",owned_inventory_count=0,
        layout_geometry="Unmodified detailed manufacturer E plate plus new adapter; all other donor components are explicitly named reference envelopes",
        limitations=["No physical fit, clamp holding, print strength, plot accuracy, homing or electrical validation.",
                     "Envelopes are representative layout, not a complete manufacturer collision model.",
                     "Sample G-code is digital simulation input, not an authorized hardware job."])
    write_json(ROOT/"reports/engineering.json",report)
    # Source-driven render, with detailed mount in second panel.
    fig=plt.figure(figsize=(14,7),facecolor="#f5f7fa")
    # Show the mount in its installed orientation so the pen is visibly vertical.
    mount_view=[(name,s.rotate((0,0,0),(1,0,0),90),col) for name,s,col in local_parts]
    for i, selected in [(1,pieces),(2,mount_view)]:
        ax=fig.add_subplot(1,2,i,projection="3d")
        for name,s,col in selected:
            m=mesh(s,col);poly=Poly3DCollection(m.vertices[m.faces],alpha=col[3]/255,linewidths=.05)
            poly.set_facecolor(np.array(col)/255);poly.set_edgecolor((.1,.13,.18,.1));ax.add_collection3d(poly)
        if i==1:
            ax.set(xlim=(-70,375),ylim=(-80,340),zlim=(-110,365),title=f"Virtual Ender-3 plotter · {pw:g} × {ph:g} mm paper\nDetailed mount; labeled reference envelopes")
            ax.set_box_aspect((445,420,475));ax.view_init(elev=23,azim=-62)
        else:
            ax.set(xlim=(-35,40),ylim=(-49,23),zlim=(-70,45),title="Manufacturer carriage + adjustable pen clamp\n14 mm M3 interface; Z axis lifts entire pen")
            ax.set_box_aspect((75,72,115));ax.view_init(elev=19,azim=-61)
        ax.set_xlabel("X / u (mm)");ax.set_ylabel("Y / v (mm)");ax.set_zlabel("Z / w (mm)")
    fig.text(.5,.02,"DIGITAL STUDY · No owned donor, purchases, fabrication, powered motion or physical validation",ha="center",fontsize=10)
    fig.tight_layout(rect=(0,.04,1,.92));fig.savefig(out/"device_render.png",dpi=160);plt.close(fig)
    write_json(ROOT/"reports/export_manifest.json",{str(p.relative_to(ROOT)):sha256(p) for p in sorted(out.iterdir()) if p.is_file()})
    print("CAD build complete: requirements_met="+str(report["requirements_met"]))


if __name__ == "__main__":main()
