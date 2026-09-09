#!/usr/bin/env python3
"""Plan frontier-model Hardware-Splicer experiments without provider network I/O."""

from __future__ import annotations

import argparse
import json

from hardware_splicer.cleanroom_unseen_spi_flash_experiment import (
    build_unseen_spi_flash_cases,
    validate_unseen_spi_flash_corpus,
)
from hardware_splicer.frontier_operator_experiment import (
    LIVE_CONFIRMATION,
    MODEL_SPECS,
    planning_manifest,
    validate_live_policy,
)


def _selected_case_ids(requested: list[str]) -> list[str]:
    all_ids = [case.case_id for case in build_unseen_spi_flash_cases()]
    if not requested:
        return all_ids
    unknown = sorted(set(requested).difference(all_ids))
    if unknown:
        raise SystemExit("unknown --case-id value(s): " + ", ".join(unknown))
    requested_set = set(requested)
    return [case_id for case_id in all_ids if case_id in requested_set]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a zero-network cost/transport plan for exploratory Astra or Fable "
            "Hardware-Splicer runs. This command never contacts a model provider."
        )
    )
    parser.add_argument("--model", choices=sorted(MODEL_SPECS), required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--estimated-input-tokens-per-case", type=int, default=40_000)
    parser.add_argument("--max-output-tokens-per-case", type=int, default=8_000)
    parser.add_argument(
        "--arm-live",
        action="store_true",
        help=(
            "Validate the explicit live-run policy and record an armed plan. Still "
            "performs no provider request."
        ),
    )
    parser.add_argument("--max-usd", type=float)
    parser.add_argument("--confirm-charges")
    parser.add_argument("--allow-multi-case", action="store_true")
    args = parser.parse_args()

    validation = validate_unseen_spi_flash_corpus()
    if not validation.get("pass"):
        raise SystemExit("refusing to plan against an invalid frozen corpus")
    case_ids = _selected_case_ids(args.case_id)

    manifest = planning_manifest(
        model=args.model,
        case_ids=case_ids,
        estimated_input_tokens_per_case=args.estimated_input_tokens_per_case,
        max_output_tokens_per_case=args.max_output_tokens_per_case,
    )
    manifest["frozen_corpus_validation_pass"] = True
    manifest["arm_live_requested"] = bool(args.arm_live)

    if args.arm_live:
        manifest["live_policy"] = validate_live_policy(
            model=args.model,
            case_count=len(case_ids),
            estimated_input_tokens_per_case=args.estimated_input_tokens_per_case,
            max_output_tokens_per_case=args.max_output_tokens_per_case,
            max_usd=args.max_usd,
            confirmation=args.confirm_charges,
            allow_multi_case=args.allow_multi_case,
        )
        manifest["armed_for_live_runner"] = True
    else:
        manifest["armed_for_live_runner"] = False

    manifest["network_io_performed"] = False
    manifest["provider_credentials_read"] = False
    manifest["live_execution_performed"] = False
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
