#!/usr/bin/env python3
"""Run the bounded 0x9f transaction for a physically authorized SPI campaign."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.spi_remote_fct import (  # noqa: E402
    MAX_CAMPAIGN_CLOCK_HZ,
    PyFtdiTransport,
    SpiDevTransport,
    build_dry_run_plan,
    canonical_json,
    run_read_only_jedec_id,
    validate_physical_execution_context,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("pyftdi", "spidev"))
    parser.add_argument("--frequency-hz", type=int, default=1_000_000)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--ftdi-url")
    parser.add_argument("--chip-select", type=int, default=0)
    parser.add_argument("--spidev-bus", type=int)
    parser.add_argument("--spidev-device", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--campaign-sha256")
    parser.add_argument("--test-article-id")
    parser.add_argument("--operator-id")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="open the specified physical transport; without this flag only a dry-run plan is emitted",
    )
    parser.add_argument(
        "--operator-confirm-bench-authorized",
        action="store_true",
        help="confirm that the revision-bound BENCH_POWER authorization exists",
    )
    args = parser.parse_args()

    if not 1 <= args.frequency_hz <= MAX_CAMPAIGN_CLOCK_HZ:
        parser.error(f"frequency must be 1..{MAX_CAMPAIGN_CLOCK_HZ} Hz")
    expected_id = bytes.fromhex("ef6018")

    try:
        result = build_dry_run_plan(
            frequency_hz=args.frequency_hz,
            trials=args.trials,
            expected_id=expected_id,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if not args.execute:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as output_stream:
                output_stream.write(canonical_json(result))
        except FileExistsError:
            parser.error("--output already exists; refusing to overwrite evidence")
        print(canonical_json(result), end="")
        return 0

    if not args.operator_confirm_bench_authorized:
        parser.error("--operator-confirm-bench-authorized is required with --execute")
    if not args.transport:
        parser.error("--transport is required with --execute")
    if not args.campaign_sha256:
        parser.error("--campaign-sha256 is required with --execute")
    if not args.test_article_id:
        parser.error("--test-article-id is required with --execute")
    if not args.operator_id:
        parser.error("--operator-id is required with --execute")
    if args.frequency_hz == MAX_CAMPAIGN_CLOCK_HZ and args.trials < 10:
        parser.error("5 MHz physical campaign execution requires at least 10 trials")
    transport = None
    runner_owns_transport = False
    try:
        validate_physical_execution_context(
            campaign_sha256=args.campaign_sha256,
            test_article_id=args.test_article_id,
            operator_id=args.operator_id,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_stream = args.output.open("x", encoding="utf-8")
    except FileExistsError:
        parser.error("--output already exists; refusing to overwrite evidence")

    def append_event(event: dict) -> None:
        output_stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        output_stream.flush()
        os.fsync(output_stream.fileno())

    append_event(
        {
            "schema_version": "hardware_splicer.spi_read_only_jedec_id_event.v1",
            "event": "output_reserved_before_transport_open",
            "campaign_sha256": args.campaign_sha256,
            "test_article_id": args.test_article_id,
            "operator_id": args.operator_id,
            "physical_authority_granted": False,
            "authority_effect": "none",
        }
    )
    try:
        if args.transport == "pyftdi":
            if not args.ftdi_url:
                parser.error("--ftdi-url is required for pyftdi")
            transport = PyFtdiTransport(
                args.ftdi_url,
                args.frequency_hz,
                chip_select=args.chip_select,
            )
        else:
            if args.spidev_bus is None or args.spidev_device is None:
                parser.error("--spidev-bus and --spidev-device are required for spidev")
            transport = SpiDevTransport(
                args.spidev_bus,
                args.spidev_device,
                args.frequency_hz,
            )

        print(
            "Host transport is configured with no SPI transfer issued. Keep JP1 open until "
            "rail and CS checks pass; then bridge JP1 and type ENABLED to continue.",
            file=sys.stderr,
        )
        try:
            enable_token = input().strip()
        except (EOFError, KeyboardInterrupt):
            append_event(
                {
                    "schema_version": "hardware_splicer.spi_read_only_jedec_id_event.v1",
                    "event": "operator_enable_cancelled",
                    "physical_authority_granted": False,
                    "authority_effect": "none",
                }
            )
            parser.error("operator enable confirmation was not received; no transfer issued")
        if enable_token != "ENABLED":
            append_event(
                {
                    "schema_version": "hardware_splicer.spi_read_only_jedec_id_event.v1",
                    "event": "operator_enable_rejected",
                    "physical_authority_granted": False,
                    "authority_effect": "none",
                }
            )
            parser.error("operator must type exactly ENABLED; no transfer issued")

        runner_owns_transport = True
        result = run_read_only_jedec_id(
            transport,
            frequency_hz=args.frequency_hz,
            trials=args.trials,
            expected_id=expected_id,
            capture_origin="physical_test_article",
            campaign_sha256=args.campaign_sha256,
            test_article_id=args.test_article_id,
            operator_id=args.operator_id,
            progress=lambda transaction: append_event(
                {
                    "schema_version": "hardware_splicer.spi_read_only_jedec_id_event.v1",
                    "event": "transaction_attempt",
                    "transaction": transaction,
                    "physical_authority_granted": False,
                    "authority_effect": "none",
                }
            ),
        )
        append_event(
            {
                "schema_version": "hardware_splicer.spi_read_only_jedec_id_event.v1",
                "event": "final_result",
                "result": result,
                "physical_authority_granted": False,
                "authority_effect": "none",
            }
        )
    except Exception as exc:
        append_event(
            {
                "schema_version": "hardware_splicer.spi_read_only_jedec_id_event.v1",
                "event": "host_execution_error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "physical_authority_granted": False,
                "authority_effect": "none",
            }
        )
        print(f"host execution failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        if transport is not None and not runner_owns_transport:
            try:
                transport.close()
            except Exception as exc:
                append_event(
                    {
                        "schema_version": "hardware_splicer.spi_read_only_jedec_id_event.v1",
                        "event": "transport_close_error",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "physical_authority_granted": False,
                        "authority_effect": "none",
                    }
                )
        output_stream.close()
    print(canonical_json(result), end="")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
