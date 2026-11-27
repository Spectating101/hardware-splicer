"""The back-test records keep their sources and the ledger never loses a prediction's method or status."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "examples" / "backtests"


def test_every_backtest_names_its_data_and_what_changed():
    for path in HERE.glob("*_2026*.json"):
        rec = json.loads(path.read_text())
        assert rec["schema"] == "hardware_splicer.backtest.v1" and rec["question"]
        assert rec.get("data") or rec.get("evidence"), path.name
        assert rec.get("result"), path.name


def test_every_open_prediction_says_how_to_measure_it():
    ledger = json.loads((HERE / "PREDICTIONS.json").read_text())
    ids = [p["id"] for p in ledger["predictions"]]
    assert len(ids) == len(set(ids))
    for p in ledger["predictions"]:
        assert "predicted" in p and p["status"]
        if p["status"] == "open":
            assert p["how_to_measure"]
        else:
            assert p["measured"]
