"""Two real supplier PDFs -> source-verified claims -> mechanical+electrical+material screen.

The test electrical and geometrical inputs are intentionally synthetic; this
is not a validated enclosure or safety/suitability assessment.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from registered_pdf_end_to_end import run
from three_layer_enclosure_v1 import request_body


def main(source_dir: Path) -> dict:
    return run(
        source_dir,
        assembly_fixture=lambda evidence: request_body(
            "candidate-pc_blend", source_evidence=evidence
        ),
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: registered_three_layer_end_to_end.py <offline-prusa-source-directory>")
    result = main(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
    if result["result"] != "pass" or not result["three_layer_assembly"]:
        raise SystemExit(1)
