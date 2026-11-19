"""Build and check the P217 keyguard registration trial (Python standard library)."""

import itertools
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET


HERE = Path(__file__).resolve().parent
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)


def element(parent, name, **attrs):
    return ET.SubElement(parent, f"{{{SVG}}}{name}", {
        key: f"{value:.6f}" if isinstance(value, float) else str(value)
        for key, value in attrs.items()
    })


def canvas(width, height, units):
    return ET.Element(f"{{{SVG}}}svg", {
        "width": f"{width}{units}", "height": f"{height}{units}",
        "viewBox": f"0 0 {width} {height}",
    })


def save(root, name):
    ET.indent(root)
    ET.ElementTree(root).write(HERE / name, encoding="utf-8", xml_declaration=True)


def rectangle(parent, name, bounds, radius=0):
    x, y, w, h = bounds
    return element(parent, "rect", id=name, x=x, y=y, width=w, height=h, rx=radius)


def draw_board(spec, revision):
    w, h = spec["active_pixels"]
    board = canvas(w, h, "")
    board.set("width","100%")
    board.set("height","100%")
    element(board, "style").text = (
        "rect{fill:#e7f1ed;stroke:#244e45;stroke-width:3}"
        "g[data-selected] rect{fill:#f8cb68}text{font:60px sans-serif;"
        "fill:#18372e;text-anchor:middle;dominant-baseline:middle;pointer-events:none}"
    )
    layout = spec["layout"]
    columns = layout["columns_x_px"]
    change = spec["revision_2"]
    for row, y in enumerate(layout["rows_y_px"]):
        for col, x in enumerate(columns):
            cell = f"r{row+1}c{col+1}"
            label = layout["labels"][row * len(columns) + col]
            width, height = layout["target_size_px"]
            if revision == 2 and cell == change["cell"]:
                x += change["shift_x_px"]
                width += change["width_change_px"]
            group = element(board, "g", role="button", **{"aria-label": label})
            rectangle(group, "target-" + cell, (x, y, width, height))
            element(group, "text", x=x+width/2, y=y+height/2).text = label
    element(board, "script").text = """
document.documentElement.addEventListener('click', function (event) {
  const cell = event.target.closest('g[role="button"]');
  if (!cell) return;
  document.querySelector('[data-selected]')?.removeAttribute('data-selected');
  cell.setAttribute('data-selected', '');
});"""
    save(board, f"board-r{revision}.svg")


def read_rects(filename, prefix):
    root = ET.parse(HERE / filename).getroot()
    return {
        node.get("id")[len(prefix):]: tuple(float(node.get(key)) for key in ("x","y","width","height"))
        for node in root.findall(f".//{{{SVG}}}rect") if node.get("id","").startswith(prefix)
    }


def plate_geometry(spec):
    device_w, device_h, _ = spec["device_size_mm"]
    edge_x, edge_y = spec["edge_margin_mm"]
    width, height = device_w + 2*edge_x, device_h + 2*edge_y
    pitch = 25.4 / spec["pixel_density_ppi"]
    screen_w, screen_h = (n*pitch for n in spec["active_pixels"])
    screen = ((width-screen_w)/2, (height-screen_h)/2, screen_w, screen_h)
    return width, height, screen


def draw_plate(spec, kind, filename, targets=None):
    width, height, (sx, sy, sw, sh) = plate_geometry(spec)
    plate = canvas(width, height, "mm")
    cuts = element(plate, "g", fill="none", stroke="#000000", **{"stroke-width":"0.08"})
    rectangle(cuts, "outline", (0, 0, width, height), 3)
    for i, (x,y) in enumerate([(4.4,4.5),(width-4.4,4.5),(4.4,height-4.5),(width-4.4,height-14)]):
        element(cuts, "circle", id=f"mount-{i+1}", cx=x, cy=y, r=1.75)
    if kind == "locator":
        clear = spec["locator_clearance_per_side_mm"]
        dx, dy = spec["edge_margin_mm"]
        dw, dh, _ = spec["device_size_mm"]
        rectangle(cuts, "tablet-pocket", (dx-clear,dy-clear,dw+2*clear,dh+2*clear))
    if kind == "guard":
        reach = spec["swipe_nominal_mm"]
        rectangle(cuts, "access-top", (sx-3,sy-3,sw+6,reach+3), 2)
        rectangle(cuts, "access-bottom", (sx-3,sy+sh-reach,sw+6,reach+3), 2)
        for side, x in [("left",6.5), ("right",sx+sw-reach)]:
            rectangle(cuts,"access-"+side,(x,height/2-18,sx+reach-6.5,36),2)
        inset = spec["aperture_inset_mm"]
        pitch = 25.4/spec["pixel_density_ppi"]
        for cell, (x,y,w,h) in targets.items():
            rectangle(cuts, "window-"+cell,
                      (sx+x*pitch+inset,sy+y*pitch+inset,w*pitch-2*inset,h*pitch-2*inset),
                      spec["corner_radius_mm"])
    save(plate,filename)


