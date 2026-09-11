#!/usr/bin/env python3
"""Resource-bounded front door for exactly one prepared Codex/Astra HS case.

Dry-run remains the default. Live execution delegates to the existing one-shot runner but
forces its MCP command through the fail-closed governor and clamps wall-clock exposure.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path[:] = [
    str(_REPO_ROOT),
    *[entry for entry in sys.path if Path(entry or os.curdir).resolve() != _SCRIPT_DIR],
]

from hardware_splicer.codex_astra_runtime import CODEX_ALLOWANCE_CONFIRMATION
from hardware_splicer.codex_budgeted_entrypoint import (
    ASTRA_DEFAULT_TIMEOUT_SECONDS,
    ASTRA_LAUNCHER_TEMP_ROOT,
    ASTRA_MAX_TIMEOUT_SECONDS,
    build_delegated_runner_argv,
    resolve_canonical_backend,
    resource_guard_manifest,
    validate_launcher,
    write_budgeted_mcp_launcher,
    write_resource_guard_manifest,
)


def _observer_dir(manifest_path: Path) -> Path:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("case manifest must be a JSON object")
    configured = payload.get("observer_directory")
    if isinstance(configured, str) and configured.strip():
        observer = Path(configured).expanduser().resolve()
    else:
        observer = manifest_path.parent
    if observer != manifest_path.parent:
        raise ValueError("observer directory must be the manifest parent")
    return observer


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resource-bounded wrapper for one Codex/Astra HS case. It forces the canonical "
            "MCP backend through a hard tool-call governor and never permits more than five "
            "minutes of wall-clock execution."
        )
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--backend-command", default="hs-backend-mcp")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-codex-allowance")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=ASTRA_DEFAULT_TIMEOUT_SECONDS,
        help=f"One-case process ceiling; hard maximum {ASTRA_MAX_TIMEOUT_SECONDS}s.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"case manifest does not exist: {manifest_path}")
    try:
        observer = _observer_dir(manifest_path)
        backend = resolve_canonical_backend(args.backend_command)
        guard = resource_guard_manifest(timeout_seconds=args.timeout_seconds)
    except (OSError, TypeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    guard_path = observer / "CODEX_ASTRA_RESOURCE_GUARD.json"
    write_resource_guard_manifest(guard_path, timeout_seconds=args.timeout_seconds)

    runner_script = _SCRIPT_DIR / "run_codex_astra_case.py"
    if not runner_script.is_file():
        raise SystemExit(f"delegated one-shot runner is missing: {runner_script}")

    # Codex permission profiles protect home/cache paths even when a leaf path is
    # explicitly readable. A private randomized directory beneath /tmp is traversable
    # by the clean-room sandbox and contains only the generated one-shot launcher.
    with tempfile.TemporaryDirectory(
        prefix="hs-astra-budgeted-mcp-",
        dir=ASTRA_LAUNCHER_TEMP_ROOT,
    ) as temp_dir:
        # The Codex Linux sandbox needs directory traversal before it can apply the
        # explicit read grant to the launcher. The directory contains no credentials
        # and only one 0700 launcher, so traversal/listing does not expose secret state.
        Path(temp_dir).chmod(0o755)
        launcher = write_budgeted_mcp_launcher(
            Path(temp_dir) / "hs-astra-budgeted-mcp",
            backend_command=backend,
        )
        if not validate_launcher(launcher):
            raise SystemExit("budgeted MCP launcher failed executable validation")
        argv = build_delegated_runner_argv(
            runner_script=runner_script,
            manifest=manifest_path,
            mcp_launcher=launcher,
            timeout_seconds=args.timeout_seconds,
            codex_command=args.codex_command,
            execute=args.execute,
            confirmation=args.confirm_codex_allowance,
        )
        if not args.execute:
            payload = {
                "schema_version": "hardware_splicer.codex_astra_budgeted_entrypoint_plan.v1",
                "execution_performed": False,
                "delegated_runner": str(runner_script),
                "canonical_backend": backend,
                "budgeted_mcp_launcher": str(launcher),
                "resource_guard_file": str(guard_path),
                "resource_guard": guard,
                "required_live_acknowledgement": CODEX_ALLOWANCE_CONFIRMATION,
                "delegated_argv": argv,
                "api_fallback": False,
                "physical_authority_granted": False,
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
            return 0

        completed = subprocess.run(
            argv,
            check=False,
            env=dict(os.environ),
        )
        return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
