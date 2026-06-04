from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


def test_generate_sku_overrides_from_buy_list(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True, exist_ok=True)

    with (bundle / "BUY_LIST.locked.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "category",
            "item",
            "spec",
            "required_qty",
            "purchase_qty",
            "sku",
            "unit",
            "pack_size",
            "min_order_qty",
            "price_usd",
            "subtotal_usd",
            "url",
            "notes",
        ])
        w.writerow(["fastener", "M3 screws", "M3x12", 4, 1, "", "bag", 100, 1, 2.5, 2.5, "", ""])

    repo = Path(__file__).resolve().parents[1]
    subprocess.check_call(
        [
            "python3",
            "scripts/generate_sku_overrides.py",
            "--bundle-dir",
            str(bundle),
        ],
        cwd=repo,
    )

    out = bundle / "SKU_OVERRIDES.template.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "by_item_contains" in data
    assert "M3 screws" in data["by_item_contains"]


def test_generate_service_proposal(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    intake = tmp_path / "intake.json"
    intake.write_text(
        json.dumps(
            {
                "client_name": "ACME",
                "project_title": "Outdoor Sensor Node",
                "project_type": "verified_prototype",
                "environment": "outdoor",
                "deadline_days": 6,
                "needs": {
                    "pcb_validation": True,
                    "mechanical_design": True,
                    "pricing_lock": True,
                    "manufacturing_package": True,
                    "ongoing_support": True,
                },
                "constraints": {
                    "max_current_a": 3.0,
                    "envelope_w_mm": 200,
                },
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "proposal"
    subprocess.check_call(
        [
            "python3",
            "scripts/generate_service_proposal.py",
            "--intake",
            str(intake),
            "--out",
            str(out_dir),
        ],
        cwd=repo,
    )

    assert (out_dir / "PROPOSAL.md").exists()
    proposal = json.loads((out_dir / "PROPOSAL.json").read_text(encoding="utf-8"))
    assert proposal["total_price_usd"] > proposal["base_price_usd"]
