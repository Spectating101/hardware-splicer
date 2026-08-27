from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_cli_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_model_first_truth.py"
    spec = importlib.util.spec_from_file_location("audit_model_first_truth_cli", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_returns_zero_for_clean_capture(tmp_path, capsys) -> None:
    cli = _load_cli_module()
    salvage = tmp_path / "salvage.json"
    salvage.write_text(
        json.dumps(
            {
                "legacy_planner_architecture_authority": "ignored",
                "recommended_build_id": None,
                "build_selection": {
                    "source": "unresolved",
                    "legacy_fallback_used": False,
                    "authority_effect": "none",
                },
                "physical_identity_authority": "declared_or_validated_exact_only",
                "salvage_resolution": {
                    "physical_identity_boundary": {
                        "functional_similarity_is_identity": False,
                        "authority_effect": "none",
                    }
                },
                "resolved_modules": [
                    {
                        "instance_id": "donor-driver",
                        "module_id": None,
                        "role": "drv",
                        "source": "donor_functional_salvage_external",
                        "identity_status": "external_unresolved",
                        "external_capability_only": True,
                    }
                ],
                "module_overrides": {},
                "splice_plan": {"target": {}},
                "power_on_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "audit.json"

    code = cli.main(["--salvage-package", str(salvage), "--out", str(out), "--pretty"])

    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["violation_count"] == 0
    stdout = capsys.readouterr().out
    assert '"status": "pass"' in stdout


def test_cli_returns_two_for_legacy_standin_capture(tmp_path) -> None:
    cli = _load_cli_module()
    salvage = tmp_path / "bad-salvage.json"
    salvage.write_text(
        json.dumps(
            {
                "legacy_planner_architecture_authority": "compatibility_only",
                "recommended_build_id": None,
                "build_selection": {
                    "source": "legacy_keyword",
                    "legacy_fallback_used": True,
                },
                "physical_identity_authority": "legacy_compatibility",
                "resolved_modules": [
                    {
                        "instance_id": "unknown-hbridge",
                        "module_id": "l298n",
                        "role": "drv",
                        "source": "donor_functional_salvage_external",
                        "identity_status": "external_unresolved",
                        "external_capability_only": True,
                    }
                ],
                "module_overrides": {"drv": "l298n"},
                "splice_plan": {"target": {}},
                "motion_authorized": True,
            }
        ),
        encoding="utf-8",
    )

    code = cli.main(["--salvage-package", str(salvage)])

    assert code == 2
