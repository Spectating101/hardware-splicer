from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from hardware_splicer.cleanroom_unseen_spi_flash_experiment import (
    build_unseen_spi_flash_cases,
)
from hardware_splicer.codex_astra_case import (
    build_case_input,
    build_codex_case_package,
    frozen_case_instructions,
    select_exact_case,
)


def _proof_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_external_mcp_agent_proof.py"
    spec = importlib.util.spec_from_file_location("hs_external_proof_protocol_for_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_codex_developer_instructions_are_byte_equal_to_frozen_runner() -> None:
    runner = _proof_runner()
    assert frozen_case_instructions() == runner._case_instructions()


@pytest.mark.parametrize(
    "case",
    list(build_unseen_spi_flash_cases()),
    ids=lambda case: case.case_id,
)
def test_codex_user_input_is_byte_equal_to_frozen_runner_for_every_case(case) -> None:
    runner = _proof_runner()
    project_id = "opaque-codex-experiment-project"
    assert build_case_input(case, project_id) == runner._case_input(case, project_id)


def test_model_visible_package_contains_no_outer_evaluator_fields() -> None:
    case = list(build_unseen_spi_flash_cases())[0]
    package = build_codex_case_package(
        case_id=case.case_id,
        experiment_project_id="opaque-project",
    )
    visible = package["model_visible"]
    outer = package["observer_only"]

    assert set(visible) == {"mission_text", "developer_instructions"}
    assert outer["case_id"] == case.case_id
    assert outer["equivalence_group"] == case.equivalence_group
    assert outer["perturbation_kind"] == case.perturbation_kind
    assert outer["outer_labels_visible_to_model"] is False
    assert "case_metadata" not in visible
    assert "equivalence_group" not in visible
    assert "perturbation_kind" not in visible


def test_case_package_preserves_exact_snapshot_for_offline_audit() -> None:
    case = list(build_unseen_spi_flash_cases())[0]
    package = build_codex_case_package(
        case_id=case.case_id,
        experiment_project_id="opaque-project",
    )
    assert package["observer_only"]["snapshot"] == dict(case.snapshot)
    assert package["observer_only"]["snapshot_sha256"].startswith("sha256:")
    assert package["observer_only"]["input_sha256"].startswith("sha256:")
    assert package["observer_only"]["instructions_sha256"].startswith("sha256:")


def test_unknown_case_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown or non-unique"):
        select_exact_case("does-not-exist")
