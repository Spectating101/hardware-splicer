import pytest
from hardware_splicer.kicad_registered_source_check import (
    registered_kicad_kind, check_kicad_bytes, kicad_source_check_enabled,
)
from hardware_splicer import kicad_registered_source_check as module


def test_verified_format_gate():
    assert registered_kicad_kind("foo.kicad_sch", b"not a schematic") is None
    assert registered_kicad_kind("foo.kicad_pcb", b"(kicad_pcb (version 2024))") == "pcb"
    assert registered_kicad_kind("foo.kicad_sch", b"(kicad_sch (version 2024))") == "schematic"


def test_opt_in_required(monkeypatch):
    monkeypatch.delenv("HARDWARE_SPLICER_ENABLE_KICAD_SOURCE_CHECK", raising=False)
    assert not kicad_source_check_enabled()
    monkeypatch.setenv("HARDWARE_SPLICER_ENABLE_KICAD_SOURCE_CHECK", "1")
    assert kicad_source_check_enabled()


def test_unavailable_cli_does_not_claim_rule_check(monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    result = check_kicad_bytes("test.kicad_pcb", b"(kicad_pcb (version 2024))")
    assert result["status"] == "unavailable"
    assert result["check_executed"] is False
    assert result["release_authorized"] is False


def test_rejects_file_with_mismatched_format():
    with pytest.raises(ValueError, match="do not agree"):
        check_kicad_bytes("sample.kicad_sch", b"(kicad_pcb (version 2024))")
