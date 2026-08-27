from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _cli():
    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_outer_engineer_run.py"
    spec = importlib.util.spec_from_file_location("outer_engineer_audit_cli", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_combined_cli_exit_codes_pass_review_block(tmp_path) -> None:
    cli = _cli()

    clean = tmp_path / "clean.json"
    clean.write_text(
        json.dumps(
            {
                "legacy_planner_architecture_authority": "ignored",
                "recommended_build_id": None,
                "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
                "physical_identity_authority": "declared_or_validated_exact_only",
                "resolved_modules": [],
                "module_overrides": {},
                "splice_plan": {"target": {}},
            }
        ),
        encoding="utf-8",
    )
    assert cli.main(["--salvage-package", str(clean)]) == 0

    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "legacy_planner_architecture_authority": "ignored",
                "recommended_build_id": None,
                "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
                "physical_identity_authority": "declared_or_validated_exact_only",
                "resolved_modules": [],
                "module_overrides": {},
                "splice_plan": {"target": {}},
                "bom_estimate": {"items": [{"module_id": "mosfet-irlz44n"}]},
            }
        ),
        encoding="utf-8",
    )
    assert cli.main(["--salvage-package", str(review)]) == 1

    blocked = tmp_path / "blocked.json"
    blocked.write_text(
        json.dumps(
            {
                "legacy_planner_architecture_authority": "ignored",
                "recommended_build_id": None,
                "build_selection": {"source": "unresolved", "legacy_fallback_used": False},
                "physical_identity_authority": "declared_or_validated_exact_only",
                "resolved_modules": [],
                "module_overrides": {},
                "splice_plan": {"target": {}},
                "firmware_scaffold": {"driver_module_id": "l298n"},
            }
        ),
        encoding="utf-8",
    )
    assert cli.main(["--salvage-package", str(blocked)]) == 2
