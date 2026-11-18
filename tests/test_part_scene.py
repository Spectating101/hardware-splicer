from collections import Counter
import io
import json
from pathlib import Path
import shutil
import struct
import zipfile

import pytest

from hardware_splicer.part_scene import build_parts_sidecar

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects/cyberdeck-real-trial-20261020"
STATUS = Path("docs/status/generated/fielddeck-display-swap-20261118.json")
GLB7 = Path("digital_v1/cad/FIELDDECK_7.glb")
DISPLAY7 = "touch_display_2_manufacturer"
DISPLAY5 = "touch_display_2_5inch_sc1975"
STATES = {"datasheet", "assumed", "computed", "unknown"}
DIFF_STATES = {"unchanged", "changed", "added", "removed"}


def _glb(parts, *, padding=0):
    binary = bytearray(b"\0" * padding)
    nodes = [{"name": "world", "children": list(range(1, len(parts) + 1))}]
    meshes, views, accessors = [], [], []
    for i, (name, x, extras) in enumerate(parts):
        start = len(binary)
        # Position is interleaved with an ignored float and starts after it.
        binary.extend(struct.pack("<12f", 99, x, 0, 0, 99, x + 2, 0, 0, 99, x, 2, 0))
        views.append({"buffer": 0, "byteOffset": start, "byteLength": 48, "byteStride": 16})
        accessors.append({"bufferView": 2 * i, "byteOffset": 4, "componentType": 5126, "count": 3,
                          "type": "VEC3", "min": [x, 0, 0], "max": [x + 2, 2, 0]})
        start = len(binary)
        binary.extend(struct.pack("<3I", 0, 1, 2))
        views.append({"buffer": 0, "byteOffset": start, "byteLength": 12})
        accessors.append({"bufferView": 2 * i + 1, "componentType": 5125, "count": 3, "type": "SCALAR"})
        nodes.append({"name": name, "mesh": i, "extras": extras})
        meshes.append({"primitives": [{"attributes": {"POSITION": 2 * i}, "indices": 2 * i + 1}]})
    doc = {"asset": {"version": "2.0"}, "scenes": [{"nodes": [0]}], "scene": 0,
           "nodes": nodes, "meshes": meshes, "bufferViews": views, "accessors": accessors,
           "buffers": [{"byteLength": len(binary)}]}
    model = json.dumps(doc).encode()
    model += b" " * (-len(model) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 28 + len(model) + len(binary))
            + struct.pack("<I4s", len(model), b"JSON") + model
            + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


@pytest.fixture
def fixture_project(tmp_path):
    project = tmp_path / "projects" / PROJECT.name
    for relative in (
        "digital_v1/cad/geometry_report.json", "digital_v1/design.json", "digital_v1/bom.json",
        "digital_v1/sources/references.json", "digital_v1/analysis/calculations.json",
        "display_swap/sources/evidence.json",
    ):
        destination = project / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / relative, destination)
    status = tmp_path / STATUS
    status.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / STATUS, status)

    common = [("pi4_board_envelope", 10, {}), ("pi4_dsi", 11, {}),
              ("keyboard_nominal_envelope", 20, {}),
              ("extra-node", 77, {"explode_m": [0, 0, 0.07]})]
    baseline = _glb(common + [("face_rear_left", 2, {}), (DISPLAY7, 30, {})])
    swap = _glb([(DISPLAY5, 30, {}), ("face_rear_left", 3, {}), *reversed(common)], padding=16)
    (project / GLB7).write_bytes(baseline)
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as archive:
        archive.writestr("revision/cad/FIELDDECK_5.glb", swap)
    with zipfile.ZipFile(project / "display_swap/export.zip", "w") as archive:
        archive.writestr("delivered/revision.zip", nested.getvalue())
    return project, baseline, swap


