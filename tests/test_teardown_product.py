"""Contract tests use synthetic fixtures; native Teardown runs separately in CI."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import pytest
from hardware_splicer.multicad_toolchain import canonical,digest
from hardware_splicer.teardown_product import source_model,export,validate_native_browser


def fixture(root:Path):
    refs=root/"references"
    refs.mkdir(parents=True)
    (refs/"bracket.step").write_bytes(b"synthetic native step data fixture")
    dest=root/"partcad"/"parts"
    dest.mkdir(parents=True)
    (dest/"bracket.step").write_bytes(b"synthetic alternative step fixture")
    row={"id":"bracket","shape":"box","dimensions_mm":[40,30,5],
         "reference_step":"references/bracket.step",
         "reference_sha256":digest((refs/"bracket.step").read_bytes()),
         "source_status":"conceptual_analytic_reference","physical_tested":False}
    manifest={"schema_version":"hardware_splicer.multicad_parts.v1",
              "product_id":"unrelated_hardware_product",
              "source_spec_sha256":"a"*64,"parts":[row],
              "vendor_geometry_qualified":False,"physical_release_authorized":False}
    (root/"PARTS_MANIFEST.json").write_bytes(canonical(manifest))
    record={"id":"bracket","authored_step_sha256":digest((dest/"bracket.step").read_bytes()),
            "reference_sha256":row["reference_sha256"],"dimensions_mm":[40,30,5],
            "independent_step_round_trip_pass":True,
            "manufacturer_qualified":False,"fabrication_authorized":False}
    (root/"MULTICAD_NATIVE_EVIDENCE.json").write_bytes(canonical({
        "schema_version":"hardware_splicer.multicad_native_evidence.v1",
        "source_spec_sha256":"a"*64,"product_id":manifest["product_id"],
        "parts":[record],"partcad_cli_executed":False,"physical_release_authorized":False}))
    log=b"Native PartCAD CLI test fixture (not executed)\n"
    (root/"PARTCAD_CLI.log").write_bytes(log)
    (root/"PARTCAD_EXECUTION_RECEIPT.json").write_bytes(canonical({
        "schema_version":"hardware_splicer.partcad_package_receipt.v1",
        "source_spec_sha256":"a"*64,"native_partcad_cli_ran":True,
        "native_cad_part_count":1,"fabrication_authorized":False,
        "all_native_parts_manufacturer_qualified":False,"partcad_log_sha256":digest(log)}))
    return manifest


def test_visualization_manifest_reusable_across_product_ids(tmp_path):
    root=tmp_path/"cad"
    fixture(root)
    data=source_model(root)
    assert data["product_id"]=="unrelated_hardware_product"
    assert data["parts"][0]["extents_mm"]==[40,30,5]
    assert not data["physical_kinematics_verified"]
    out=tmp_path/"teardown"
    report=export(root,out)
    assert (out/"machine/main.js").is_file()
    assert data["source_spec_sha256"] in (out/"machine/main.js").read_text()
    assert report["native_browser_run"] is False


@pytest.mark.parametrize("mode",["altered_step","missing_cli","forged_cli","changed_log","fake_physical","wrong_revision"])
def test_refuse_forged_or_stale_upstream_cad(tmp_path,mode):
    root=tmp_path/"cad"
    fixture(root)
    if mode=="altered_step":
        (root/"partcad/parts/bracket.step").write_bytes(b"modified")
    elif mode=="missing_cli":
        (root/"PARTCAD_EXECUTION_RECEIPT.json").unlink()
    else:
        p=root/"PARTCAD_EXECUTION_RECEIPT.json"
        record=json.loads(p.read_text())
        if mode=="forged_cli": record["native_partcad_cli_ran"]=False
        if mode=="changed_log": (root/"PARTCAD_CLI.log").write_bytes(b"changed")
        if mode=="fake_physical": record["fabrication_authorized"]=True
        if mode=="wrong_revision": record["source_spec_sha256"]="f"*64
        p.write_bytes(canonical(record))
    with pytest.raises((ValueError, OSError)):
        source_model(root)


def test_refuse_browser_claim_without_real_html_and_screenshot(tmp_path):
    root=tmp_path/"cad";fixture(root)
    out=tmp_path/"teardown";export(root,out)
    with pytest.raises((ValueError,OSError)):
        validate_native_browser(out)
