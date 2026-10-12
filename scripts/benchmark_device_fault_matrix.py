#!/usr/bin/env python3
"""Mutation benchmark for the generated application's host fault matrix.

Seeds realistic bugs into the generated ``src/app_core.h`` and measures which
detector notices each one:

* ``smoke``    - ``boot_ok`` only: the application boots and prints an OK reading.
* ``healthy``  - every scenario on an unfaulted bus (``boot_ok``,
                 ``default_address_binding``, ``read_period``).
* ``matrix``   - all 15 host scenarios, including injected faults.

``serial_grammar`` re-runs other scenarios, so it is never counted as a healthy-bus
detector. A surviving mutant is not automatically a test gap: each survivor is either
reviewed as behaviourally equivalent (with a written reason) or reported as a gap.

This measures how well the *host model's* tests catch application-logic bugs. It does
not measure silicon, timing, the Adafruit libraries or physical correctness, and it
never changes any authority flag.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SCHEMA = "hardware_splicer.device_fault_matrix_benchmark.v1"
SMOKE = frozenset({"boot_ok"})
HEALTHY = frozenset({"boot_ok", "default_address_binding", "read_period"})
CLAIM_BOUNDARY = (
    "Mutation benchmark of host application-logic tests against a modelled bus. It is not silicon, "
    "ESP32 timing, vendor-library behaviour or electrical evidence, and it authorizes nothing."
)


@dataclass(frozen=True)
class Mutant:
    id: str
    bug_class: str
    story: str
    old: str
    new: str
    # Set only after a written review of a survivor; never to make a score look better.
    equivalent_reason: str = ""


def _m(id, bug_class, story, old, new, equivalent_reason=""):
    return Mutant(id, bug_class, story, old, new, equivalent_reason)


MUTANTS: tuple[Mutant, ...] = (
    # --- fault thresholds and timing constants -------------------------------------------------
    _m("fail_threshold_off_by_one", "threshold", "needs four failed reads, not three, before declaring a read fault",
       "if (consecutive_fails_ >= kReadFailThreshold) {", "if (consecutive_fails_ > kReadFailThreshold) {"),
    _m("fail_threshold_too_eager", "threshold", "declares a read fault after two failures",
       "static constexpr int kReadFailThreshold = 3;", "static constexpr int kReadFailThreshold = 2;"),
    _m("read_period_wrong", "timing", "reads every 2.5 s instead of every 2 s",
       "static constexpr uint32_t kReadPeriodMs = 2000;", "static constexpr uint32_t kReadPeriodMs = 2500;"),
    _m("backoff_initial_wrong", "timing", "first retry waits 2 s instead of 1 s",
       "static constexpr uint32_t kBackoffInitialMs = 1000;", "static constexpr uint32_t kBackoffInitialMs = 2000;"),
    _m("backoff_cap_unbounded", "timing", "retry backoff cap is effectively removed",
       "static constexpr uint32_t kBackoffCapMs = 30000;", "static constexpr uint32_t kBackoffCapMs = 3000000;"),
    _m("backoff_never_grows_when_missing", "timing", "a missing sensor is retried at a constant interval",
       "                    return;\n                }\n                backoff_ms_ *= 2;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (state_ == AppState::FAULT_SENSOR_READ) {",
       "                    return;\n                }\n                backoff_ms_ *= 1;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (state_ == AppState::FAULT_SENSOR_READ) {"),
    _m("naive_clock_rollover", "timing", "elapsed time clamps to zero when the 32-bit millisecond counter wraps",
       "    const uint32_t elapsed = now - then;\n    return elapsed;", "    return now >= then ? now - then : 0;"),
    # --- plausibility ---------------------------------------------------------------------------
    _m("nan_not_rejected", "plausibility", "NaN readings are accepted as real data",
       "    if (std::isnan(reading.temp_c) || std::isnan(reading.hum_pct) || std::isnan(reading.pres_hpa)) return false;\n", ""),
    _m("humidity_upper_bound_removed", "plausibility", "humidity above 100 % is accepted",
       " || reading.hum_pct > kHumMaxPct", ""),
    _m("pressure_upper_bound_removed", "plausibility", "pressure above 1100 hPa is accepted",
       " || reading.pres_hpa > kPresMaxHpa", ""),
    _m("temperature_range_widened", "plausibility", "temperature up to 125 C is accepted",
       "static constexpr float kTempMaxC = 85.0f;", "static constexpr float kTempMaxC = 125.0f;"),
    _m("pressure_floor_removed", "plausibility", "pressure of 0 hPa is accepted",
       "static constexpr float kPresMinHpa = 300.0f;", "static constexpr float kPresMinHpa = 0.0f;"),
    _m("plausibility_skipped_on_read", "plausibility", "a successful bus read is trusted without a range check",
       "const bool ok = hal_.sensor_read(reading) && reading_is_plausible(reading);",
       "const bool ok = hal_.sensor_read(reading) && (reading_is_plausible(reading) || true);"),
    # --- identity and addressing ----------------------------------------------------------------
    _m("first_matching_address_wins", "addressing", "stops probing at the first chip that answers, so a second device is never noticed",
       "                hits += 1;\n                found = addr;\n            }", "                hits += 1;\n                found = addr;\n                break;\n            }"),
    _m("failed_rebind_ignored", "addressing", "a failed rebind to the matched address is ignored",
       "            if (!hal_.sensor_begin(found)) return 0;\n", "            (void)hal_.sensor_begin(found);\n"),
    _m("no_rebind_after_probe", "addressing", "driver is left bound to the last address probed",
       "            if (!hal_.sensor_begin(found)) return 0;\n", ""),
    _m("boot_ignores_ambiguity", "addressing", "two answering chips at boot are not treated as ambiguous",
       "        const int hits = probe_sensor();\n        if (hits > 1) {\n            enter_fault(now, AppState::FAULT_AMBIGUOUS_ADDRESS, \"AMBIGUOUS ADDR\");\n            return;\n        }\n        if (hits == 0) {",
       "        const int hits = probe_sensor();\n        if (hits > 99) {\n            enter_fault(now, AppState::FAULT_AMBIGUOUS_ADDRESS, \"AMBIGUOUS ADDR\");\n            return;\n        }\n        if (hits == 0) {"),
    _m("ambiguity_not_latched", "addressing", "after an ambiguous-address fault the application keeps reading",
       "        if (state_ == AppState::FAULT_AMBIGUOUS_ADDRESS) {\n            return;\n        }\n", ""),
    _m("display_first_address_only", "addressing", "only the first declared display address is tried",
       "for (size_t i = 0; i < n_display_; ++i) {\n            const uint8_t addr = display_addrs_[i];",
       "for (size_t i = 0; i < n_display_ && i < 1; ++i) {\n            const uint8_t addr = display_addrs_[i];"),
    # --- display behaviour ----------------------------------------------------------------------
    _m("display_missing_never_logged", "display", "an absent declared display is never reported",
       "if (display_declared_ && !display_ok_ && !display_missing_logged_) {", "if (false) {"),
    _m("display_missing_log_repeats", "display", "the missing-display line repeats on every loop",
       "            display_missing_logged_ = true;\n", ""),
    _m("writes_to_absent_display", "display", "draws readings even when no display answered",
       "        if (!display_ok_) {\n            return;\n        }\n        if (!have_last_) {",
       "        if (!have_last_) {"),
    _m("fault_drawn_without_display", "display", "draws fault text even when no display answered",
       "        if (display_ok_) {\n            hal_.display_show(message, \"\", \"\", \"\");", "        if (true) {\n            hal_.display_show(message, \"\", \"\", \"\");"),
    _m("stale_headlined_as_ok", "display", "a stale reading is shown under an OK headline",
       "show_reading(\"STATE STALE\");", "show_reading(\"STATE OK\");"),
    _m("last_reading_not_kept", "display", "the last good reading is never remembered, so stale shows no data",
       "        have_last_ = true;\n", ""),
    # --- recovery and state machine -------------------------------------------------------------
    _m("recovery_from_missing_not_announced", "recovery", "a sensor that reappears is not announced as recovered",
       "                if (hits == 1) {\n                    hal_.log(\"RECOVERED\");", "                if (hits == 1) {"),
    _m("read_fault_recovery_not_announced", "recovery", "a read fault that clears is not announced as recovered",
       "        if (was_fault) {\n            hal_.log(\"RECOVERED\");\n        }", "        if (was_fault && false) {\n            hal_.log(\"RECOVERED\");\n        }"),
    _m("failure_count_not_cleared_on_success", "recovery", "isolated failures accumulate across good reads and eventually fault",
       "        consecutive_fails_ = 0;\n        last_ = reading;", "        last_ = reading;"),
    _m("stale_not_logged", "recovery", "the first failed read is not reported as STALE",
       "            log_state(now, AppState::STALE);\n", ""),
    _m("no_bus_recovery_on_fault_entry", "recovery", "entering a read fault does not try to recover the bus",
       "                    log_state(now, AppState::FAULT_SENSOR_READ);\n                    (void)hal_.bus_recover();",
       "                    log_state(now, AppState::FAULT_SENSOR_READ);"),
    _m("no_bus_recovery_on_retry", "recovery", "retries from a read fault never recover the bus",
       "                last_action_ms_ = now;\n                (void)hal_.bus_recover();\n                const int hits = probe_sensor();",
       "                last_action_ms_ = now;\n                const int hits = probe_sensor();"),
    _m("no_rebind_on_fault_entry", "recovery", "entering a read fault does not rebind the driver",
       "                    (void)hal_.sensor_begin(sensor_addr_);\n", ""),
    _m("read_fault_backoff_not_reset", "recovery", "backoff keeps its grown value after a read fault clears, so the next fault starts slow",
       "                    if (state_ == AppState::OK) {\n                        backoff_ms_ = kBackoffInitialMs;\n                        return;",
       "                    if (state_ == AppState::OK) {\n                        return;",
       "backoff_ms_ is read only inside the two fault branches, and every entry into FAULT_SENSOR_READ "
       "resets it in take_reading, so also resetting it at recovery is unobservable."),
    # --- output grammar -------------------------------------------------------------------------
    _m("state_line_grammar_drift", "grammar", "the state line separator changes from '=' to ': '",
       "\"T=%u STATE=%s\"", "\"T=%u STATE: %s\""),
    _m("boot_line_addresses_swapped", "grammar", "the BOOT line reports the display address as the sensor's",
       "sensor_addr_, display_addr_);\n        } else {", "display_addr_, sensor_addr_);\n        } else {"),
    # --- reviewed equivalents (kept so the benchmark proves it handles them honestly) ------------
    _m("missing_recovery_clears_count_redundant", "recovery", "drops a counter reset that take_reading repeats immediately",
       "                    state_ = AppState::OK;\n                    consecutive_fails_ = 0;\n                    backoff_ms_ = kBackoffInitialMs;\n                    take_reading(now);",
       "                    state_ = AppState::OK;\n                    backoff_ms_ = kBackoffInitialMs;\n                    take_reading(now);",
       "FAULT_SENSOR_MISSING is reachable only from boot(), where consecutive_fails_ is still 0, and "
       "take_reading() clears it on the next success; the extra reset cannot change any output."),
)


# Written after the harness was strengthened and never used to tune it, so they estimate how well
# the matrix generalises beyond the mutants it was tuned against.
HELDOUT_MUTANTS: tuple[Mutant, ...] = (
    _m("heldout_sensor_addr_not_recorded", "addressing", "the matched address is never stored, so BOOT reports 0x00",
       "            sensor_addr_ = found;\n", ""),
    _m("heldout_read_fault_backoff_linear", "timing", "read-fault retry backoff grows by a constant instead of doubling",
       "                backoff_ms_ *= 2;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (wrap_elapsed(now, last_action_ms_) >= kReadPeriodMs) {",
       "                backoff_ms_ += 1000;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (wrap_elapsed(now, last_action_ms_) >= kReadPeriodMs) {"),
    _m("heldout_period_boundary_exclusive", "timing", "a reading is taken only strictly after the period, so the period edge is missed",
       "if (wrap_elapsed(now, last_action_ms_) >= kReadPeriodMs) {", "if (wrap_elapsed(now, last_action_ms_) > kReadPeriodMs) {"),
    _m("heldout_missing_retry_boundary_exclusive", "timing", "a missing sensor is retried only strictly after its backoff",
       "        if (state_ == AppState::FAULT_SENSOR_MISSING) {\n            if (wrap_elapsed(now, last_action_ms_) >= backoff_ms_) {",
       "        if (state_ == AppState::FAULT_SENSOR_MISSING) {\n            if (wrap_elapsed(now, last_action_ms_) > backoff_ms_) {"),
    _m("heldout_temperature_floor_removed", "plausibility", "readings below -40 C are accepted",
       "reading.temp_c < kTempMinC || ", ""),
    _m("heldout_humidity_floor_removed", "plausibility", "negative humidity is accepted",
       "reading.hum_pct < kHumMinPct || ", ""),
    _m("heldout_recovery_skips_boot_line", "recovery", "a sensor that reappears is not re-identified in the BOOT line",
       "                    hal_.log(\"RECOVERED\");\n                    log_boot();", "                    hal_.log(\"RECOVERED\");"),
    _m("heldout_display_never_probed", "display", "the display is never probed, so it is always reported missing",
       "        probe_display();\n        const int hits = probe_sensor();", "        const int hits = probe_sensor();"),
    _m("heldout_pressure_unit_wrong", "display", "the display shows pressure in Pa while labelled hPa elsewhere",
       "\"%.1f hPa\"", "\"%.1f Pa\""),
    _m("heldout_missing_backoff_cap_removed", "timing", "the 30 s cap is not applied to a missing sensor's backoff",
       "                backoff_ms_ *= 2;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (state_ == AppState::FAULT_SENSOR_READ) {",
       "                backoff_ms_ *= 2;\n            }\n            return;\n        }\n        if (state_ == AppState::FAULT_SENSOR_READ) {"),
    _m("heldout_stale_state_not_tracked", "recovery", "the STALE state is logged but not tracked internally",
       "            state_ = AppState::STALE;\n", "",
       "STALE is never read back by loop_once or take_reading: only FAULT_* and OK are branched on, and "
       "log_state takes the state as an argument, so tracking it internally is unobservable."),
    _m("heldout_boot_clock_not_recorded", "timing", "the boot time is not recorded as the first action time",
       "            booted_ = true;\n            last_action_ms_ = now;\n", "            booted_ = true;\n"),
)


def apply_mutant(source: str, mutant: Mutant) -> str:
    """Return mutated source; refuse a mutant that matches zero or several places."""
    count = source.count(mutant.old)
    if count != 1:
        raise ValueError(f"mutant {mutant.id} matched {count} places, expected exactly 1")
    mutated = source.replace(mutant.old, mutant.new, 1)
    if mutated == source:
        raise ValueError(f"mutant {mutant.id} did not change the source")
    return mutated


def build_package(directory: Path) -> Path:
    from hardware_splicer.device_application import build_device_application
    from hardware_splicer.device_plan import example_specs

    _metadata, archive = build_device_application(example_specs()["esp32_oled_bme280_usb"])
    zip_path = directory / "application.zip"
    zip_path.write_bytes(archive)
    project = directory / "baseline"
    with zipfile.ZipFile(zip_path) as bundle:
        bundle.extractall(project)
    return project


def run_project(project: Path, *, compile_timeout: float = 120, run_timeout: float = 60) -> dict:
    """Compile with the production flags and run; return the scenario results."""
    gxx = shutil.which("g++")
    if not gxx:
        raise RuntimeError("g++ is required")
    try:
        compiled = subprocess.run(
            [gxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", "src", "test/host/harness.cpp", "-o", "harness"],
            cwd=project, capture_output=True, timeout=compile_timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"outcome": "STILLBORN", "failed": [], "detail": "compile timed out"}
    if compiled.returncode != 0:
        first = (compiled.stderr or b"").decode(errors="replace").strip().splitlines()[:1]
        return {"outcome": "STILLBORN", "failed": [], "detail": first[0] if first else "compile failed"}
    try:
        ran = subprocess.run([str(project / "harness")], cwd=project, capture_output=True, timeout=run_timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"outcome": "KILLED", "failed": ["<timeout>"], "detail": "harness did not finish"}
    rows = []
    for line in ran.stdout.decode(errors="replace").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                return {"outcome": "KILLED", "failed": ["<malformed output>"], "detail": "harness output was not JSON"}
    failed = [row.get("scenario") for row in rows if row.get("pass") is not True]
    if ran.returncode != 0 and not failed:
        failed = ["<exit code>"]
    return {"outcome": "KILLED" if failed else "SURVIVED", "failed": failed, "scenarios": [row.get("scenario") for row in rows], "detail": ""}


def evaluate(mutant: Mutant, baseline: Path, workdir: Path) -> dict:
    project = workdir / mutant.id
    shutil.copytree(baseline, project)
    core = project / "src" / "app_core.h"
    core.write_text(apply_mutant(core.read_text(encoding="utf-8"), mutant), encoding="utf-8")
    result = run_project(project)
    failed = set(result["failed"])
    return {
        "id": mutant.id,
        "bug_class": mutant.bug_class,
        "story": mutant.story,
        "outcome": result["outcome"],
        "failing_scenarios": sorted(failed),
        "detected_by": {
            "smoke": bool(failed & SMOKE),
            "healthy": bool(failed & HEALTHY),
            "matrix": result["outcome"] == "KILLED",
        },
        "equivalent_reason": mutant.equivalent_reason,
        "detail": result["detail"],
    }


def summarize(rows: list[dict]) -> dict:
    live = [row for row in rows if row["outcome"] != "STILLBORN"]
    reviewed_equivalent = [row for row in live if row["outcome"] == "SURVIVED" and row["equivalent_reason"]]
    scored = [row for row in live if row not in reviewed_equivalent]

    def tier(name: str) -> dict:
        killed = sum(1 for row in scored if row["detected_by"][name])
        return {"killed": killed, "of": len(scored), "score": round(killed / len(scored), 3) if scored else None}

    classes: dict[str, dict] = {}
    for row in scored:
        entry = classes.setdefault(row["bug_class"], {"total": 0, "smoke": 0, "healthy": 0, "matrix": 0})
        entry["total"] += 1
        for name in ("smoke", "healthy", "matrix"):
            entry[name] += int(row["detected_by"][name])
    return {
        "mutants_defined": len(rows),
        "stillborn_compile_errors": [row["id"] for row in rows if row["outcome"] == "STILLBORN"],
        "reviewed_equivalent": [row["id"] for row in reviewed_equivalent],
        "scored_mutants": len(scored),
        "tiers": {name: tier(name) for name in ("smoke", "healthy", "matrix")},
        "survivors_without_review": [row["id"] for row in scored if row["outcome"] == "SURVIVED"],
        "caught_only_by_fault_scenarios": [row["id"] for row in scored if row["detected_by"]["matrix"] and not row["detected_by"]["healthy"]],
        "by_bug_class": classes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, help="write the JSON report here")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    parser.add_argument("--set", choices=("primary", "heldout", "all"), default="primary",
                        help="which mutants to score (default: the primary set)")
    parser.add_argument("--harness", type=Path,
                        help="use this host harness instead of the generated one, e.g. to score an earlier revision")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="hs-fault-matrix-") as scratch:
        work = Path(scratch)
        baseline = build_package(work)
        if args.harness:
            (baseline / "test" / "host" / "harness.cpp").write_bytes(args.harness.read_bytes())
        base = run_project(baseline)
        if base["outcome"] != "SURVIVED":
            print(f"Baseline is not clean ({base['outcome']}: {base['failed']}); the benchmark is invalid.", file=sys.stderr)
            return 2
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            chosen = {"primary": MUTANTS, "heldout": HELDOUT_MUTANTS, "all": MUTANTS + HELDOUT_MUTANTS}[args.set]
            rows = list(pool.map(lambda mutant: evaluate(mutant, baseline, work), chosen))
    report = {
        "schema_version": SCHEMA,
        "claim_boundary": CLAIM_BOUNDARY,
        "target": "esp32_oled_bme280_usb host application core (src/app_core.h)",
        "mutant_set": args.set,
        "harness_override": args.harness.name if args.harness else None,
        "detectors": {"smoke": sorted(SMOKE), "healthy": sorted(HEALTHY), "matrix": "all host scenarios"},
        "summary": summarize(rows),
        "mutants": rows,
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    summary = report["summary"]
    print(f"mutants defined={summary['mutants_defined']} scored={summary['scored_mutants']} "
          f"stillborn={len(summary['stillborn_compile_errors'])} reviewed_equivalent={len(summary['reviewed_equivalent'])}")
    for name, tier in summary["tiers"].items():
        print(f"  {name:8s} {tier['killed']:>3}/{tier['of']:<3} = {tier['score']}")
    if summary["survivors_without_review"]:
        print("  SURVIVORS needing review:", ", ".join(summary["survivors_without_review"]))
    if summary["stillborn_compile_errors"]:
        print("  STILLBORN (fix the mutant):", ", ".join(summary["stillborn_compile_errors"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
