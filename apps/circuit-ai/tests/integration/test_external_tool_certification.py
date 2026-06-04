from __future__ import annotations

import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server

DEMO_DIR = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo"
DEMO_NET_A = DEMO_DIR / "usb_esp32_sensor.net"
DEMO_NET_B = DEMO_DIR / "drone_fc_power.net"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "")
    monkeypatch.setenv("CIRCUIT_AI_USAGE_DB", str(tmp_path / "usage.sqlite"))
    return api_server.app.test_client()


def _generated_empty_kicad_board() -> Path:
    pcbnew = pytest.importorskip("pcbnew")
    outdir = Path(tempfile.mkdtemp(prefix="cai-cert-board-"))
    board_path = outdir / "cert_board.kicad_pcb"
    board = pcbnew.CreateEmptyBoard()
    pcbnew.SaveBoard(str(board_path), board)
    assert board_path.exists()
    return board_path


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_live_kicad_cli_manufacturing_certification(client):
    board_path = _generated_empty_kicad_board()

    with board_path.open("rb") as pf:
        r = client.post(
            "/api/v2/manufacture/gerber",
            data={"pcb_file": (pf, board_path.name)},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    gerber = r.get_json() or {}
    assert gerber.get("status") == "success"
    assert gerber.get("export_method") == "kicad-cli"
    assert Path(gerber["zip_file"]).exists()

    with board_path.open("rb") as pf:
        r = client.post(
            "/api/v2/manufacture/pnp",
            data={"pcb_file": (pf, board_path.name)},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    pnp = r.get_json() or {}
    assert pnp.get("status") == "success"
    assert pnp.get("export_method") == "kicad-cli"
    assert "Ref" in (pnp.get("csv") or "")

    with board_path.open("rb") as pf:
        r = client.post(
            "/api/v2/manufacture/package",
            data={"pcb_file": (pf, board_path.name)},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    package = r.get_json() or {}
    assert package.get("status") == "success"
    package_path = Path(package["package_file"])
    assert package_path.exists()

    with zipfile.ZipFile(package_path) as zf:
        manifest = json.loads(zf.read("MANIFEST.json"))
        metadata = manifest.get("metadata") or {}
        assert metadata.get("gerbers_export_method") == "kicad-cli"
        assert metadata.get("pnp_export_method") == "kicad-cli"
        assert metadata.get("kicad_cli_version")


@pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice not installed")
def test_live_ngspice_and_machine_full_sim_certification(client):
    r = client.post(
        "/api/v2/simulate/spice",
        data=json.dumps({"netlist_text": "* certification\nV1 in 0 5\nR1 in 0 1k\n.op\n.end\n"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    spice = (r.get_json() or {}).get("result") or {}
    assert spice.get("ok") is True
    assert spice.get("export_method") == "ngspice"
    assert "Doing analysis" in (spice.get("stdout") or "")

    if not DEMO_NET_A.exists() or not DEMO_NET_B.exists():
        pytest.skip("demo netlists not present")

    payload = {
        "machine": {
            "machine_name": "CertificationMachine",
            "boards": [
                {
                    "board_id": "main_ctrl",
                    "lane": "generic",
                    "requirements": {
                        "meta": {"project_name": "Main Ctrl"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 2},
                        "risk_and_validation": {"what_good_looks_like": "Boot"},
                    },
                },
                {
                    "board_id": "power_stage",
                    "lane": "power",
                    "requirements": {
                        "meta": {"project_name": "Power Stage"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 2},
                        "power": {
                            "rails": [{"name": "12V", "voltage_v": 12.0, "max_current_a": 1.0}],
                            "sources": [{"name": "VIN", "voltage_v": 24.0, "max_current_a": 2.0}],
                            "loads": [{"name": "Main", "rail": "12V", "current_a": 0.4}],
                        },
                        "risk_and_validation": {"what_good_looks_like": "No brownout"},
                    },
                },
            ],
            "interconnects": [{"from_board": "power_stage", "to_board": "main_ctrl", "interface": "power", "length_cm": 20}],
            "power_tree": [
                {"source": "battery_24v", "board_id": "power_stage", "rail": "VIN", "voltage_v": 24.0, "max_current_a": 2.0},
                {"source": "power_stage", "board_id": "main_ctrl", "rail": "12V", "voltage_v": 12.0, "max_current_a": 1.0},
            ],
        },
        "board_design_files": {
            "main_ctrl": {"path": str(DEMO_NET_A), "kind": "netlist"},
            "power_stage": {"path": str(DEMO_NET_B), "kind": "netlist"},
        },
        "strict": False,
        "simulation_fidelity": "high",
    }
    r = client.post("/api/v2/machines/full-simulate", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    result = (r.get_json() or {}).get("result") or {}
    assert result.get("verdict") in {"pass", "partial_pass", "fail"}

    board_sims = result.get("board_simulations") or []
    assert len(board_sims) >= 2
    assert all(bool((row.get("spice") or {}).get("ok")) for row in board_sims)
    gate_map = {g.get("gate"): g for g in (result.get("gates") or []) if isinstance(g, dict)}
    assert gate_map["board_level_operating_point"]["passed"] is True
    assert gate_map["board_level_ngspice_crosscheck"]["passed"] is True
