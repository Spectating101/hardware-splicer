#!/usr/bin/env python3
"""Run deterministic SPI virtual verification without model inference."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hardware_splicer.spi_virtual_verification import (
    apply_spi_fault,
    build_raw_document_v4_candidate,
    run_spi_fault_corpus,
    verify_spi_virtual_candidate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Hardware Splicer's zero-inference SPI virtual verifier."
    )
    parser.add_argument(
        "--case",
        choices=(
            "baseline",
            "corpus",
            "direct_3v3_drive",
            "reversed_miso",
            "grouped_direction_translator",
            "missing_absmax_provenance",
        ),
        default="corpus",
        help="Built-in verification case to execute.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    base = build_raw_document_v4_candidate()
    if args.case == "corpus":
        result = run_spi_fault_corpus(base)
        success = bool(result["all_expectations_pass"])
    else:
        candidate = base if args.case == "baseline" else apply_spi_fault(base, args.case)
        result = verify_spi_virtual_candidate(candidate)
        success = result["verification_status"] != "failed"

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
