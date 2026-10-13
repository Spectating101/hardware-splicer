"""The case export: closed printable solids whose numbers come from the plan, with no authority."""
import copy
import hashlib
import io
import json
import struct
import zipfile

import pytest

from hardware_splicer.device_case import DeviceCaseError, build_device_case, mesh_report
from hardware_splicer.device_plan import DevicePlanError, build_device_plan, example_specs


def read_stl(data):
    count = struct.unpack("<I", data[80:84])[0]
    assert len(data) == 84 + 50 * count
    tris = []
    for index in range(count):
        record = struct.unpack("<12fH", data[84 + 50 * index:134 + 50 * index])
        tris.append(tuple(tuple(record[3 + 3 * v:6 + 3 * v]) for v in range(3)))
    return tris


def inside(tris, point):
    """Even-odd ray cast along +x, nudged off the grid so it never grazes an edge."""
    px, py, pz = point[0], point[1] + 1e-4, point[2] + 2e-4
    hits = 0
    for a, b, c in tris:
        e1 = [b[i] - a[i] for i in range(3)]
        e2 = [c[i] - a[i] for i in range(3)]
        h = (0.0, -e2[2], e2[1])  # direction (1,0,0) x e2
        det = e1[0] * h[0] + e1[1] * h[1] + e1[2] * h[2]
        if abs(det) < 1e-12:
            continue
        s = [px - a[0], py - a[1], pz - a[2]]
        u = (s[0] * h[0] + s[1] * h[1] + s[2] * h[2]) / det
        if u < 0 or u > 1:
            continue
        q = (s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0])
        v = q[0] / det
        if v < 0 or u + v > 1:
            continue
        if q[0] * e2[0] / det + q[1] * e2[1] / det + q[2] * e2[2] / det > 0:
            hits += 1
    return hits % 2 == 1


@pytest.fixture(scope="module", params=sorted(example_specs()))
def exported(request):
    spec = example_specs()[request.param]
    meta, data = build_device_case(spec)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    return spec, build_device_plan(spec), meta, data, files


def test_each_part_is_a_closed_solid_measured_from_its_triangles(exported):
    _spec, _plan, meta, _data, files = exported
    for name in ("case_base", "case_lid"):
        report = mesh_report([tuple(tuple(round(c * 100) for c in v) for v in tri) for tri in read_stl(files[f"{name}.stl"])])
        assert report["closed_manifold"] is True and report["volume_mm3"] > 0
        assert report == {k: v for k, v in meta["meshes"][name].items()}


def test_the_volumes_match_a_hand_calculation_from_the_plan(exported):
    _spec, plan, meta, _data, _files = exported
    case = plan["case"]
    ox, oy, oz, w = case["outer_mm"]["x"], case["outer_mm"]["y"], case["outer_mm"]["z"], case["wall_mm"]
    top = case["lid_underside_y"]
    cavity = (ox - 2 * w) * (oz - 2 * w) * (top - w)
    usb = case["usb_cutout"]
    stops = sum((b["x1"] - b["x0"]) * (b["y1"] - b["y0"]) * (b["z1"] - b["z0"]) for b in (case.get("board_stops") or {}).get("boxes", []))
    base = ox * oz * top - cavity - usb["width_mm"] * usb["height_mm"] * w + stops
    assert meta["meshes"]["case_base"]["volume_mm3"] == pytest.approx(base, abs=0.5)
    from hardware_splicer.device_case import LIP_FIT_MM, LIP_HEIGHT_MM, LIP_WALL_MM
    lip_out_x, lip_out_z = ox - 2 * w - 2 * LIP_FIT_MM, oz - 2 * w - 2 * LIP_FIT_MM
    lip = (lip_out_x * lip_out_z - (lip_out_x - 2 * LIP_WALL_MM) * (lip_out_z - 2 * LIP_WALL_MM)) * LIP_HEIGHT_MM
    window = case["window"]
    lid = ox * oz * (oy - top) + lip - window["width_mm"] * window["depth_mm"] * (oy - top)
    assert meta["meshes"]["case_lid"]["volume_mm3"] == pytest.approx(lid, abs=0.5)


def test_the_parts_have_the_plans_outer_size_and_stand_on_a_flat_face(exported):
    _spec, plan, meta, _data, _files = exported
    outer = plan["case"]["outer_mm"]
    base, lid = meta["meshes"]["case_base"]["size_mm"], meta["meshes"]["case_lid"]["size_mm"]
    assert base[:2] == [outer["x"], outer["z"]] and base[2] == plan["case"]["lid_underside_y"]
    assert lid[:2] == [outer["x"], outer["z"]] and lid[2] == pytest.approx(outer["y"] - plan["case"]["lid_underside_y"] + 2.0)


