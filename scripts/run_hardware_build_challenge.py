#!/usr/bin/env python3
"""Run the independent first hardware-build submission gate."""
import argparse
import json
from pathlib import Path

from hardware_splicer.hardware_build_challenge import evaluate_build_submission


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = evaluate_build_submission(args.submission.resolve())
    body = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body)
    print(body)
    raise SystemExit(0 if result["automated_submission_checks_pass"] else 1)


if __name__ == "__main__":
    main()
