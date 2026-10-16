"""What an AI agent sees: the spec schema, the described operations, and suggestions that repair a broken spec."""
import copy
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.device_plan import (
    WIRE_COLORS, DevicePlanError, build_device_plan, device_catalog, device_spec_json_schema, example_specs, module_library,
)
from hardware_splicer.mcp_backend_gateway import task_operation_manifest
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def conforms(spec, schema):
    """The few rules of the schema a model's output could break; enough to compare with what the planner accepts."""
    props = schema["properties"]
    modules = props["modules"]
    ids = modules["items"]["properties"]["module"]["enum"]
    slug = re.compile(modules["items"]["properties"]["id"]["pattern"])
    endpoint = re.compile(props["connections"]["items"]["properties"]["from"]["pattern"])
    if not 1 <= len(spec["modules"]) <= modules["maxItems"]:
        return False
    if any(m["module"] not in ids or not slug.match(m["id"]) for m in spec["modules"]):
        return False
    for wire in spec.get("connections", []):
        if not endpoint.match(wire["from"]) or not endpoint.match(wire["to"]):
            return False
        if "wire" in wire and wire["wire"] not in props["connections"]["items"]["properties"]["wire"]["enum"]:
            return False
    return True


def test_the_schema_is_built_from_the_library_and_agrees_with_what_the_planner_accepts():
    schema = device_spec_json_schema()
    items = schema["properties"]["modules"]["items"]["properties"]
    assert items["module"]["enum"] == [m["id"] for m in module_library()["modules"]]
    assert schema["properties"]["connections"]["items"]["properties"]["wire"]["enum"] == sorted(WIRE_COLORS)
    case = schema["properties"]["case"]["properties"]
    base = example_specs()["esp32_oled_usb"]
    for key, low, high in (("wall_mm", case["wall_mm"]["minimum"], case["wall_mm"]["maximum"]), ("clearance_mm", case["clearance_mm"]["minimum"], case["clearance_mm"]["maximum"])):
        for value, ok in ((low, True), (high, True), (low - 0.01, False), (high + 0.01, False)):
            spec = copy.deepcopy(base)
            spec["case"][key] = value
            if ok:
                assert build_device_plan(spec)["counts"]["errors"] == 0
            else:
                with pytest.raises(DevicePlanError):
                    build_device_plan(spec)
    assert case["antenna_clearance"]["type"] == case["board_stops"]["type"] == "boolean"


def test_every_example_conforms_and_a_spec_the_schema_rejects_is_rejected_by_the_planner_too():
    schema = device_spec_json_schema()
    for name, spec in example_specs().items():
        assert conforms(spec, schema), name
    bad_module = copy.deepcopy(example_specs()["esp32_oled_usb"])
    bad_module["modules"][1]["module"] = "ssd1327-imaginary"
    assert not conforms(bad_module, schema)
    with pytest.raises(DevicePlanError):
        build_device_plan(bad_module)
    bad_wire = copy.deepcopy(example_specs()["esp32_oled_usb"])
    bad_wire["connections"][0]["wire"] = "plaid"
    assert not conforms(bad_wire, schema)
    with pytest.raises(DevicePlanError):
        build_device_plan(bad_wire)


def test_the_catalogue_lists_each_modules_real_pins_and_roles():
    library = {m["id"]: m for m in module_library()["modules"]}
    catalogue = device_catalog()
    assert [row["id"] for row in catalogue] == list(library)
    pico = next(row for row in catalogue if row["id"] == "raspberry-pi-pico")
    assert len(pico["pins"]) == 40 and any(p["name"] == "GP4" and "i2c_sda_default" in p["roles"] for p in pico["pins"])
    assert next(row for row in catalogue if row["id"] == "ssd1306-096-i2c")["i2c_addresses"] == ["0x3C", "0x3D"]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp("agent")
    import os

    os.environ["HARDWARE_SPLICER_OUTPUT_ROOT"] = str(root)
    return TestClient(create_product_app(ProjectStore(root / "store")))


def test_the_spec_schema_endpoint_serves_the_schema_and_catalogue(client):
    body = client.get("/v1/devices/spec-schema").json()
    assert body["ok"] is True and body["schema"] == device_spec_json_schema() and body["modules"] == device_catalog()