def test_openings_are_open_and_walls_are_solid_when_probed_in_the_exported_file(exported):
    _spec, plan, _meta, _data, files = exported
    case = plan["case"]
    ox, oz, w = case["outer_mm"]["x"], case["outer_mm"]["z"], case["wall_mm"]
    base, lid = read_stl(files["case_base.stl"]), read_stl(files["case_lid.stl"])
    usb = case["usb_cutout"]
    y_mid = oz / 2 - usb["z"]  # base frame: Y = oz - (z + oz / 2)
    assert not inside(base, (w / 2, y_mid, usb["y"]))                       # through the USB opening
    assert inside(base, (w / 2, y_mid, usb["y"] + usb["height_mm"] / 2 + 3))  # wall above it
    assert inside(base, (ox / 2, oz / 2, w / 2))                            # floor
    assert not inside(base, (ox / 2, oz / 2, w + 5))                        # cavity
    window = case["window"]
    wx, wz = window["x"] + ox / 2, window["z"] + oz / 2
    assert not inside(lid, (wx, wz, 1.0))                                   # display window
    assert inside(lid, (wx + window["width_mm"] / 2 + 1, wz, 1.0))          # plate beside it
    assert inside(lid, (w + 0.3 + 0.5, oz / 2, 3.0))                        # the lip
    assert not inside(lid, (ox / 2, oz / 2, 3.0))                           # inside the lip


def test_the_package_is_deterministic_hashed_and_grants_nothing(exported):
    spec, _plan, meta, data, files = exported
    assert build_device_case(copy.deepcopy(spec))[1] == data
    assert meta["printed"] is False and meta["test_fitted"] is False
    assert meta["physical_correctness"] == "UNPROVEN"
    assert meta["firmware_authorized"] is False and meta["power_on_authorized"] is False
    assert json.loads(files["CASE_PROPOSAL.json"]) == meta
    for name, facts in meta["files"].items():
        assert hashlib.sha256(files[name]).hexdigest() == facts["sha256"]
    assert set(files) == {"case_base.stl", "case_base.scad", "case_lid.stl", "case_lid.scad", "README.md", "DEVICE_PLAN.json", "CASE_PROPOSAL.json"}
    assert b"has not been printed" in files["README.md"] and b"Thermal behaviour has not been assessed" in files["README.md"]
    assert not files["case_base.stl"].startswith(b"solid")  # a binary STL must not look like ASCII


def test_the_scad_files_hold_the_same_boxes(exported):
    _spec, _plan, _meta, _data, files = exported
    text = files["case_base.scad"].decode()
    assert text.count("cube(") >= 6 and "difference()" in text and "print orientation" in text


def test_a_plan_with_errors_is_refused_and_a_caller_cannot_supply_its_own_plan():
    spec = copy.deepcopy(example_specs()["esp32_oled_usb"])
    spec["connections"].append({"from": "display.VCC", "to": "mcu.GND"})
    with pytest.raises(DevicePlanError):
        build_device_case(spec)
    spec = copy.deepcopy(example_specs()["esp32_oled_usb"])
    honest = build_device_case(copy.deepcopy(spec))[1]
    spec["plan"] = {"case": {"style": "two_part_box", "wall_mm": 9.0, "outer_mm": {"x": 1, "y": 1, "z": 1}}}
    assert build_device_case(spec)[1] == honest  # a supplied plan is ignored; it is recomputed from the spec


def test_a_cutout_that_does_not_fit_its_wall_is_refused_not_silently_clipped(monkeypatch):
    import hardware_splicer.device_case as module

    real = module.build_device_plan

    def tall(spec):
        plan = real(spec)
        plan["case"]["usb_cutout"]["height_mm"] = 80.0
        return plan

    monkeypatch.setattr(module, "build_device_plan", tall)
    with pytest.raises(DeviceCaseError, match="USB cut-out"):
        module.build_device_case(example_specs()["esp32_oled_usb"])


def test_the_mesh_check_notices_a_hole():
    from hardware_splicer.device_case import _solid

    solid = _solid([(0, 100, 0, 100, 0, 100)], [])
    assert mesh_report(solid)["closed_manifold"] is True
    assert mesh_report(solid[:-1])["closed_manifold"] is False


def test_the_http_endpoint_serves_the_same_bytes_and_refuses_bad_specs(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from hardware_splicer.product_api import create_product_app
    from hardware_splicer.project_store import ProjectStore

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    client = TestClient(create_product_app(ProjectStore(tmp_path / "store")))
    spec = example_specs()["esp32_oled_bme280_usb"]
    expected = build_device_case(spec)[1]
    ok = client.post("/v1/devices/case", json=spec)
    assert ok.status_code == 200 and ok.headers["content-type"] == "application/zip"
    assert "device-case-proposal.zip" in ok.headers["content-disposition"] and ok.content == expected
    assert client.post("/v1/devices/case", json={"spec": spec}).content == expected
    assert client.post("/v1/devices/case", content=b"nope").status_code == 422
    broken = copy.deepcopy(spec)
    broken["connections"].append({"from": "display.VCC", "to": "mcu.GND"})
    assert client.post("/v1/devices/case", json=broken).status_code == 422


def test_the_exported_base_has_the_stop_blocks_where_the_plan_puts_them(exported):
    _spec, plan, _meta, _data, files = exported
    stops = (plan["case"].get("board_stops") or {}).get("boxes", [])
    assert len(stops) == 2
    base = read_stl(files["case_base.stl"])
    ox, oz = plan["case"]["outer_mm"]["x"], plan["case"]["outer_mm"]["z"]
    for box in stops:
        # Base frame: X = x, Y = oz - z, Z = y, with x and z centred in the plan.
        centre = ((box["x0"] + box["x1"]) / 2 + ox / 2, oz - ((box["z0"] + box["z1"]) / 2 + oz / 2), (box["y0"] + box["y1"]) / 2)
        assert inside(base, centre)
        above = (centre[0], centre[1], box["y1"] + 2.0)
        assert not inside(base, above)  # the block is low; the cavity is open above it
