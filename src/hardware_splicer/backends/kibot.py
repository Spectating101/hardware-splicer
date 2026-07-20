from __future__ import annotations

from pathlib import Path

from .base import BackendResult, BackendStatus, executable_version, run_command_backend


def write_kibot_config(
    *,
    project_file: str | Path,
    out_dir: str | Path,
) -> BackendResult:
    project = Path(project_file)
    if not project.exists():
        return BackendResult(
            backend="kibot",
            status=BackendStatus.BLOCKED,
            diagnostics=[f"KiCad project not found: {project}"],
        )
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    config = root / "hardware_splicer.kibot.yaml"
    config.write_text(
        """kibot:\n  version: 1\n\npreflight:\n  run_erc: true\n  run_drc: true\n  check_zone_fills: true\n\noutputs:\n  - name: gerbers\n    type: gerber\n    dir: fabrication/gerbers\n  - name: drill\n    type: excellon\n    dir: fabrication/drill\n  - name: bom\n    type: bom\n    dir: assembly\n  - name: position\n    type: position\n    dir: assembly\n  - name: board_render\n    type: pcbdraw\n    dir: documentation\n""",
        encoding="utf-8",
    )
    return BackendResult(
        backend="kibot",
        status=BackendStatus.SUCCESS,
        inputs=[str(project)],
        outputs=[str(config)],
        version=executable_version("kibot"),
    )


def run_kibot(
    *,
    project_file: str | Path,
    config_file: str | Path,
    out_dir: str | Path,
) -> BackendResult:
    project = Path(project_file)
    config = Path(config_file)
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    return run_command_backend(
        backend="kibot",
        command=["kibot", "-c", str(config), "-e", str(project), "-d", str(root)],
        cwd=root,
        inputs=[str(project), str(config)],
        expected_outputs=["fabrication", "assembly", "documentation"],
        version=executable_version("kibot"),
    )
