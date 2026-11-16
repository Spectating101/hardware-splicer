"""Source-bound native KiCad acceptance must reject altered or forged evidence."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "spi_native_acceptance",ROOT/"scripts/verify_native_spi_capability.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DESIGN=ROOT/"hardware/reference_designs/spi_flash_adapter_v1"


def fixture():
    receipt=json.loads((DESIGN/"verification.json").read_text())
    manifest=json.loads((DESIGN/"design_manifest.json").read_text())
    erc={"$schema":"https://schemas.kicad.org/erc.v1.json",
         "source":"spi_flash_adapter_v1.kicad_sch",
         "sheets":[{"violations":[]}]}
    drc={"$schema":"https://schemas.kicad.org/drc.v1.json",
         "source":"spi_flash_adapter_v1.kicad_pcb",
         "violations":[],"unconnected_items":[],"schematic_parity":[]}
    hashes={key:module.sha((DESIGN/name).read_bytes())
            for key,name in module.RECEIPT_FILES.items()}
    return receipt,manifest,erc,drc,hashes


def test_original_source_and_existing_receipt_fit_strict_native_contract():
    module.verify_native_reports(*fixture())


@pytest.mark.parametrize("key",[
    "fabrication_ready","power_on_ready","physical_authority_granted",
])
def test_forged_physical_authority_rejected(key):
    receipt,manifest,erc,drc,hashes=fixture()
    receipt["authority"][key]=True
    with pytest.raises(ValueError,match="physical authority"):
        module.verify_native_reports(receipt,manifest,erc,drc,hashes)


def test_stale_board_file_or_new_schematic_fails():
    receipt,manifest,erc,drc,hashes=fixture()
    hashes["pcb"]="b"*64
    with pytest.raises(ValueError,match="canonical schematic"):
        module.verify_native_reports(receipt,manifest,erc,drc,hashes)


def test_unconnected_pad_and_erc_violation_rejected():
    receipt,manifest,erc,drc,hashes=fixture()
    drc["unconnected_items"]=[{"type":"unconnected","severity":"error"}]
    with pytest.raises(ValueError,match="unconnected nets"):
        module.verify_native_reports(receipt,manifest,erc,drc,hashes)
    receipt,manifest,erc,drc,hashes=fixture()
    erc["sheets"][0]["violations"]=[{"type":"pin_to_pin","severity":"error"}]
    with pytest.raises(ValueError,match="ERC contains"):
        module.verify_native_reports(receipt,manifest,erc,drc,hashes)


def test_missing_schematic_parity_cannot_be_claimed():
    receipt,manifest,erc,drc,hashes=fixture()
    del drc["schematic_parity"]
    with pytest.raises(ValueError,match="schematic parity"):
        module.verify_native_reports(receipt,manifest,erc,drc,hashes)


def test_forged_zero_drc_when_actual_report_warning_present_rejected():
    receipt,manifest,erc,drc,hashes=fixture()
    drc["violations"]=[{"type":"clearance","severity":"warning"}]
    with pytest.raises(ValueError,match="finding count"):
        module.verify_native_reports(receipt,manifest,erc,drc,hashes)


def test_unsupported_major_version_rejected():
    receipt,manifest,erc,drc,hashes=fixture()
    receipt["toolchain"]["kicad_cli"]="10.0.0"
    with pytest.raises(ValueError,match="KiCad 9"):
        module.verify_native_reports(receipt,manifest,erc,drc,hashes)


def test_incomplete_bom_or_assembly_check_rejected():
    receipt,manifest,erc,drc,hashes=fixture()
    del receipt["checks"]["bom_parity_issues"]
    with pytest.raises(ValueError,match="engineering checks"):
        module.verify_native_reports(receipt,manifest,erc,drc,hashes)