def test_every_device_operation_is_described_and_those_taking_a_spec_carry_its_schema(client):
    paths = client.get("/openapi.json").json()["paths"]
    device = {path: ops for path, ops in paths.items() if path.startswith("/v1/devices")}
    assert len(device) >= 10
    for path, ops in device.items():
        for method, op in ops.items():
            assert op["summary"] and not op["summary"].startswith(("Post ", "Get ")), (method, path)
            assert len(op["description"]) > 40, (method, path)
    for path in ("/v1/devices/plan", "/v1/devices/engineering", "/v1/devices/case", "/v1/devices/application", "/v1/devices/firmware", "/v1/devices/application/run"):
        schema = paths[path]["post"]["requestBody"]["content"]["application/json"]["schema"]
        assert "modules" in schema["properties"], path
    description = paths["/v1/devices/plan"]["post"]["description"]
    assert "approves nothing" in description and "suggestions" in description
    assert "never a pass" in paths["/v1/devices/engineering"]["post"]["description"]


def test_the_device_design_task_manifest_gives_an_agent_the_whole_workflow_in_one_call():
    manifest = task_operation_manifest("device_design", create_product_app())
    assert manifest["workflow_operation_ids"] == [
        "get_spec_schema_v1_devices_spec_schema_get", "get_examples_v1_devices_examples_get", "post_draft_v1_devices_draft_post", "post_plan_v1_devices_plan_post",
        "post_engineering_v1_devices_engineering_post", "post_case_v1_devices_case_post", "post_application_v1_devices_application_post",
        "post_application_run_v1_devices_application_run_post", "post_observations_v1_devices_observations_post",
    ]
    assert manifest["authority_contract"] == {"projection_grants_physical_authority": False, "backend_gates_bypassed": False, "automatic_execution": False}
    plan = next(op for op in manifest["operations"] if op["operation_id"].startswith("post_plan"))
    assert "modules" in plan["operation"]["requestBody"]["content"]["application/json"]["schema"]["properties"]


def test_the_task_manifest_offers_every_operation_the_agent_guide_lists_in_its_order():
    # The guide's loop table and the projection drifted once: application/run was documented but not offered.
    guide = (Path(__file__).resolve().parents[1] / "docs" / "AGENT_DEVICE_DESIGN.md").read_text()
    listed = re.findall(r"^\| \d+b? \| `(GET|POST) (/v1/devices/[a-z/-]+)` \|", guide, flags=re.MULTILINE)
    manifest = task_operation_manifest("device_design", create_product_app())
    offered = [(op["method"], op["path"]) for op in manifest["operations"]]
    assert listed and offered == listed


def apply_first_suggestions(spec, plan):
    """What a simple agent does with the planner's suggestions: take the first candidate. Returns whether it changed anything."""
    changed = False
    wires_by_id = {w["id"]: w for w in plan["wires"]}
    for finding in plan["findings"]:
        for suggestion in finding.get("suggestions", []):
            if suggestion["action"] == "add_connection":
                spec["connections"].append({"from": suggestion["from"], "to": suggestion["to_one_of"][0]})
                changed = True
            elif suggestion["action"] == "replace_connection":
                wire = wires_by_id[suggestion["wire"]]
                for row in spec["connections"]:
                    if suggestion["from"] in (row["from"], row["to"]) and f"{wire['to']['module']}.{wire['to']['pin']}" in (row["from"], row["to"]):
                        key = "to" if row["from"] == suggestion["from"] else "from"
                        row[key] = suggestion["to_one_of"][0]
                        changed = True
            elif suggestion["action"] == "move_signal":
                signal = "SCL" if suggestion["signal"] == "scl" else "SDA"
                if not suggestion["to_one_of"]:
                    continue
                for row in spec["connections"]:
                    if row["from"].upper().endswith("." + signal):
                        row["to"] = suggestion["to_one_of"][0]
                        changed = True
                        break
                else:
                    continue
                return changed  # one move at a time, then re-plan
    return changed


def break_a_wire(spec, source):
    spec["connections"] = [c for c in spec["connections"] if c["from"] != source]


def swap_sda_to(spec, pin):
    for row in spec["connections"]:
        if row["from"] == "display.SDA":
            row["to"] = f"mcu.{pin}"


