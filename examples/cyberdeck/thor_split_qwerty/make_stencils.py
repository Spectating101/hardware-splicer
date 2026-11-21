"""Generate printable 1:1 Thor split-QWERTY paper fit templates (A4 SVG).

Paper templates are solely for ergonomics and positional measurements.
Do not drill/cut device from these unqualified outer-scan fits.
"""
from __future__ import annotations
import json,html
from pathlib import Path

HERE=Path(__file__).resolve().parent
SRC=HERE/"generated/fit_report.json"


def template(name:str,variant:dict)->str:
    # A4 portrait 210x297 mm. Thor lower geometry origin centered at (105,60).
    ox,oy=105.0,52.0
    x0,x1=-74.66,77.75
    y0,y1=-74.4,-1.0
    def X(v):return round(ox+v,3)
    def Y(v):return round(oy-v,3)
    res=[
       '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
       '<rect width="210" height="297" fill="white"/>',
       f'<text x="9" y="10" font-family="sans-serif" font-size="5" font-weight="bold">HS THOR / {name.upper()} — PRINT AT 100%</text>',
       '<text x="9" y="17" font-family="sans-serif" font-size="3">EXTERIOR SCAN PROJECTION ONLY. NOT A CUTTING OR DRILL TEMPLATE.</text>',
       f'<rect x="{X(x0)}" y="{Y(y1)}" width="{x1-x0:.2f}" height="{y1-y0:.2f}" rx="4" fill="none" stroke="#999" stroke-width=".35"/>',
       f'<rect x="{X(-35.25)}" y="{Y(-8)}" width="74.25" height="63" fill="#edf7f4" stroke="#4b8e75" stroke-width=".35"/>',
       f'<text x="{X(2)}" y="{Y(-40)}" text-anchor="middle" font-size="4" fill="#44806d">RETAIN LOWER DISPLAY</text>',
    ]
    for s in variant["sides"]:
        minx,miny,maxx,maxy=s["pcb_rect_case_xy_mm"]
        res.append(f'<rect x="{X(minx)}" y="{Y(maxy)}" width="{maxx-minx}" height="{maxy-miny}" fill="none" stroke="#1764b5" stroke-width=".35"/>')
        capw,caph=VARIANTS[name]["keycap_mm"]
        for k in s["keys"]:
            x,y,_=k["case_center_xyz_mm"]
            px,py=X(x-capw/2),Y(y+caph/2)
            res.extend([
                f'<rect x="{px}" y="{py}" width="{capw}" height="{caph}" rx=".7" fill="#e4edf8" stroke="#154975" stroke-width=".2"/>',
                f'<text x="{X(x)}" y="{Y(y)+.95:.2f}" text-anchor="middle" font-family="sans-serif" font-size="{1.6 if len(k["label"])>3 else 2.6}" fill="#162d41">{html.escape(k["label"])}</text>',
            ])
    res.extend([
       '<line x1="16" y1="155" x2="66" y2="155" stroke="#222" stroke-width=".5"/>',
       '<line x1="16" y1="153" x2="16" y2="157" stroke="#222" stroke-width=".5"/>',
       '<line x1="66" y1="153" x2="66" y2="157" stroke="#222" stroke-width=".5"/>',
       '<text x="41" y="163" text-anchor="middle" font-family="sans-serif" font-size="4">50 mm scale check</text>',
       '<text x="9" y="178" font-family="sans-serif" font-size="4">BOTH halves must be typed with thumbs on an unmodified donor first.</text>',
       '<text x="9" y="185" font-family="sans-serif" font-size="3.4">Check case corner curvature, central display border, closed lid and controls underneath.</text>',
       '<text x="9" y="192" font-family="sans-serif" font-size="3.4">Keycap dimensions are approximations; switch tactile feel and actuation not tested.</text>',
       '<text x="9" y="203" font-family="sans-serif" font-size="3.4">External wings MUST detach before folding unless hinge clearances are physically proven.</text>',
       '</svg>',
    ])
    return "\n".join(res)+"\n"

VARIANTS={
  "flush_7mm":{"keycap_mm":(5.5,7)},
  "detachable_9mm":{"keycap_mm":(8,8)},
}

def main():
    doc=json.loads(SRC.read_text())
    for name,variant in doc["variants"].items():
        path=HERE/"generated"/name/f"thor_{name}_1to1_A4.svg"
        path.write_text(template(name,variant))
        print(path.relative_to(HERE))

if __name__=="__main__":main()
