"""Compare the sealed design decisions with the manually adjudicated answer key."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEALED = "ba08a1c1984c06d7fb144d67540d963bcfba5e7a0db49391b690a83bd9f83163"


def classify(expected, actual):
    if expected not in {"yes", "no", "control"} or actual not in {"yes", "no", "unresolved"}:
        raise ValueError(f"Unknown verdict {expected!r}, {actual!r}")
    if expected == "control":
        return "control_unresolved" if actual == "unresolved" else "unsupported_control_decision"
    if actual == "unresolved":
        return "abstained"
    if actual == expected:
        return "correct_" + actual
    return "false_accept" if actual == "yes" else "false_reject"


def grade(sealed, key):
    if sha256(sealed).hexdigest() != SEALED:
        raise ValueError("Prediction bytes differ from the sealed run")
    predictions = json.loads(sealed)
    if predictions.keys() != key.keys():
        raise ValueError("Device list differs between predictions and answer key")
    counts = dict.fromkeys(("correct_yes", "correct_no", "abstained", "false_accept", "false_reject",
                            "control_unresolved", "unsupported_control_decision"), 0)
    results = {}
    for device, evidence in key.items():
        answers = evidence["answers"]
        cases = predictions[device]["cases"]
        if cases.keys() != answers.keys():
            raise ValueError(f"Case list differs for {device}")
        results[device] = {}
        for case, expected in answers.items():
            outcome = classify(expected, cases[case]["prediction"])
            results[device][case] = outcome
            counts[outcome] += 1
    return {"cases": results, "counts": counts, "predictions_sha256": SEALED}


if __name__ == "__main__":
    report = grade((HERE / "predictions.json").read_bytes(), json.loads((HERE / "answer_key.json").read_text()))
    print(json.dumps(report, indent=2, sort_keys=True))
