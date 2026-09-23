from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.provider_review import evaluate_provider_review


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate an SPI provider review record without granting physical authority."
    )
    parser.add_argument("record", type=Path)
    parser.add_argument(
        "--campaign",
        type=Path,
        default=Path("hardware/reference_designs/spi_flash_adapter_v1/physical_proof_campaign_v1.json"),
    )
    parser.add_argument(
        "--require-eligible",
        action="store_true",
        help="Exit nonzero unless the record is eligible for a human fabrication decision.",
    )
    args = parser.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8"))
    campaign = json.loads(args.campaign.read_text(encoding="utf-8"))
    result = evaluate_provider_review(record, campaign)
    print(json.dumps(result, indent=2, sort_keys=True))

    if args.require_eligible and result["status"] != "ELIGIBLE_FOR_HUMAN_DECISION":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
