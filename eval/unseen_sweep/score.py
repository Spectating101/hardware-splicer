"""Score the sealed run against the withheld Sweep2.x compatibility table."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PREDICTIONS_SHA = "05ec4afe055ace97f6bad7ef9d9ea100599519de2bdd29b4f51a4ad798f53d42"
README_SHA = "e84da2800817f7b439e68306311c8b9fd4c3095565fe0e3d4f5c78b331cba1f7"
COLUMNS = {"Choc V1": ["Choc V1"], "Choc V2": ["Choc V2"], "Choc Mini": ["Choc Mini"],
           "MX & Alps": ["Cherry MX", "Alps / Matias"]}


def read_verified(path, digest):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"Evidence hash mismatch for {path.name}")
    return data.decode()


def table_row(text, label):
    rows = [line.strip().strip("|").split("|") for line in text.splitlines() if line.startswith("|")]
    row, = [row for row in rows if row[0].strip() == label]
    return [cell.strip() for cell in row]


def score(readme):
    prediction = json.loads(read_verified(HERE / "predictions.json", PREDICTIONS_SHA))
    text = read_verified(readme, README_SHA)
    table = dict(zip(table_row(text, "Device"), table_row(text, "Sweep2.x"), strict=True))
    counts = Counter()
    results = {}
    for column, names in COLUMNS.items():
        expected = {"✔": "accept", "": "reject"}[table[column]]
        for name in names:
            actual = prediction["swaps"][name]["prediction"]
            if actual == "unresolved":
                result = "abstained_on_known"
            elif actual == expected:
                result = "correct_" + actual
            else:
                result = "false_" + actual
            counts[result] += 1
            results[name] = {"expected": expected, "predicted": actual, "result": result, "oracle_column": column}
    (key_count,) = re.findall(r"^\* (\d+) switches of a compatible type", text, re.MULTILINE)
    assigned_keys = set(prediction["switch_to_controller"])
    if sum(prediction["keys_by_controller"].values()) != len(assigned_keys):
        raise ValueError("Controller counts do not reconcile with key assignments")
    original = prediction["original_extractor_key_refs"]
    return {
        "prediction_commit": "6b56c2f4", "predictions_sha256": PREDICTIONS_SHA, "oracle_sha256": README_SHA,
        "oracle_url": "https://github.com/davidphilipbarr/Sweep/blob/8ba72a256d627567660ecc0b6f51bb18fa8badb5/README.md",
        "source_outcome": "Maintainer-declared PCB support for the Sweep2.x family",
        "cases": results, "published_columns": len(COLUMNS),
        "counts": {key: counts[key] for key in ("correct_accept", "correct_reject", "false_accept", "false_reject", "abstained_on_known")},
        "missing_information_control": prediction["swaps"]["unmarked loose switch"]["prediction"],
        "published_key_quantity": int(key_count), "reconstructed_quantity": len(assigned_keys),
        "published_quantity_matches": len(assigned_keys) == int(key_count),
        "baseline_extractor": {"reported": len(original), "true_key_refs": len(set(original) & assigned_keys),
                               "missed_keys": len(assigned_keys - set(original))},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream_readme", type=Path)
    print(json.dumps(score(parser.parse_args().upstream_readme), indent=2, sort_keys=True))
