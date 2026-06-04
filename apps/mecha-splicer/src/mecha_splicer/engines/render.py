from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RenderResult:
    ok: bool
    method: str
    cmd: str
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok, "method": self.method, "cmd": self.cmd, "stdout": self.stdout, "stderr": self.stderr, "error": self.error}


def render_openscad_to_stl(scad_path: Path, stl_path: Path, *, docker_image: Optional[str] = None, timeout_s: int = 120) -> dict:
    """
    Render an OpenSCAD `.scad` file to `.stl`.

    Strategy:
      1) Use local `openscad` binary if available.
      2) Else, if `docker_image` provided and `docker` exists, run OpenSCAD in docker.
    """
    scad_path = Path(scad_path)
    stl_path = Path(stl_path)
    stl_path.parent.mkdir(parents=True, exist_ok=True)

    openscad = shutil.which("openscad")
    if openscad:
        cmd = [openscad, "-o", str(stl_path), str(scad_path)]
        return _run(cmd, method="openscad", timeout_s=timeout_s).to_dict()

    docker = shutil.which("docker")
    if docker and docker_image:
        # Mount parent directory to keep relative includes working.
        host_dir = scad_path.parent.resolve()
        in_scad = f"/work/{scad_path.name}"
        out_stl = f"/work/{stl_path.name}"
        cmd = [
            docker,
            "run",
            "--rm",
            "-v",
            f"{host_dir}:/work",
            docker_image,
            "openscad",
            "-o",
            out_stl,
            in_scad,
        ]
        return _run(cmd, method=f"docker:{docker_image}", timeout_s=timeout_s).to_dict()

    return RenderResult(ok=False, method="none", cmd="", error="No openscad binary found; provide openscad or use --openscad-docker-image with docker.").to_dict()


def _run(cmd: list[str], *, method: str, timeout_s: int) -> RenderResult:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, env={**os.environ})
        if p.returncode != 0:
            return RenderResult(ok=False, method=method, cmd=" ".join(cmd), stdout=p.stdout, stderr=p.stderr, error=f"exit {p.returncode}")
        return RenderResult(ok=True, method=method, cmd=" ".join(cmd), stdout=p.stdout, stderr=p.stderr)
    except Exception as e:
        return RenderResult(ok=False, method=method, cmd=" ".join(cmd), error=str(e))

