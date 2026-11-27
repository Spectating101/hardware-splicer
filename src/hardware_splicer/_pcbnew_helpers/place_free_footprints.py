"""Constructive placement of a board's free footprints (pcbnew, KiCad 9/10), for HS's component-board pipeline.

    python3 place.py BOARD_IN BOARD_OUT --locked REF,REF,... [--hints hints.json] [--gap 0.5] [--passes 2]

Places each free footprint, one at a time, where its pads are nearest the already placed pads they connect to:
* the order follows connectivity: the free part with the most connections to placed pads goes next;
* a decoupling capacitor (two pads: a supply and ground) is tied to one IC supply pin of that supply, spread one
  capacitor per pin where it can be, and held close to it with the capacitor's ground near the IC's ground pin;
* supply and ground nets reach everywhere, so they pull weakly; signal nets pull fully;
* a footprint keeps its courtyard (and its drawn silkscreen and pads) clear of every other part by a routing gap and
  1 mm from the board edge, and stays on the top side;
* hints may name, per part, other parts it should sit near ({"U3": ["Q1"]}) or a region ({"U3": [x0, y0, x1, y1]}).
Then refinement passes lift and re-place each free part with everything else in place. Reference and value labels of
free parts are hidden (the task allows it), so no label lands on a pad.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys

import numpy as np
import pcbnew

RES = 0.25          # occupancy grid, mm
STEP = 0.5          # candidate centre spacing, mm
EDGE = 1.05         # courtyard to board edge, mm
GND_RE = re.compile(r"(^|[^A-Z])(GND|GNDA|GNDD|AGND|DGND|PGND|VSS)([^A-Z]|$)", re.I)
SUPPLY_RE = re.compile(r"^[+]?\d+V\d*$|^\+\d+V|^V(CC|DD|BUS|SYS)|^\+?3V3$|^\+?5V$|^\+?12V$", re.I)
mm = pcbnew.ToMM


def is_gnd(n): return bool(GND_RE.search(n or ""))
def is_supply(n): return bool(n) and not is_gnd(n) and bool(SUPPLY_RE.search(n))


def keep_clear_box(fp):
    """Courtyard, pads and silkscreen drawing: what the rule check compares between parts (not fabrication drawings)."""
    boxes = []
    for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        cy = fp.GetCourtyard(layer)
        if cy.OutlineCount():
            boxes.append(cy.BBox())
    for pad in fp.Pads():
        boxes.append(pad.GetBoundingBox())
    for item in fp.GraphicalItems():
        if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and "TEXT" not in item.GetClass().upper():
            boxes.append(item.GetBoundingBox())
    return (min(mm(b.GetX()) for b in boxes), min(mm(b.GetY()) for b in boxes),
            max(mm(b.GetRight()) for b in boxes), max(mm(b.GetBottom()) for b in boxes))


def footprint_geometry(fp):
    """Per rotation: the keep-clear box relative to the position and the pads (dx, dy, net)."""
    out = {}
    pos = fp.GetPosition(); orient = fp.GetOrientationDegrees()
    fp.SetPosition(pcbnew.VECTOR2I(0, 0))
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        x0, y0, x1, y1 = keep_clear_box(fp)
        pads = [(mm(p.GetPosition().x), mm(p.GetPosition().y), p.GetNetname()) for p in fp.Pads()]
        out[rot] = {"box": (x0, y0, x1, y1), "pads": pads}
    fp.SetOrientationDegrees(orient); fp.SetPosition(pos)
    return out


class Placer:
    def __init__(self, board, locked, hints, gap):
        self.b = board; self.gap = gap; self.hints = hints or {}
        bb = board.GetBoardEdgesBoundingBox()
        self.ox, self.oy = mm(bb.GetX()), mm(bb.GetY())
        self.W, self.H = mm(bb.GetWidth()), mm(bb.GetHeight())
        self.nx, self.ny = int(math.ceil(self.W / RES)) + 1, int(math.ceil(self.H / RES)) + 1
        self.occ = np.zeros((self.ny, self.nx), dtype=np.int32)
        e = int(math.ceil(EDGE / RES))
        self.occ[:e, :] = 1; self.occ[-e:, :] = 1; self.occ[:, :e] = 1; self.occ[:, -e:] = 1
        self.fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
        self.locked = set(locked)
        self.free = [r for r in self.fps if r not in self.locked]
        self.geo = {r: footprint_geometry(self.fps[r]) for r in self.free}
        self.net_pads: dict[str, list[tuple[float, float, str]]] = {}
        self.where: dict[str, tuple[float, float, int]] = {}
        self.boxes: dict[str, tuple[int, int, int, int]] = {}
        for r in self.locked:
            fp = self.fps[r]
            self._mark_fp(r, fp, inflate=0.0)
            for p in fp.Pads():
                self.net_pads.setdefault(p.GetNetname(), []).append((mm(p.GetPosition().x), mm(p.GetPosition().y), r))
        self.decap = self._decoupling()

    # -------------------------------------------------------------- occupancy
    def _cells(self, x0, y0, x1, y1):
        return (max(0, int((x0 - self.ox) / RES)), max(0, int((y0 - self.oy) / RES)),
                min(self.nx, int(math.ceil((x1 - self.ox) / RES)) + 1), min(self.ny, int(math.ceil((y1 - self.oy) / RES)) + 1))

    def _mark_fp(self, ref, fp, inflate):
        x0, y0, x1, y1 = keep_clear_box(fp)
        c = self._cells(x0 - inflate, y0 - inflate, x1 + inflate, y1 + inflate)
        self.occ[c[1]:c[3], c[0]:c[2]] += 1
        self.boxes[ref] = c

    def _unmark(self, ref):
        c = self.boxes.pop(ref)
        self.occ[c[1]:c[3], c[0]:c[2]] -= 1

    def _inflate(self, ref):
        n = len(self.geo[ref][0]["pads"])
        # fine-pitch ICs need room to fan their pins out; small parts need one track's channel
        return self.gap if n <= 3 else self.gap * 1.6 if n < 8 else self.gap * 3.0

    # -------------------------------------------------------------- decoupling
    def _decoupling(self):
        """Capacitor -> (IC ref, supply pin xy-net) assignment; ICs are footprints with 5+ pads on that supply."""
        caps = {}
        for r in self.free:
            pads = self.geo[r][0]["pads"]
            nets = {p[2] for p in pads}
            if r.startswith("C") and len(pads) == 2 and len(nets) == 2 and any(is_gnd(n) for n in nets) and any(is_supply(n) for n in nets):
                caps[r] = next(n for n in nets if is_supply(n))
        def value_f(ref):
            v = self.fps[ref].GetValue().lower().split()[0]
            m = re.match(r"([\d.]+)\s*([pnu]?)", v)
            if not m: return 1.0
            return float(m.group(1)) * {"p": 1e-6, "n": 1e-3, "u": 1.0, "": 1.0}[m.group(2)]
        ics = {}
        for r, fp in self.fps.items():
            if len(fp.Pads()) < 5 or not re.match(r"^(U|IC)\d", r): continue
            for p in fp.Pads():
                if is_supply(p.GetNetname()):
                    ics.setdefault(p.GetNetname(), []).append((r, p.GetNumber()))
        assign, load = {}, {}
        for cap in sorted(caps, key=value_f):
            pins = ics.get(caps[cap], [])
            if not pins: continue
            pin = min(pins, key=lambda rp: (load.get(rp, 0), len(self.fps[rp[0]].Pads())))
            load[pin] = load.get(pin, 0) + 1
            assign[cap] = {"ic": pin[0], "pin": pin[1], "net": caps[cap]}
        return assign

    def _ic_pin(self, ref, num):
        fp = self.fps[ref]
        for p in fp.Pads():
            if p.GetNumber() == num:
                return mm(p.GetPosition().x), mm(p.GetPosition().y)

    def _ic_gnd(self, ref, near):
        pts = [(mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in self.fps[ref].Pads() if is_gnd(p.GetNetname())]
        return min(pts, key=lambda q: math.dist(q, near)) if pts else None

    # -------------------------------------------------------------- scoring
    def _ready(self, ref):
        d = self.decap.get(ref)
        return d is None or d["ic"] in self.locked or d["ic"] in self.where

    def _pull(self, ref):
        """How strongly the part is tied to what is placed: signal-net connections to placed pads."""
        if ref in self.decap and self._ready(ref):
            return 100.0
        s = 0.0
        for _, _, n in self.geo[ref][0]["pads"]:
            if not n or is_gnd(n): continue
            k = len(self.net_pads.get(n, []))
            s += (0.05 if is_supply(n) else 1.0) * min(k, 3)
        for h in self.hints.get(ref, []):
            if isinstance(h, str) and (h in self.where or h in self.locked): s += 2.0
        return s + 0.01 * len(self.geo[ref][0]["pads"])

    def _targets(self, ref):
        """(pad index, target points, weight) terms for the part, plus a soft centre target."""
        terms = []
        pads = self.geo[ref][0]["pads"]
        dec = self.decap.get(ref)
        for i, (_, _, n) in enumerate(pads):
            if not n: continue
            if dec and n == dec["net"]:
                terms.append((i, np.array([self._ic_pin(dec["ic"], dec["pin"])]), 6.0)); continue
            if dec and is_gnd(n):
                pin = self._ic_pin(dec["ic"], dec["pin"]); g = self._ic_gnd(dec["ic"], pin)
                if g: terms.append((i, np.array([g]), 1.5))
                continue
            pts = [(x, y) for x, y, r in self.net_pads.get(n, []) if r != ref]
            if not pts: continue
            w = 0.1 if is_gnd(n) else 0.15 if is_supply(n) else 1.0
            terms.append((i, np.array(pts), w))
        centre = None; region = None
        for h in self.hints.get(ref, []):
            if isinstance(h, str) and (h in self.where or h in self.locked):
                fp = self.fps[h]; terms.append((-1, np.array([(mm(fp.GetX()), mm(fp.GetY()))]), 2.0))
            elif isinstance(h, list) and len(h) == 4:
                region = h
        pts = np.concatenate([t[1] for t in terms]) if terms else None
        if region:
            centre = ((region[0] + region[2]) / 2, (region[1] + region[3]) / 2)
        elif pts is not None:
            centre = tuple(pts.mean(axis=0))
        else:
            centre = (self.ox + self.W / 2, self.oy + self.H / 2)
        return terms, centre, region

    def _feasible(self, ref, rot, inflate):
        x0, y0, x1, y1 = self.geo[ref][rot]["box"]
        wcell = int(math.ceil((x1 - x0 + 2 * inflate) / RES)) + 1
        hcell = int(math.ceil((y1 - y0 + 2 * inflate) / RES)) + 1
        ii = np.pad(np.cumsum(np.cumsum(self.occ > 0, axis=0), axis=1), ((1, 0), (1, 0)))
        S = ii[hcell:, wcell:] - ii[:-hcell, wcell:] - ii[hcell:, :-wcell] + ii[:-hcell, :-wcell]
        free = S == 0     # free[j, i]: the box whose top-left cell is (i, j) is clear
        return free, (x0 - inflate, y0 - inflate)

    def place(self, ref):
        terms, centre, region = self._targets(ref)
        inflate = self._inflate(ref)
        best = None
        for rot in (0, 90, 180, 270):
            free, (bx0, by0) = self._feasible(ref, rot, inflate)
            js, is_ = np.nonzero(free)
            if not len(js): continue
            cx = self.ox + is_ * RES - bx0; cy = self.oy + js * RES - by0
            keep = (np.abs(np.round(cx / STEP) * STEP - cx) < 1e-6) | True
            if region:
                keep &= (cx >= region[0]) & (cx <= region[2]) & (cy >= region[1]) & (cy <= region[3])
            d = np.hypot(cx - centre[0], cy - centre[1])
            for radius in (6, 12, 25, 60, 1e9):
                sel = keep & (d <= radius)
                if sel.sum() >= 40 or radius > 1e8: break
            cx, cy, d = cx[sel], cy[sel], d[sel]
            if len(cx) > 6000:
                idx = np.argsort(d)[:6000]; cx, cy, d = cx[idx], cy[idx], d[idx]
            if not len(cx): continue
            pads = self.geo[ref][rot]["pads"]
            score = 0.02 * d
            for i, pts, w in terms:
                if i < 0:
                    px, py = cx, cy
                else:
                    px, py = cx + pads[i][0], cy + pads[i][1]
                dist = np.min(np.hypot(px[:, None] - pts[None, :, 0], py[:, None] - pts[None, :, 1]), axis=1)
                score = score + w * dist
            k = int(np.argmin(score))
            if best is None or score[k] < best[0]:
                best = (float(score[k]), float(cx[k]), float(cy[k]), rot)
        if best is None:
            raise RuntimeError(f"no room for {ref}")
        _, x, y, rot = best
        self._put(ref, x, y, rot, inflate)
        return best

    def _put(self, ref, x, y, rot, inflate):
        fp = self.fps[ref]
        fp.SetOrientationDegrees(rot); fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        self._mark_fp(ref, fp, inflate)
        self.where[ref] = (x, y, rot)
        for p in fp.Pads():
            self.net_pads.setdefault(p.GetNetname(), []).append((mm(p.GetPosition().x), mm(p.GetPosition().y), ref))

    def _lift(self, ref):
        self._unmark(ref); self.where.pop(ref)
        for n in list(self.net_pads):
            self.net_pads[n] = [t for t in self.net_pads[n] if t[2] != ref]

    def run(self, passes):
        def big(r):
            x0, y0, x1, y1 = self.geo[r][0]["box"]
            return (x1 - x0) * (y1 - y0) >= 30 or len(self.geo[r][0]["pads"]) >= 5
        for phase in ([r for r in self.free if big(r)], [r for r in self.free if not big(r)]):
            pending = list(phase)
            while pending:
                ready = [r for r in pending if self._ready(r)] or pending
                ref = max(ready, key=self._pull)
                self.place(ref); pending.remove(ref)
        for _ in range(passes):
            for ref in sorted(self.free, key=lambda r: -len(self.geo[r][0]["pads"])):
                old = self.where[ref]; inflate = self._inflate(ref)
                self._lift(ref)
                try:
                    self.place(ref)
                except RuntimeError:
                    self._put(ref, old[0], old[1], old[2], inflate)
        for r in self.free:
            fp = self.fps[r]; fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
        return {"placed": {r: self.where[r] for r in self.free}, "decoupling": self.decap}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board"); ap.add_argument("out")
    ap.add_argument("--locked", required=True); ap.add_argument("--hints")
    ap.add_argument("--gap", type=float, default=0.5); ap.add_argument("--passes", type=int, default=2)
    a = ap.parse_args()
    b = pcbnew.LoadBoard(a.board)
    hints = json.load(open(a.hints)) if a.hints else {}
    res = Placer(b, a.locked.split(","), hints, a.gap).run(a.passes)
    pcbnew.SaveBoard(a.out, b)
    json.dump(res, open(a.out + ".placement.json", "w"), indent=1)
    print(json.dumps({"placed": len(res["placed"]), "decoupling": res["decoupling"]}))


if __name__ == "__main__":
    sys.exit(main())