def millimeter_targets(spec, filename, scale=1.0, rotated=False):
    width, height, (sx, sy, _, _) = plate_geometry(spec)
    pitch = 25.4 / spec["pixel_density_ppi"]
    targets = {}
    for cell, bounds in read_rects(filename,"target-").items():
        x,y,w,h = (v*pitch*scale for v in bounds)
        x,y = sx+x,sy+y
        if rotated:
            x,y = width-x-w,height-y-h
        targets[cell] = (x,y,w,h)
    return targets


def displacement_bound(spec):
    # Independent conservative envelope for every point on the circularly rotated plate.
    width, height, _ = plate_geometry(spec)
    max_radius = math.hypot(width,height)/2
    yaw = 2*max_radius*math.sin(math.radians(spec["yaw_deg"])/2)
    translation = spec["locator_clearance_per_side_mm"] + sum(spec["allowance_mm"].values())
    return yaw + translation


def assess_targets(windows, targets, allowance, dx=0.0, dy=0.0):
    if set(windows) != set(targets):
        raise ValueError("Window and target IDs differ")
    margins = {}
    for key, (x,y,w,h) in windows.items():
        tx,ty,tw,th = targets[key]
        margins[key] = min(x+dx-tx,y+dy-ty,tx+tw-x-dx-w,ty+th-y-dy-h)-allowance
    return {"outside": sorted(key for key,gap in margins.items() if gap < 0),
            "smallest_margin_mm": round(min(margins.values()),3)}


def rectangle_gap(a,b):
    x,y,w,h = a
    u,v,s,t = b
    return math.hypot(max(u-x-w,x-u-s,0), max(v-y-h,y-v-t,0))


def geometry_checks(spec, path):
    root = ET.parse(HERE/path).getroot()
    width,height,(sx,sy,sw,sh) = plate_geometry(spec)
    assert math.isclose(float(root.get("width").removesuffix("mm")),width)
    assert math.isclose(float(root.get("height").removesuffix("mm")),height)
    windows = read_rects(path,"window-")
    access = read_rects(path,"access-")
    assert len(windows) == 12 and len(access) == 4
    error = spec["allowance_mm"]["cut_per_edge"]
    cuts = list(windows.values())+list(access.values())
    # Rectangular envelopes enclose their rounded corners, yielding lower bounds.
    web = min(rectangle_gap(a,b) for a,b in itertools.combinations(cuts,2))-2*error
    edge_web = min(min(x,y,width-x-w,height-y-h) for x,y,w,h in cuts)-2*error
    clear_diameter = min(min(r[2:]) for r in windows.values())-2*error
    assert min(web,edge_web) >= spec["minimum_web_mm"]
    assert clear_diameter >= spec["minimum_aperture_mm"]
    assert all(2*spec["corner_radius_mm"]<=min(r[2:]) for r in windows.values())
    top,bottom,left,right = [access[k] for k in ("top","bottom","left","right")]
    half_w,half_h=width/2,height/2
    edge_segments=[
        (half_w,sy,top),(half_w,sy+sh,bottom),(sx,half_h,left),(sx+sw,half_h,right)
    ]
    for x,y,(ax,ay,aw,ah) in edge_segments:
        assert min(x-ax,y-ay,ax+aw-x,ay+ah-y)>displacement_bound(spec)
    swipe = min(top[1]+top[3]-sy,sy+sh-bottom[1],left[0]+left[2]-sx,sx+sw-right[0])-displacement_bound(spec)
    assert swipe>=spec["minimum_edge_swipe_mm"]
    return {"minimum_web_between_openings_mm":round(web,3),"minimum_outer_web_mm":round(edge_web,3),
            "minimum_central_clear_diameter_mm":round(clear_diameter,3),"edge_swipe_depth_mm":round(swipe,3)}


def check_mount(spec):
    width,height, _ = plate_geometry(spec)
    patterns=[]
    for file in ("backing.svg","locator.svg","guard-r1.svg","guard-r2.svg"):
        holes=ET.parse(HERE/file).findall(f".//{{{SVG}}}circle")
        assert all(float(n.get("r"))==1.75 for n in holes) and len(holes)==4
        patterns.append([(float(n.get("cx")),float(n.get("cy"))) for n in holes])
    assert all(p==patterns[0] for p in patterns)
    holes=patterns[0]
    error=spec["allowance_mm"]["cut_per_edge"]
    minimum_wall=min(min(x,y,width-x,height-y) for x,y in holes)-1.75-2*error
    assert minimum_wall>=2
    inner_cuts=list(read_rects("guard-r2.svg","window-").values())
    inner_cuts.extend(read_rects("guard-r2.svg","access-").values())
    inner_cuts.extend(read_rects("locator.svg","tablet-pocket").values())
    remaining=min(rectangle_gap((x,y,0,0),rect)-1.75-2*error for x,y in holes for rect in inner_cuts)
    assert remaining>=2
    flipped=max(min(math.dist((width-x,height-y),point) for point in holes) for x,y in holes)
    assert flipped>3.5+2*error
    return {"holes":len(holes),"minimum_mount_edge_wall_mm":round(minimum_wall,3),
            "minimum_mount_to_cut_wall_mm":round(remaining,3),
            "rotated_mount_mismatch_mm":round(flipped,3)}


