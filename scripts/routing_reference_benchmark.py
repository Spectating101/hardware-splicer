"""Strip a designer-routed 2-layer KiCad board to its placement, route it with Copper, and compare the two layouts.

    python3 scripts/routing_reference_benchmark.py <HS src dir> board.kicad_pcb OUT_DIR GND_NET

Tracks, arcs, vias and copper zones are removed (keepouts stay), so Copper starts from the designer's own placement.
The designer's board and Copper's are both checked by KiCad 10's DRC; errors that come from placement (courtyards,
edge clearance) appear on both and are not the router's. Needs the HARDWARE_SPLICER_COPPER_* settings and
HARDWARE_SPLICER_KICAD_CLI pointing at a KiCad 10 kicad-cli (scripts/kicad10-cli).
"""
import json, math, re, subprocess, sys, os
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from hardware_splicer import copper_route

def top_children(text):
    """(start, end, head) of each top-level child of (kicad_pcb ...), respecting strings."""
    i, depth, start, out, n = 0, 0, None, [], len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\": i += 2; continue
            if c == '"': in_str = False
        elif c == '"': in_str = True
        elif c == "(":
            depth += 1
            if depth == 2: start = i
        elif c == ")":
            if depth == 2 and start is not None:
                head = re.match(r"\((\w+)", text[start:start + 40]).group(1)
                out.append((start, i + 1, head))
                start = None
            depth -= 1
        i += 1
    return out

def metrics(text):
    segs = re.findall(r"\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)", text)
    length = sum(math.dist((float(a), float(b)), (float(c), float(d))) for a, b, c, d in segs)
    return {"segments": len(segs), "track_length_mm": round(length, 1), "vias": len(re.findall(r"^\s*\(via\b", text, re.M))}

def strip(text):
    keep, last = [], 0
    for s, e, head in top_children(text):
        body = text[s:e]
        drop = head in ("segment", "arc", "via") or (head == "zone" and "(keepout" not in body)
        if drop:
            keep.append(text[last:s]); last = e
    keep.append(text[last:])
    return "".join(keep)

def drc(pcb, out):
    rep = out / "drc_human.json"
    subprocess.run([os.environ["HARDWARE_SPLICER_KICAD_CLI"], "pcb", "drc", "--format", "json", "--severity-error",
                    "--output", str(rep), str(pcb)], capture_output=True, text=True, timeout=900, cwd=str(pcb.parent))
    if not rep.exists(): return None
    d = json.loads(rep.read_text())
    return {"errors": len([v for v in d.get("violations", []) if v.get("severity") == "error"]), "unconnected": len(d.get("unconnected_items", []))}

if __name__ == "__main__":
    src, out, gnd = Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(), sys.argv[4]
    out.mkdir(parents=True, exist_ok=True)
    text = src.read_text(errors="replace")
    human = metrics(text)
    human["drc"] = drc(src, out)
    placed = out / "placed.kicad_pcb"
    placed.write_text(strip(text))
    pro = src.with_suffix(".kicad_pro")
    if pro.exists(): (out / "placed.kicad_pro").write_text(pro.read_text())
    result = {"board": src.name, "human": human, "stripped_metrics": metrics(placed.read_text())}
    try:
        r = copper_route.route_with_copper(placed, out / "copper", pour_net=gnd, timeout_s=1800)
        routed = Path(r["routed_board"]).read_text(errors="replace") if r.get("routed_board") else ""
        result["copper"] = {k: v for k, v in r.items() if k not in ("rounds", "elegance")}
        result["copper_metrics"] = metrics(routed) if routed else None
    except Exception as exc:
        result["copper"] = {"error": f"{type(exc).__name__}: {exc}"[:600]}
    (out / "result.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps(result, default=str)[:1500])
