"""Independent electrical-interface and BOM preflight for HS Sensor 001.

This verifier reads *actual generated source files* and their receipt. It can
prove symbolic catalog wiring and target source pins agree, but it is NOT KiCad
ERC, a real board pinout measurement or a supplier qualification.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from .device_plan import build_device_plan, module_library
from .device_firmware import resolve_shared_i2c_bus

SCHEMA="hardware_splicer.sensor_electrical_preflight.v1"
BOM_SCHEMA="hardware_splicer.sensor_bom_provenance.v1"


def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def canonical(data:dict)->bytes:
    return (json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()


def check(condition:bool,message:str)->None:
    if not condition:
        raise ValueError("Electrical/BOM preflight refused: "+message)


def assess(project:Path)->tuple[dict,dict]:
    project=Path(project)
    receipt=json.loads((project/"CROSS_DOMAIN_RECEIPT.json").read_text())
    check(receipt.get("schema_version")=="hardware_splicer.cross_domain_sensor_001.v1","unknown receipt schema")
    check(receipt.get("revision_consistent") is True,"unverified source revision")
    names=("DEVICE_SPEC.json","DEVICE_PLAN.json","FIRMWARE_SOURCE.zip")
    for name in names:
        body=(project/name).read_bytes()
        target=receipt["artifacts"][name]
        check(sha(body)==target["sha256"] and len(body)==target["bytes"],name+" does not match receipt")
    spec=json.loads((project/"DEVICE_SPEC.json").read_text())
    plan=json.loads((project/"DEVICE_PLAN.json").read_text())
    check(sha((project/"DEVICE_SPEC.json").read_bytes())==receipt["source_spec_sha256"],"source digest invalid")
    check(build_device_plan(spec)==plan,"wiring plan not reproducible from input spec")
    check(plan["counts"]["errors"]==0 and plan["counts"]["warnings"]==0,"catalog plan still contains findings")
    check(spec["power"]["source"]=="usb","not an authorized USB-sourced reference")
    byid={m["id"]:m for m in plan["modules"]}
    check(set(byid)=={"mcu","sensor"},"expected exactly MCU and sensor")
    check(byid["mcu"]["module"]=="esp32-devkitc-v4","wrong MCU variant")
    check(byid["sensor"]["module"]=="adafruit-bme280-stemma-qt","wrong sensor breakout")
    catalogue={m["id"]:m for m in module_library()["modules"]}
    check(len(plan["wires"])==4,"reference requires exactly four direct jumpers")

    # Symbolic physical nets, not KiCad electrical rule checking.
    edges=set()
    pinnames={row["id"]:{p["name"] for p in row["pins"]} for row in plan["modules"]}
    for wire in plan["wires"]:
        ends=[(wire[end]["module"],wire[end]["pin"]) for end in ("from","to")]
        check(ends[0]!=ends[1],"shorted self-loop wire")
        for mod,pin in ends:
            check(mod in pinnames and pin in pinnames[mod],"wire refers to nonexistent catalog pin")
        edges.add(frozenset(ends))
    must={
        frozenset({("sensor","Vin"),("mcu","3V3")}),
        frozenset({("sensor","GND"),("mcu","GND")}),
        frozenset({("sensor","SDI"),("mcu","IO21")}),
        frozenset({("sensor","SCK"),("mcu","IO22")}),
    }
    check(edges==must,"reference electrical nets differ, are shorted or connect to unsafe pins")
    bus,decl=resolve_shared_i2c_bus(plan)
    check(bus["sda"]["gpio"]==21 and bus["scl"]["gpio"]==22,
          "unexpected ESP32 firmware I2C pinout")
    check(len(decl)==1 and decl[0]["library_id"]=="adafruit-bme280-stemma-qt",
          "wrong I2C sensor identity")

    blob=(project/"FIRMWARE_SOURCE.zip").read_bytes()
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        check(len(archive.namelist())==len(set(archive.namelist())),"duplicate firmware files")
        source=archive.read("src/main.cpp").decode("utf-8")
        embedded=json.loads(archive.read("FIRMWARE_PROPOSAL.json"))
        check(json.loads(archive.read("DEVICE_SPEC.json"))==spec,"embedded firmware spec stale")
        check(json.loads(archive.read("DEVICE_PLAN.json"))==plan,"embedded firmware wiring stale")
        descriptor=json.loads(archive.read("PART_DESCRIPTOR.json"))
    check(embedded.get("spec_sha256")==receipt["source_spec_sha256"],
          "embedded firmware spec digest differs")
    check(embedded.get("part",{}).get("library_id")=="adafruit-bme280-stemma-qt",
          "firmware part mismatches hardware BOM")
    check(embedded.get("part",{}).get("descriptor_sha256")==sha(canonical(descriptor)),
          "firmware part descriptor not source-bound")
    check(embedded.get("pins")==bus,"firmware pin bindings disagree with electrical connectivity")
    for signal,gpio in (("SDA",21),("SCL",22)):
        occurrences=re.findall(r"(?m)^constexpr int "+signal+r"_PIN\s*=\s*(\d+);\s*$",source)
        check(occurrences==[str(gpio)],"compiled Arduino source pin "+signal+" differs from plan")
    check("Wire.begin(SDA_PIN, SCL_PIN, 100000)" in source,"firmware I2C setup missing")
    check(embedded.get("firmware_authorized") is False and embedded.get("power_on_authorized") is False,
          "firmware improperly approves physical use")

    parts=[]
    for m in plan["modules"]:
        item=catalogue[m["module"]]
        check(m["sources"]==item["sources"],"module catalog source provenance drift")
        parts.append({
            "design_ref":m["id"],"catalog_id":m["module"],"catalog_name":item["name"],
            "quantity":1,"sources":item["sources"],"source_count":len(item["sources"]),
            "procurement_status":"UNQUALIFIED",
            "exact_vendor_and_board_revision_physically_confirmed":False,
            "catalog_dimensions_measured":False,
            "electrical_ratings_verified_on_real_board":False,
        })
    stock=[{"description":row["item"],"quantity":row["quantity"],
            "status":"UNQUALIFIED", "note":row.get("note")}
           for row in plan["shopping"]
           if "jumper wire" in row["item"].lower() or "micro-usb" in row["item"].lower()]
    bom={
        "schema_version":BOM_SCHEMA,
        "source_spec_sha256":receipt["source_spec_sha256"],
        "catalog_source":"src/hardware_splicer/data/device_modules.json",
        "parts":parts,
        "supporting_materials":stock,
        "supplier_price_verified":False,
        "supply_current_budget_measured":False,
        "regulator_and_pullup_behavior_measured":False,
        "bom_fabrication_ready":False,
    }
    electrical={
        "schema_version":SCHEMA,
        "source_spec_sha256":receipt["source_spec_sha256"],
        "firmware_source_zip_sha256":sha(blob),
        "firmware_main_cpp_sha256":sha(source.encode()),
        "part_descriptor_sha256":sha(canonical(descriptor)),
        "catalog_module_ids":["esp32-devkitc-v4","adafruit-bme280-stemma-qt"],
        "symbolic_nets":[
            {"sensor":s,"mcu":m} for s,m in
            (("Vin","3V3"),("GND","GND"),("SDI","IO21"),("SCK","IO22"))
        ],
        "i2c_gpios":{"sda":21,"scl":22},
        "software_source_pin_consistency":True,
        "symbolic_catalog_net_consistency":True,
        "reference_supply_selection":"ESP32 3V3 -> Adafruit BME280 Vin",
        "catalog_sources_present":True,
        "pinout_physically_measured":False,
        "i2c_pullup_network_verified":False,
        "rail_current_measured":False,
        "native_kicad_erc_drc_executed":False,
        "electrical_hardware_qualified":False,
        "fabrication_authorized":False,
        "power_on_authorized":False,
        "blockers":[
            "Only four symbolic jumper wires; no native KiCad schematic/PCB or ERC/DRC",
            "BME280 header/voltage-level shifting and I2C pullups not measured on selected breakout",
            "ESP32 3.3V rail available current with radio/sensor load not bench verified",
            "Vendor parts, board revisions and packaging not independently procured/qualified",
            "Physical solder joints, header alignment, cable polarity and wiring not inspected",
        ],
    }
    return electrical,bom


def write(project:Path)->tuple[dict,dict]:
    electrical,bom=assess(project)
    project=Path(project)
    targets={"ELECTRICAL_PREFLIGHT.json":electrical,"BOM_PROVENANCE.json":bom}
    if any((project/name).exists() for name in targets):
        raise FileExistsError("Refusing to overwrite earlier electrical/BOM evidence")
    for name,data in targets.items():
        (project/name).write_bytes(canonical(data))
    return electrical,bom