def _inventory(glb):
    size = struct.unpack_from("<I", glb, 12)[0]
    doc = json.loads(glb[20:20 + size])
    payload = 28 + size
    widths = {"SCALAR": 1, "VEC3": 3}
    component_sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}

    def signature(index):
        accessor = doc["accessors"][index]
        view = doc["bufferViews"][accessor["bufferView"]]
        start = payload + view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        width = widths[accessor["type"]] * component_sizes[accessor["componentType"]]
        stride = view.get("byteStride", width)
        stop = start + stride * accessor["count"]
        return accessor["componentType"], [glb[i:i + width] for i in range(start, stop, stride)]

    result = {}
    for node in doc["nodes"]:
        name = node.get("name")
        occurrence = 1 + sum(key[0] == name for key in result)
        result[name, occurrence] = [
            (primitive.get("mode", 4), signature(primitive["attributes"]["POSITION"]),
             signature(primitive["indices"]) if "indices" in primitive else None)
            for primitive in doc["meshes"][node["mesh"]]["primitives"]
        ] if "mesh" in node else None
    return result


def _assert_diff(diff, baseline, swap, delivered=False):
    # The recorded swap (docs/status/generated/fielddeck-display-swap-20261118.json) changes exactly the
    # four rear enclosure pieces, adds the 5-inch display and four spacers, and removes the 7-inch display.
    # Re-exported but identical parts must stay unchanged even though their mesh bytes differ.
    previous, current = _inventory(baseline), _inventory(swap)
    if delivered:
        changed = {("tray_rear_left", 1), ("face_rear_left", 1), ("tray_rear_right", 1), ("face_rear_right", 1)}
        expected = {key: "changed" if key in changed else "unchanged" for key in previous.keys() & current.keys()}
    else:   # synthetic fixtures are written fresh, so byte equality is exact there
        expected = {key: "unchanged" if previous[key] == current[key] else "changed"
                    for key in previous.keys() & current.keys()}
    expected.update(dict.fromkeys(previous.keys() - current.keys(), "removed"))
    expected.update(dict.fromkeys(current.keys() - previous.keys(), "added"))
    if delivered:
        assert {key for key, state in expected.items() if state == "removed"} == {("touch_display_2_manufacturer", 1)}
        assert len([state for state in expected.values() if state == "added"]) == 5
    assert diff["status"] == "available"
    assert len(diff["nodes"]) == len(expected)
    assert {(row["node_name"], row["occurrence"]): row["status"] for row in diff["nodes"]} == expected
    assert diff["counts"] == dict(Counter(expected.values())) | {
        state: 0 for state in DIFF_STATES - set(expected.values())
    }


@pytest.mark.parametrize("revision", ["7", "5"])
def test_parts_schema_and_evidence(fixture_project, revision):
    project, baseline, swap = fixture_project
    scene = build_parts_sidecar(project, revision)
    status = json.loads((ROOT / STATUS).read_text())
    assert scene["schema_version"] == "hardware_splicer.parts_sidecar.v1"
    assert scene["units"] == scene["glb_native_units"] == "mm"
    assert scene["glb_scale_to_mm"] == 1
    assert scene["missing_inputs"] == []
    parts = scene["parts"]
    nodes = _inventory(baseline if revision == "7" else swap)
    assert Counter(part["node_name"] for part in parts) == Counter(name for name, _ in nodes)
    assert len({part["part_id"] for part in parts}) == len(nodes)
    assert {part["node_index"] for part in parts} == set(range(len(nodes)))
    for part in parts:
        assert part["label"] and part["group"]
        assert part["geometry_basis"] in {"envelope", "custom", "vendor_step", "proxy", "unknown"}
        assert part["no_bom_line"] == (part["bom_line"] is None)
        assert len(part["explode_vector_mm"]) == 3
        for evidence in part["evidence"]:
            assert set(evidence) == {"field", "value", "state", "source", "source_sha256"}
            assert evidence["state"] != "measured"
            assert evidence["state"] in STATES
            if evidence["state"] != "unknown":
                assert evidence["source"]
                assert len(evidence["source_sha256"]) == 64

    by_name = {part["node_name"]: part for part in parts}
    assert by_name["world"]["geometry_basis"] == "unknown"
    for part in ("pi4_board_envelope", "pi4_dsi", "keyboard_nominal_envelope"):
        assert by_name[part]["geometry_basis"] == "envelope"
    assert by_name["pi4_board_envelope"]["group"] == by_name["pi4_dsi"]["group"] == "pi4"
    assert by_name["pi4_board_envelope"]["explode_vector_mm"] == by_name["pi4_dsi"]["explode_vector_mm"]
    assert by_name["pi4_dsi"]["explode_vector_mm"] == ([-29, 0, 0] if revision == "7" else [-29.5, 0, 0])
    assert by_name["pi4_dsi"]["explode_derived"] is True
    assert by_name["extra-node"]["explode_vector_mm"] == [0, 0, 70]
    assert by_name["extra-node"]["explode_derived"] is False
    display = by_name[DISPLAY7 if revision == "7" else DISPLAY5]
    assert display["geometry_basis"] == "vendor_step"
    assert display["bom_line"] == "display"
    assert {row["state"] for row in display["evidence"]} == STATES
    if revision == "7":
        assert display["explode_vector_mm"] == [0, 0, 65]
        assert display["explode_derived"] is False
    else:
        assert display["explode_derived"] is True
        assert scene["glb_source"].endswith("revision.zip!/revision/cad/FIELDDECK_5.glb")
    ribbon = next(row for row in scene["interfaces"] if row["interface_id"] == "display-ribbon")
    assert ribbon["endpoints_present"]
    assert ribbon["to_part_id"] == display["part_id"]
    assert ribbon["open_checks"][:2] == ["pin_mapping_unknown", "signal_voltage_unknown"]
    for reason in ribbon["open_checks"]:
        assert any(b["reason"] == reason and b.get("interface_id") == "display-ribbon" for b in scene["blockers"])
    assert scene["alternates"][0]["status"] == "blocked"
    assert scene["alternates"][0]["failed_checks"] == status["incompatible_control"]["failed_checks"]
    _assert_diff(scene["revision_diff"], baseline, swap)


