"""Electrical and procurement qualification tests; real HS generator, no mocks."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest
from hardware_splicer.sensor_electrical_preflight import assess, write

ROOT=Path(__file__).resolve().parents[1]
loader=importlib.util.spec_from_file_location(
    "hs_sensor_source", ROOT/"scripts/generate_cross_domain_sensor_001.py")
source=importlib.util.module_from_spec(loader)
loader.loader.exec_module(source)


def candidate(tmp_path:Path)->Path:
    root=tmp_path/"candidate"
    source.build_cross_domain_package(source.sensor_only_spec(),root)
    return root


def replace_zip_file(project:Path,name:str,transform)->None:
    old=project/"FIRMWARE_SOURCE.zip"
    with zipfile.ZipFile(old) as z:
        names=z.namelist()
        content={n:z.read(n) for n in names}
    content[name]=transform(content[name])
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_STORED) as z:
        for n in sorted(content):
            z.writestr(n,content[n])
    raw=stream.getvalue()
    old.write_bytes(raw)
    receiptfile=project/"CROSS_DOMAIN_RECEIPT.json"
    receipt=json.loads(receiptfile.read_text())
    receipt["artifacts"]["FIRMWARE_SOURCE.zip"]={
        "sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)
    }
    receiptfile.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")


def test_real_generated_firmware_vs_4_pin_electrical_and_unqualified_bom(tmp_path):
    root=candidate(tmp_path)
    electrical,bom=write(root)
    assert electrical["software_source_pin_consistency"]
    assert electrical["i2c_gpios"]=={"sda":21,"scl":22}
    assert len(electrical["symbolic_nets"])==4
    assert {p["catalog_id"] for p in bom["parts"]}=={
        "esp32-devkitc-v4","adafruit-bme280-stemma-qt"}
    assert all(p["sources"] and p["procurement_status"]=="UNQUALIFIED" for p in bom["parts"])
    assert all(p["electrical_ratings_verified_on_real_board"] is False for p in bom["parts"])
    assert not electrical["native_kicad_erc_drc_executed"]
    assert not electrical["power_on_authorized"]
    with pytest.raises(FileExistsError):
        write(root)


def test_forged_firmware_i2c_bindings_rejected_even_if_zip_receipt_resealed(tmp_path):
    root=candidate(tmp_path)
    def swap(raw:bytes)->bytes:
        data=json.loads(raw)
        data["pins"]["sda"]["gpio"]=22
        return json.dumps(data,sort_keys=True).encode()
    replace_zip_file(root,"FIRMWARE_PROPOSAL.json",swap)
    with pytest.raises(ValueError,match="firmware pin bindings"):
        assess(root)


def test_source_code_gpio_conflict_rejected_even_if_zip_receipt_resealed(tmp_path):
    root=candidate(tmp_path)
    def tamper(raw:bytes)->bytes:
        assert b"constexpr int SDA_PIN = 21;" in raw
        return raw.replace(b"constexpr int SDA_PIN = 21;",b"constexpr int SDA_PIN = 22;")
    replace_zip_file(root,"src/main.cpp",tamper)
    with pytest.raises(ValueError,match="source pin SDA"):
        assess(root)


def test_forged_catalog_module_identity_rejected(tmp_path):
    root=candidate(tmp_path)
    plan=root/"DEVICE_PLAN.json"
    data=json.loads(plan.read_text())
    data["modules"][1]["module"]="different_board"
    plan.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    receipt=root/"CROSS_DOMAIN_RECEIPT.json"
    value=json.loads(receipt.read_text())
    body=plan.read_bytes()
    value["artifacts"]["DEVICE_PLAN.json"]={"sha256":hashlib.sha256(body).hexdigest(),"bytes":len(body)}
    receipt.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
    with pytest.raises(ValueError,match="wiring plan not reproducible"):
        assess(root)


def test_3v3_to_5v_swapped_signal_blocked_by_plan_layer(tmp_path):
    spec=source.sensor_only_spec()
    spec["connections"]=[
       {"from":c["from"],"to":"mcu.5V" if c["from"]=="sensor.Vin" else c["to"]}
       for c in spec["connections"]
    ]
    from hardware_splicer.device_plan import DevicePlanError
    with pytest.raises(DevicePlanError):
        source.build_cross_domain_package(spec,tmp_path/"unsafe")