@pytest.mark.parametrize("name,damage", [
    ("esp32_oled_bme280_usb", lambda s: break_a_wire(s, "display.GND")),
    ("esp32_oled_bme280_usb", lambda s: break_a_wire(s, "sensor.SDI")),
    ("pico_oled_usb", lambda s: break_a_wire(s, "display.VCC")),
    ("pico_oled_usb", lambda s: swap_sda_to(s, "GP22")),
    ("pico_oled_usb", lambda s: swap_sda_to(s, "GP1")),
    ("pico_oled_bme280_usb", lambda s: (break_a_wire(s, "display.SCL"), break_a_wire(s, "sensor.SCK"))),
])
def test_following_the_suggestions_repairs_a_broken_spec_until_the_plan_has_no_errors(name, damage):
    spec = copy.deepcopy(example_specs()[name])
    damage(spec)
    plan = build_device_plan(spec)
    assert plan["counts"]["errors"] > 0
    for _ in range(6):
        if plan["counts"]["errors"] == 0:
            break
        assert apply_first_suggestions(spec, plan), [f["rule"] for f in plan["findings"] if f["severity"] == "error"]
        plan = build_device_plan(spec)
    assert plan["counts"]["errors"] == 0


def test_the_mixed_controller_suggestion_offers_only_pins_of_the_controller_already_in_use():
    spec = copy.deepcopy(example_specs()["pico_oled_usb"])
    for row in spec["connections"]:
        if row["from"] == "display.SCL":
            row["to"] = "mcu.GP7"  # I2C1, while SDA is on GP4 (I2C0)
    plan = build_device_plan(spec)
    finding = next(f for f in plan["findings"] if f["rule"] == "i2c_mixed_controllers")
    scl = next(s for s in finding["suggestions"] if s["signal"] == "scl")
    assert scl["to_one_of"] == ["mcu.GP1", "mcu.GP5", "mcu.GP9", "mcu.GP13", "mcu.GP17", "mcu.GP21"]  # I2C0 SCL pins only


def test_a_plan_with_no_errors_carries_no_suggestions_and_changes_no_bytes():
    plan = build_device_plan(example_specs()["esp32_oled_usb"])
    assert not any("suggestions" in f for f in plan["findings"])


# --- a suggestion must keep the design a design the rest of the product accepts -----------------------------------------


def _without(spec, pin):
    broken = copy.deepcopy(spec)
    broken["connections"] = [w for w in broken["connections"] if not w["from"].startswith(pin)]
    return broken


def _missing(spec):
    return next(f for f in build_device_plan(spec)["findings"] if f["rule"] == "missing_connection")


@pytest.mark.parametrize("pin", ["sensor.SDI", "sensor.SCK", "display.SDA", "display.SCL"])
def test_a_missing_bus_wire_is_suggested_onto_the_pin_the_other_module_already_uses(pin):
    spec = _without(example_specs()["esp32_oled_bme280_usb"], pin)
    suggestion = _missing(spec)["suggestions"][0]
    expected = "mcu.IO21" if pin.endswith(("SDI", "SDA")) else "mcu.IO22"
    assert suggestion["to_one_of"] == [expected]
    assert suggestion["joins_existing_bus"] is True


@pytest.mark.parametrize("pin", ["sensor.SDI", "sensor.SCK", "display.SDA", "display.SCL"])
def test_applying_that_suggestion_gives_a_design_the_firmware_export_accepts(pin):
    from hardware_splicer.device_firmware import build_device_firmware

    spec = _without(example_specs()["esp32_oled_bme280_usb"], pin)
    suggestion = _missing(spec)["suggestions"][0]
    spec["connections"].append({"from": suggestion["from"], "to": suggestion["to_one_of"][0]})
    plan = build_device_plan(spec)
    assert not [f for f in plan["findings"] if f["severity"] in {"error", "warning"}]
    metadata, _archive = build_device_firmware(spec)
    assert (metadata["pins"]["sda"]["gpio"], metadata["pins"]["scl"]["gpio"]) == (21, 22)


def test_with_no_bus_wired_yet_the_suggestion_is_still_a_choice_and_says_nothing_about_joining():
    spec = example_specs()["esp32_oled_bme280_usb"]
    spec = {**spec, "connections": [w for w in spec["connections"] if not w["from"].endswith((".SDA", ".SDI"))]}
    for finding in build_device_plan(spec)["findings"]:
        if finding["rule"] == "missing_connection" and "suggestions" in finding:
            suggestion = finding["suggestions"][0]
            assert len(suggestion["to_one_of"]) > 1 and "joins_existing_bus" not in suggestion