def test_missing_inputs_do_not_create_parts_or_infer_removals(fixture_project):
    project, _, _ = fixture_project
    (project / GLB7).unlink()
    scene = build_parts_sidecar(project, 7)
    assert GLB7.as_posix() in scene["missing_inputs"]
    assert not scene["parts"]
    assert scene["revision_diff"]["status"] == "unavailable"
    assert not scene["revision_diff"]["nodes"]
    assert scene["revision_diff"]["counts"] == dict.fromkeys(DIFF_STATES, 0)
    assert not any(row["endpoints_present"] for row in scene["interfaces"])
    swap = build_parts_sidecar(project, 5)
    assert swap["parts"]
    assert swap["revision_diff"]["status"] == "unavailable"


def test_delivered_glb_inventory_and_diff():
    scene = build_parts_sidecar(PROJECT, "5")
    inputs = scene["missing_inputs"]
    if inputs:
        missing_meshes = [source for source in inputs if ".glb" in source]
        if missing_meshes:
            pytest.skip("Missing delivered GLBs: " + ", ".join(missing_meshes))
    # Independently reopen only the ZIP members named in the sidecar provenance.
    chunks = scene["glb_source"].split("!/")
    data = (PROJECT / chunks[0]).read_bytes()
    for member in chunks[1:]:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            data = archive.read(member)
    baseline = (PROJECT / GLB7).read_bytes()
    _assert_diff(scene["revision_diff"], baseline, data, delivered=True)
    for result, glb in ((scene, data), (build_parts_sidecar(PROJECT, 7), baseline)):
        assert Counter(part["node_name"] for part in result["parts"]) == Counter(name for name, _ in _inventory(glb))


def test_retriangulated_identical_part_is_unchanged_but_moved_vertex_is_changed():
    from hardware_splicer import part_scene

    square = (0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 10.0, 10.0, 0.0, 0.0, 10.0, 0.0)
    one_diagonal = part_scene._triangle_signature(4, square, (0, 1, 2, 0, 2, 3))
    other_diagonal = part_scene._triangle_signature(4, square, (0, 1, 3, 1, 2, 3))
    moved = part_scene._triangle_signature(4, square[:6] + (10.0, 10.5, 0.0) + square[9:], (0, 1, 2, 0, 2, 3))
    bounds = [0.0, 0.0, 0.0, 10.0, 10.0, 0.0]

    def node(signature):
        return (0, "digest-differs-every-time", bounds, {}, [signature])

    assert part_scene._same_geometry(node(one_diagonal), node(other_diagonal))
    assert not part_scene._same_geometry(node(one_diagonal), node(moved))
    assert not part_scene._same_geometry(node(None), node(None))
