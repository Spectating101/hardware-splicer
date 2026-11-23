import hashlib
import json
from pathlib import Path
import struct

import pytest

from scripts import prepare_sort_workcell_001 as workcell


def test_openarm_preview_requires_pinned_metadata_and_matching_mesh_nodes(tmp_path, monkeypatch):
    names = [f"part_{index}" for index in range(542)]
    geometry = json.dumps({"nodes": [{"name": name, "mesh": index}
                                    for index, name in enumerate(names)]}).encode()
    geometry += b" " * (-len(geometry) % 4)
    glb = tmp_path / "source.glb"
    raw = struct.pack("<4sIII4s", b"glTF", 2, len(geometry) + 20, len(geometry), b"JSON") + geometry
    glb.write_bytes(raw)
    metadata = tmp_path / "source.json"
    raw_metadata = json.dumps({"totalParts": len(names), "parts": [{"node": name} for name in names]}).encode()
    metadata.write_bytes(raw_metadata)
    monkeypatch.setattr(workcell, "SOURCE_SHA", hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(workcell, "METADATA_SHA", hashlib.sha256(raw_metadata).hexdigest())

    output = tmp_path / "verified"
    receipt = workcell.build(glb, metadata, output, Path(__file__).resolve().parents[1])
    assert receipt["metadata_matches_mesh_nodes"]
    assert (output / "machine" / "robot_metadata.json").read_bytes() == raw_metadata

    renamed = raw_metadata.replace(b'"part_0"', b'"unrelated_part"')
    metadata.write_bytes(renamed)
    rejected = tmp_path / "rejected"
    with pytest.raises(ValueError, match="metadata revision/content mismatch"):
        workcell.build(glb, metadata, rejected, tmp_path)
    monkeypatch.setattr(workcell, "METADATA_SHA", hashlib.sha256(renamed).hexdigest())
    with pytest.raises(ValueError, match="identities do not match"):
        workcell.build(glb, metadata, rejected, tmp_path)
    assert not rejected.exists()
