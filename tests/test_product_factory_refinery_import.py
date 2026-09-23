from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "experiments" / "product_factory" / "import_refinery_seed.py"
SPEC = importlib.util.spec_from_file_location("pf_importer", IMPORTER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FIXTURE = json.loads((ROOT / "experiments" / "product_factory" / "fixtures" / "refinery_seed_acceptance.json").read_text())


def test_refinery_seed_opens_engineering_not_physical_authority() -> None:
    run = MODULE.import_seed(FIXTURE, run_id="PF-999", opened_at="2026-09-24")
    assert run["stages"][0]["state"] == "PASS_REFINERY_REVIEWED_MARKET"
    assert run["stages"][1]["state"] == "PASS_REFINERY_COMMERCIAL_GATE"
    assert run["stages"][2]["state"] == "READY_FOR_HS_PRODUCT_CONTRACT"
    assert run["stages"][3]["state"] == "BLOCKED_ON_PRODUCT_CONTRACT"
    assert run["authority"]["design_work_authorized"] is True
    assert run["authority"]["fabrication_ready"] is False
    assert run["authority"]["physical_authority_granted"] is False
    assert run["authority"]["commercial_superiority"] == "UNPROVEN"


def test_refinery_seed_cannot_smuggle_fabrication_authority() -> None:
    seed = json.loads(json.dumps(FIXTURE))
    seed["authority"]["fabrication_authorized"] = True
    with pytest.raises(ValueError, match="may not authorize fabrication"):
        MODULE.import_seed(seed, run_id="PF-999", opened_at="2026-09-24")


def test_refinery_seed_must_still_clear_its_margin_floor() -> None:
    seed = json.loads(json.dumps(FIXTURE))
    seed["economics"]["landed_cogs_ceiling_usd"] = 60
    with pytest.raises(ValueError, match="margin floor"):
        MODULE.import_seed(seed, run_id="PF-999", opened_at="2026-09-24")


def test_refinery_seed_requires_supported_schema() -> None:
    seed = json.loads(json.dumps(FIXTURE))
    seed["schema"] = "unknown"
    with pytest.raises(ValueError, match="unsupported"):
        MODULE.import_seed(seed, run_id="PF-999", opened_at="2026-09-24")
