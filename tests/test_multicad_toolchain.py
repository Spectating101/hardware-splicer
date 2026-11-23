"""Adversarial manifest contract tests. Native CAD is executed separately in CI."""
import copy,hashlib,json
from pathlib import Path
import pytest
from hardware_splicer.multicad_toolchain import (
    canonical, digest, shape_dimensions, validate_manifest,
    check_native_outputs, partcad_execution_receipt,
)


def fixture(root):
    root.mkdir(parents=True,exist_ok=True)
    refs=root/"references"
    refs.mkdir()
    b=b"independent-source-step-for-contract-fixtures"
    (refs/"stand.step").write_bytes(b)
    row={"id":"stand","shape":"box","dimensions_mm":[40,20,4],
         "reference_step":"references/stand.step","reference_sha256":digest(b),
         "source_status":"conceptual_analytic_reference","physical_tested":False}
    m={"schema_version":"hardware_splicer.multicad_parts.v1","product_id":"other_product",
       "source_spec_sha256":"a"*64,"parts":[row],
       "physical_release_authorized":False,"vendor_geometry_qualified":False}
    (root/"PARTS_MANIFEST.json").write_bytes(canonical(m))
    return m


def test_cross_product_generic_manifest_allowed(tmp_path):
    m=fixture(tmp_path/"parts")
    assert validate_manifest(tmp_path/"parts") == m
    assert shape_dimensions(m["parts"][0]) == (40.,20.,4.)


@pytest.mark.parametrize("change",[
    "path_traversal","wrong_source","duplicate","bad_shape","bad_dims",
    "missing_part","physical_claim","vendor_claim","unknown_revision",
])
def test_manifest_refuses_untrusted_input(tmp_path,change):
    root=tmp_path/"parts"
    m=fixture(root)
    p=m["parts"][0]
    if change=="path_traversal": p["reference_step"]="../../secret.step"
    elif change=="wrong_source": p["reference_sha256"]="0"*64
    elif change=="duplicate": m["parts"].append(copy.deepcopy(p))
    elif change=="bad_shape": p["shape"]="unverified_pressure_vessel"
    elif change=="bad_dims": p["dimensions_mm"]=[40,0,4]
    elif change=="missing_part": (root/"references"/"stand.step").unlink()
    elif change=="physical_claim": m["physical_release_authorized"]=True
    elif change=="vendor_claim": m["vendor_geometry_qualified"]=True
    elif change=="unknown_revision": m["source_spec_sha256"]="not-a-hash"
    (root/"PARTS_MANIFEST.json").write_bytes(canonical(m))
    with pytest.raises(ValueError,match="multi-CAD refused"):
        validate_manifest(root)


def test_native_receipt_requires_all_actual_step_files(tmp_path):
    root=tmp_path/"parts"
    m=fixture(root)
    dest=root/"partcad"/"parts"
    dest.mkdir(parents=True)
    output=b"test-only-synthetic-new-step"
    (dest/"stand.step").write_bytes(output)
    row={"id":"stand","reference_sha256":m["parts"][0]["reference_sha256"],
         "authored_step_sha256":digest(output),
         "independent_step_round_trip_pass":True,
         "manufacturer_qualified":False,"fabrication_authorized":False}
    report={"schema_version":"hardware_splicer.multicad_native_evidence.v1",
            "source_spec_sha256":m["source_spec_sha256"],
            "product_id":m["product_id"],"parts":[row],
            "partcad_cli_executed":False,"physical_release_authorized":False}
    (root/"MULTICAD_NATIVE_EVIDENCE.json").write_bytes(canonical(report))
    check_native_outputs(root)
    (dest/"stand.step").write_bytes(b"tamper")
    with pytest.raises(ValueError,match="multi-CAD refused"):
        check_native_outputs(root)


def test_partcad_log_not_a_substitute_for_real_native_execution(tmp_path):
    root=tmp_path/"parts"
    fixture(root)
    log=tmp_path/"cli.txt"
    log.write_text("")
    with pytest.raises((OSError,ValueError)):
        partcad_execution_receipt(root,log)
