"""Actual upstream-native UUID map capture with source-backed tamper tests."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hardware_splicer.integrations.kicad_runtime_uuid_provenance import (
    verify_converter_uuid_provenance,
    verify_files,
)

ROOT=Path(__file__).resolve().parents[1]
SCHEMATIC=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch"
TOOLS=ROOT/"examples/integrations/kicad-circuit-json"


@pytest.fixture(scope="module")
def real_sources(tmp_path_factory):
    if not shutil.which("kicad-cli") or not shutil.which("node") or not shutil.which("npm"):
        pytest.skip("real KiCad CLI, Node and npm required")
    folder=tmp_path_factory.mktemp("uuid-provenance")
    if not (TOOLS/"node_modules").exists():
        r=subprocess.run(["npm","install","--no-audit","--no-fund"],cwd=TOOLS,
                         capture_output=True,text=True,timeout=160)
        assert r.returncode==0,r.stderr
    net=folder/"official.net"
    docs=folder/"converted.json"
    receipt=folder/"native-uuid.json"
    original=folder/"without-provenance.json"
    export=subprocess.run(["kicad-cli","sch","export","netlist",
        "--format","kicadsexpr","--output",str(net),str(SCHEMATIC)],
        capture_output=True,text=True,timeout=95)
    assert export.returncode==0,export.stderr
    p=subprocess.run(["node",str(TOOLS/"convert_with_provenance.mjs"),
        str(SCHEMATIC),str(docs),str(receipt)],
        capture_output=True,text=True,timeout=100)
    assert p.returncode==0,p.stderr
    c=subprocess.run(["node",str(TOOLS/"convert.mjs"),
        str(SCHEMATIC),str(original)],
        capture_output=True,text=True,timeout=100)
    assert c.returncode==0,c.stderr
    return SCHEMATIC,net,docs,receipt,original


def _validate(schematic,net,docs,receipt):
    return verify_converter_uuid_provenance(
        schematic.read_bytes(),net.read_text(encoding="utf-8"),
        json.dumps(docs,indent=2).encode()+b"\n" if isinstance(docs,list) else docs,
        json.dumps(receipt,indent=2).encode()+b"\n" if isinstance(receipt,dict) else receipt,
    )


def test_upstream_converter_has_direct_runtime_uuid_40_of_40_with_79_source_pins(real_sources):
    schematic,net,docs,receipt,original=real_sources
    r=verify_files(schematic,net,docs,receipt)
    assert r["native_uuid_entries_verified"]==40
    assert r["physical_component_uuid_links_verified"]==36
    assert r["nonphysical_power_flags_uuid_links_verified"]==4
    assert r["source_port_numbers_reconciled_to_official_export"]==79
    assert r["direct_converter_runtime_uuid_mapping"]
    assert r["source_sheet_paths_verified"]==40
    assert not r["electrical_net_connectivity_verified_here"]
    assert not r["geometry_electrical_merge_authorized"]
    assert not r["manufacturing_authorized"]
    # No changes to standard Circuit JSON payload were required.
    assert docs.read_bytes()==original.read_bytes()


def test_uuid_sidecar_consistent_bijection_rejects_swapping_identical_resistor_uuids(real_sources):
    schematic,net,docs,receipt,_=real_sources
    side=copy.deepcopy(json.loads(receipt.read_text()))
    a=next(x for x in side["records"] if x["native_reference"]=="R2")
    b=next(x for x in side["records"] if x["native_reference"]=="R3")
    a["native_symbol_uuid"],b["native_symbol_uuid"]=b["native_symbol_uuid"],a["native_symbol_uuid"]
    with pytest.raises(ValueError,match="identity mismatch"):
        _validate(schematic,net,docs.read_bytes(),side)


def test_converter_schematic_component_crosswalk_forgery_fails(real_sources):
    schematic,net,docs,receipt,_=real_sources
    side=copy.deepcopy(json.loads(receipt.read_text()))
    a=next(x for x in side["records"] if x["native_reference"]=="R2")
    b=next(x for x in side["records"] if x["native_reference"]=="R3")
    a["schematic_component_id"],b["schematic_component_id"]=b["schematic_component_id"],a["schematic_component_id"]
    with pytest.raises(ValueError,match="wrong visual/source"):
        _validate(schematic,net,docs.read_bytes(),side)


def test_tampered_uuids_and_missing_sheet_instance_fail_closed(real_sources):
    schematic,net,docs,receipt,_=real_sources
    original=json.loads(receipt.read_text())
    for mutation in ("uuid","path","ref"):
        side=copy.deepcopy(original)
        item=next(x for x in side["records"] if x["native_reference"]=="U1")
        if mutation=="uuid":item["native_symbol_uuid"]="00000000-0000-0000-0000-000000000000"
        if mutation=="path":item["native_sheet_uuid_path"]="/invented/"
        if mutation=="ref":item["native_reference"]="U999"
        with pytest.raises(ValueError):
            _validate(schematic,net,docs.read_bytes(),side)


def test_tampered_original_source_or_source_hash_fails(real_sources):
    schematic,net,docs,receipt,_=real_sources
    bad=schematic.read_bytes()+b"\n; synthetic modification\n"
    with pytest.raises(ValueError,match="SHA256"):
        verify_converter_uuid_provenance(
            bad,net.read_text(),docs.read_bytes(),receipt.read_bytes()
        )


def test_loss_or_duplicate_native_uuid_entry_fails_closed(real_sources):
    schematic,net,docs,receipt,_=real_sources
    side=json.loads(receipt.read_text())
    side["records"].pop()
    with pytest.raises(ValueError,match="cover each"):
        _validate(schematic,net,docs.read_bytes(),side)
    side=json.loads(receipt.read_text())
    side["records"][0]=dict(side["records"][1])
    with pytest.raises(ValueError,match="repeated"):
        _validate(schematic,net,docs.read_bytes(),side)


def test_forged_upstream_output_with_recomputed_digest_is_still_rejected(real_sources):
    schematic,net,docs,receipt,_=real_sources
    mutated=json.loads(docs.read_text())
    item=next(x for x in mutated if x["type"]=="schematic_component")
    item["source_component_id"]="invented_fake_source_component"
    raw=json.dumps(mutated,indent=2).encode()+b"\n"
    side=json.loads(receipt.read_text())
    side["converter_output_sha256"]=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError,match="wrong visual/source"):
        _validate(schematic,net,raw,side)


def test_converter_pin_number_spoof_is_detected_even_if_output_rehashed(real_sources):
    schematic,net,docs,receipt,_=real_sources
    mutated=json.loads(docs.read_text())
    row=next(x for x in mutated if x["type"]=="source_port" and x.get("pin_number")==1)
    row["pin_number"]=999
    raw=json.dumps(mutated,indent=2).encode()+b"\n"
    side=json.loads(receipt.read_text())
    side["converter_output_sha256"]=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):
        _validate(schematic,net,raw,side)


def test_provenance_not_a_netlist_or_physical_repair_certificate(real_sources):
    *_,receipt,_=real_sources
    item=json.loads(receipt.read_text())
    assert item["source_wire_connectivity_authenticated"] is False
    assert item["original_converter_output_modified"] is False
    assert item["capture"]=="upstream_converter_ctx_symbolUuidToComponentId"
    assert all(x["native_symbol_uuid"] for x in item["records"])
