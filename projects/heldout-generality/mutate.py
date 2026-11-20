"""Construct a deliberately invalid copper-to-other-net bridge (digital-only).

Use KiCad's native pcbnew, not text substitution. The original input remains
untouched. This must never be sent to fabrication or energized.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import uuid
from pathlib import Path

import pcbnew


def make_short(source: Path, destination: Path) -> dict:
    pcb = pcbnew.LoadBoard(str(source))
    pads = sorted(
        (
            p for f in pcb.GetFootprints() for p in f.Pads()
            if p.GetNetCode() > 0 and p.IsOnLayer(pcbnew.F_Cu)
        ),
        key=lambda p: (p.GetParentFootprint().GetReference(), p.GetNumber(), p.GetNetCode()),
    )
    candidates = []
    for index, a in enumerate(pads):
        for b in pads[index + 1:]:
            if a.GetNetCode() == b.GetNetCode():
                continue
            delta = a.GetPosition() - b.GetPosition()
            dx = pcbnew.ToMM(delta.x)
            dy = pcbnew.ToMM(delta.y)
            d = math.hypot(dx, dy)
            if 1.0 <= d <= 9.0:
                candidates.append((round(d, 6), a, b))
    if not candidates:
        raise ValueError("no local same-layer different-net pad pair; mutation unsupported")
    _, a, b = min(
        candidates,
        key=lambda r: (r[0], r[1].GetNetname(), r[2].GetNetname(),
                       r[1].GetParentFootprint().GetReference(),
                       r[2].GetParentFootprint().GetReference()),
    )
    track = pcbnew.PCB_TRACK(pcb)
    track.SetStart(a.GetPosition())
    track.SetEnd(b.GetPosition())
    track.SetLayer(pcbnew.F_Cu)
    track.SetWidth(pcbnew.FromMM(0.20))
    track.SetNet(a.GetNet())
    pcb.Add(track)
    pcbnew.SaveBoard(str(destination), pcb)
    # KiCad assigns random UUIDs to new tracks. Normalize only this synthetic
    # track ID to make DRC de-duplication deterministic across independent runs.
    generated_uuid = track.m_Uuid.AsString()
    content = destination.read_text(encoding="utf-8")
    if content.count(generated_uuid) != 1:
        raise ValueError("new track UUID not uniquely serialized")
    stable_name = ":".join([
        "hs-heldout-v1",
        hashlib.sha256(source.read_bytes()).hexdigest(),
        a.GetParentFootprint().GetReference(), a.GetNumber(), a.GetNetname(),
        b.GetParentFootprint().GetReference(), b.GetNumber(), b.GetNetname(),
    ])
    stable_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, stable_name))
    destination.write_text(content.replace(generated_uuid, stable_uuid), encoding="utf-8")
    return {
        "type": "intentional_F_Cu_different_net_bridge",
        "origin_ref": a.GetParentFootprint().GetReference(),
        "target_ref": b.GetParentFootprint().GetReference(),
        "origin_net": a.GetNetname(),
        "target_net": b.GetNetname(),
        "distance_mm": round(math.hypot(
            pcbnew.ToMM(a.GetPosition().x-b.GetPosition().x),
            pcbnew.ToMM(a.GetPosition().y-b.GetPosition().y)), 6),
        "physical_test_performed": False,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: mutate.py <original.kicad_pcb> <invalid.kicad_pcb>")
    result = make_short(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(result, sort_keys=True))