def draw_inspection(spec):
    width,height,screen=plate_geometry(spec)
    drawing=canvas(width,height,"mm")
    dx,dy=spec["edge_margin_mm"]
    dw,dh,_=spec["device_size_mm"]
    rectangle(drawing,"base",(0,0,width,height),3).set("fill","#c9ced0")
    rectangle(drawing,"tablet",(dx,dy,dw,dh),8).set("fill","#384849")
    rectangle(drawing,"display",screen).set("fill","#e1e6e7")
    targets=millimeter_targets(spec,"board-r2.svg")
    for cell,bounds in targets.items():
        rectangle(drawing,"ui-"+cell,bounds).set("fill","#86bbaa")
    outlines=element(drawing,"g",fill="none",stroke="#ac3c20",**{"stroke-width":".45"})
    for node in ET.parse(HERE/"guard-r2.svg").findall(f".//{{{SVG}}}g/*"):
        outlines.append(node)
    for cell,(x,y,w,h) in targets.items():
        element(drawing,"text",x=x+w/2,y=y+h/2,**{"text-anchor":"middle","font-size":3.5,
                "font-family":"sans-serif","fill":"#15282a"}).text=cell
    save(drawing,"inspection-r2.svg")


def main():
    spec=json.loads((HERE/"design.json").read_text())
    revisions={}
    for rev in (1,2):
        draw_board(spec,rev)
        targets=read_rects(f"board-r{rev}.svg","target-")
        draw_plate(spec,"guard",f"guard-r{rev}.svg",targets)
        windows=read_rects(f"guard-r{rev}.svg","window-")
        true_targets=millimeter_targets(spec,f"board-r{rev}.svg")
        revision=assess_targets(windows,true_targets,displacement_bound(spec))
        assert not revision["outside"]
        revisions[f"r{rev}"]=dict(**revision,**geometry_checks(spec,f"guard-r{rev}.svg"))
    draw_plate(spec,"backing","backing.svg")
    draw_plate(spec,"locator","locator.svg")
    v1,v2=(read_rects(f"guard-r{r}.svg","window-") for r in (1,2))
    changes=[key for key in v1 if v1[key]!=v2[key]]
    assert changes==[spec["revision_2"]["cell"]]
    # Exact nominal displacement for negative controls, without double-counting the tolerance envelope.
    controls={
        "old_overlay_on_revised_board":assess_targets(v1,millimeter_targets(spec,"board-r2.svg"),0),
        "overlay_shifted_5mm":assess_targets(v1,millimeter_targets(spec,"board-r1.svg"),0,dx=5),
        "screen_at_90_percent_top_left":assess_targets(v1,millimeter_targets(spec,"board-r1.svg",scale=.9),0),
        "screen_rotated_180_degrees":assess_targets(v1,millimeter_targets(spec,"board-r1.svg",rotated=True),0),
    }
    assert controls["old_overlay_on_revised_board"]["outside"]==changes
    assert len(controls["overlay_shifted_5mm"]["outside"])==12
    assert len(controls["screen_rotated_180_degrees"]["outside"])==12
    assert controls["screen_at_90_percent_top_left"]["outside"]
    left=read_rects("guard-r1.svg","access-")["left"]
    trial_reach=8.5
    wider_slot=(*left[:2], left[2]+trial_reach-spec["swipe_nominal_mm"],left[3])
    trial_web=rectangle_gap(wider_slot,v1["r2c1"])-2*spec["allowance_mm"]["cut_per_edge"]
    assert trial_web<spec["minimum_web_mm"]
    results={"product":"P217","units":"mm","scope":"synthetic board on nominal display, digital verification",
             "screen_size_mm":[round(v,3) for v in plate_geometry(spec)[2][2:]],
             "combined_edge_displacement_bound_mm":round(displacement_bound(spec),3),
             "revisions":revisions,"changed_openings":changes,"mount":check_mount(spec),
             "rejected_side_slot":{"original_reach_mm":trial_reach,"worst_web_mm":round(trial_web,3),
                                   "required_web_mm":spec["minimum_web_mm"]},
             "negative_controls":controls}
    draw_inspection(spec)
    (HERE/"results.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results,indent=2))


if __name__=="__main__":
    main()
