#!/usr/bin/env python3
"""Execute bounded synthetic observations with a live replaceable operator."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hardware_splicer.adaptive_diagnosis import run_adaptive_case
from hardware_splicer.operator_review_bridge import copilot_text_operator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-id', default='rover_brownout')
    parser.add_argument('--hidden-fault', default='connector_drop')
    parser.add_argument('--max-tests', type=int, default=2)
    parser.add_argument('--output', default='/tmp/hs_adaptive_diagnosis.json')
    args = parser.parse_args()
    cases = json.loads((ROOT / 'eval/hypothesis_discrimination/cases.json').read_text())
    case = next((r for r in cases if r['case_id'] == args.case_id), None)
    if case is None:
        parser.error('unknown scenario')
    result = run_adaptive_case(case, hidden_fault=args.hidden_fault,
                               operator=copilot_text_operator, max_tests=args.max_tests)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['correct_and_calibrated'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
