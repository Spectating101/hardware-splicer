"""Run the fictional declared examples through the production evaluator."""
import json
from pathlib import Path
import sys


DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY.parents[1] / "src"))

from hardware_splicer.part_substitution import evaluate_substitution  # noqa: E402


def main():
    index = json.loads((DIRECTORY / "fixture-index.json").read_text())
    outcomes = []
    for entry in index["examples"]:
        report = evaluate_substitution(json.loads((DIRECTORY / entry["file"]).read_text()))
        outcomes.append({"example": entry["file"], "status": report["status"],
                         "expected_status": entry["expected_status"],
                         "findings": [{"code": row["code"], "status": row["status"],
                                       "part_ids": row["part_ids"]}
                                      for row in report["checks"] if row["status"] != "pass"],
                         "required_adaptations": [{"kind": row["kind"], "part_ids": row["part_ids"]}
                                                  for row in report["required_adaptations"]],
                         "scenarios": [{"scenario_id": row["scenario_id"],
                                        "before_total_power_w": row["before"]["total_power_w"],
                                        "after_total_power_w": row["after"]["total_power_w"],
                                        "after_runtime_by_source": row["after"]["runtime_by_source"]}
                                       for row in report["scenarios"]]})
    print(json.dumps({"evidence_class": index["evidence_class"],
                      "physical_validation_performed": False, "outcomes": outcomes}, indent=2))
    return 0 if all(row["status"] == row["expected_status"] for row in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
