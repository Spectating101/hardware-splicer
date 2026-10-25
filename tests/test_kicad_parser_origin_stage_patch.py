"""Offline contract tests for the pinned upstream parser-stage patcher."""
from pathlib import Path
import importlib.util
import pytest

PATCH = Path(__file__).resolve().parents[1] / "examples/integrations/kicad-circuit-json/patch_upstream_origin_stage.py"
spec = importlib.util.spec_from_file_location("hs_origin_patcher", PATCH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

STAGE = """
    // Create schematic_component
    const uuid = symbol.uuid
    const componentId = inserted.schematic_component_id
        componentId,
        cjPos,
      )
    componentCenter: { x: number; y: number },
  ) {
      const sideOfComponent: "top" | "bottom" | "left" | "right" =
"""
CONVERTER = """
  getOutputString() {
"""

def make_tree(tmp_path, stage=STAGE, converter=CONVERTER):
    a = tmp_path / module.STAGE
    b = tmp_path / module.CONVERTER
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_text(stage)
    b.write_text(converter)
    return a, b

def test_patch_captures_native_uuid_at_stage_and_all_inserted_port_ids(tmp_path):
    a, b = make_tree(tmp_path)
    hashes = module.patch_checkout(tmp_path)
    assert len(hashes) == 2
    assert "native_kicad_symbol_uuid: symbol.uuid" in a.read_text()
    assert "origin.source_port_ids.push(sourcePort.source_port_id)" in a.read_text()
    assert "getNativeOriginSidecar()" in b.read_text()
    assert "sheet_hierarchy_verified: false" in b.read_text()
    assert hashes[0]["before_sha256"] != hashes[0]["after_sha256"]

def test_unrecognized_upstream_stage_fails_without_partial_write(tmp_path):
    a, b = make_tree(tmp_path, stage=STAGE.replace("const uuid = symbol.uuid", "const uuid = undefined"))
    old = a.read_text()
    with pytest.raises(ValueError, match="signature changed"):
        module.patch_checkout(tmp_path)
    assert a.read_text() == old
    assert b.read_text() == CONVERTER

def test_double_apply_refuses_duplicate_instrumentation(tmp_path):
    a, b = make_tree(tmp_path)
    module.patch_checkout(tmp_path)
    with pytest.raises(ValueError, match="signature changed"):
        module.patch_checkout(tmp_path)
