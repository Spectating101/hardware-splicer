from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "apps/circuit-ai/circuit-ai-frontend/components/workbench"
DENSE_SURFACES = [
    "constructor-dock.tsx",
    "proposal-queue-panel.tsx",
    "candidate-architecture-tray.tsx",
    "declared-placement-editor.tsx",
    "brep-render-mesh-control.tsx",
    "brep-surface-anchor-control.tsx",
    "brep-anchor-mating-control.tsx",
    "brep-mating-path-control.tsx",
    "brep-mating-path-refinement-control.tsx",
    "declared-clearance-checker.tsx",
    "declared-interface-access-editor.tsx",
]
MECHANICAL_SURFACES = [
    "declared-placement-editor.tsx",
    "brep-render-mesh-control.tsx",
    "brep-surface-anchor-control.tsx",
    "brep-anchor-mating-control.tsx",
    "brep-mating-path-control.tsx",
    "brep-mating-path-refinement-control.tsx",
    "declared-clearance-checker.tsx",
    "declared-interface-access-editor.tsx",
]


def test_dense_construct_surfaces_keep_an_eight_pixel_readability_floor() -> None:
    for filename in DENSE_SURFACES:
        text = (WORKBENCH / filename).read_text(encoding="utf-8")
        assert "text-[7px]" not in text, f"{filename} reintroduced sub-8px operational text"


def test_dense_mechanical_microcopy_keeps_a_readable_line_box() -> None:
    for filename in MECHANICAL_SURFACES:
        text = (WORKBENCH / filename).read_text(encoding="utf-8")
        assert "leading-3" not in text, f"{filename} reintroduced cramped 12px line-height microcopy"


def test_machine_workbench_keeps_one_compact_desktop_visual_checkpoint() -> None:
    spec = (
        ROOT
        / "apps/circuit-ai/circuit-ai-frontend/e2e/machine-workbench.spec.js"
    ).read_text(encoding="utf-8")
    assert spec.count("machine-workbench-constructor-compact.png") == 1
    assert spec.count("width: 1366, height: 768") == 1
    assert "compactCanvasBox.width).toBeGreaterThan(620)" in spec
    assert "compactCanvasBox.height).toBeGreaterThan(340)" in spec


def test_dense_brep_refinement_visual_evidence_is_kept_in_the_browser_gate() -> None:
    spec = (
        ROOT
        / "apps/circuit-ai/circuit-ai-frontend/e2e/machine-brep-mating-path-refinement.spec.js"
    ).read_text(encoding="utf-8")
    assert spec.count("machine-brep-mating-path-refinement-dense.png") == 1
    assert "testInfo.outputPath" in spec
