"""tscircuit capacity-autorouter glue — opt-in MIT autoroute alternative."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def _npx_available() -> bool:
    return bool(shutil.which("npx") or shutil.which("node"))


def run_tscircuit_autorouter(
    build_dir: str | Path,
    *,
    out_dir: Optional[str | Path] = None,
    timeout_s: int = 300,
) -> Dict[str, Any]:
    """Attempt tscircuit autoroute from circuit_json when Node tooling is present.

    FreeRouting remains the default product engine. This path is opt-in and may
    skip when circuit-json or npx/@tscircuit packages are unavailable.
    """
    root = Path(build_dir)
    circuit_path = root / "build_compilation" / "circuit_json.json"
    if not circuit_path.is_file():
        return {
            "ok": False,
            "skipped": True,
            "reason": "circuit_json_missing",
            "engine": "tscircuit",
        }

    if not _npx_available():
        return {
            "ok": False,
            "skipped": True,
            "reason": "node_npx_unavailable",
            "engine": "tscircuit",
        }

    work = Path(out_dir) if out_dir else root / "build_compilation" / "exports" / "tscircuit_autoroute"
    work.mkdir(parents=True, exist_ok=True)
    out_json = work / "autorouted_circuit.json"

    # Prefer explicit package if installed; otherwise document skip with install hint.
    # We avoid network install during product runs unless HARDWARE_SPLICER_TSCIRCUIT_AUTOROUTE_INSTALL=1.
    allow_install = os.environ.get("HARDWARE_SPLICER_TSCIRCUIT_AUTOROUTE_INSTALL", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # Minimal invocation: copy input + write a status stub when the CLI isn't ready.
    # Real routing uses `@tscircuit/capacity-autorouter` when resolvable.
    try:
        circuit_docs = json.loads(circuit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "skipped": False, "reason": f"circuit_json_invalid:{exc}", "engine": "tscircuit"}

    probe = [
        "npx",
        "--yes" if allow_install else "--no-install",
        "@tscircuit/capacity-autorouter",
        "--help",
    ]
    try:
        help_proc = subprocess.run(
            probe,
            capture_output=True,
            text=True,
            timeout=min(60, timeout_s),
            check=False,
            cwd=str(work),
        )
    except Exception as exc:
        return {
            "ok": False,
            "skipped": True,
            "reason": f"tscircuit_probe_failed:{exc}",
            "engine": "tscircuit",
            "install_hint": "npm i -g @tscircuit/capacity-autorouter  (or set HARDWARE_SPLICER_TSCIRCUIT_AUTOROUTE_INSTALL=1)",
        }

    if help_proc.returncode != 0:
        return {
            "ok": False,
            "skipped": True,
            "reason": "tscircuit_autorouter_unavailable",
            "engine": "tscircuit",
            "stderr": (help_proc.stderr or "")[-800:],
            "install_hint": "npm i @tscircuit/capacity-autorouter  (or set HARDWARE_SPLICER_TSCIRCUIT_AUTOROUTE_INSTALL=1)",
        }

    # Package help exists — attempt a file-based run if the CLI supports it.
    # Fallback: persist input + honest status for operator handoff.
    in_copy = work / "input_circuit.json"
    in_copy.write_text(json.dumps(circuit_docs, indent=2), encoding="utf-8")

    for cmd in (
        ["npx", "--no-install", "@tscircuit/capacity-autorouter", str(in_copy), "-o", str(out_json)],
        ["npx", "--no-install", "@tscircuit/capacity-autorouter", "autoroute", str(in_copy), "--out", str(out_json)],
    ):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False, cwd=str(work))
        except subprocess.TimeoutExpired:
            return {"ok": False, "skipped": False, "reason": "tscircuit_timeout", "engine": "tscircuit"}
        except Exception:
            continue
        if out_json.is_file() and out_json.stat().st_size > 20:
            return {
                "ok": True,
                "skipped": False,
                "engine": "tscircuit",
                "routed_circuit_json": str(out_json),
                "out_dir": str(work),
            }
        if proc.returncode == 0:
            # Help-only success without file output — package present but CLI contract differs.
            status = {
                "ok": False,
                "skipped": False,
                "reason": "tscircuit_cli_contract_unsupported",
                "engine": "tscircuit",
                "input_circuit_json": str(in_copy),
                "out_dir": str(work),
                "note": "Package resolved; pass circuit-json through tscircuit playground or update bridge CLI flags.",
                "stderr": (proc.stderr or "")[-600:],
            }
            (work / "AUTOROUTE_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
            return status

    status = {
        "ok": False,
        "skipped": False,
        "reason": "tscircuit_autoroute_failed",
        "engine": "tscircuit",
        "input_circuit_json": str(in_copy),
        "out_dir": str(work),
    }
    (work / "AUTOROUTE_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status
