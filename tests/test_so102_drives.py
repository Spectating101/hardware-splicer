import importlib.util
import json
from pathlib import Path

import pytest

from hardware_splicer.digital_engine_cli import run
from hardware_splicer.so102_drives import follower_drive


def test_shoulder_and_elbow_share_a_mount_but_have_distinct_joints_and_cables():
    shoulder = follower_drive("shoulder")
    elbow = follower_drive("elbow")
    assert shoulder["mount"] == elbow["mount"]
    assert shoulder["mount"]["step_bounding_box_mm"] == [113, 34, 20]
    for report, joint_id, long_cable in [(shoulder, 2, [1, 2]), (elbow, 3, [3, 4])]:
        assert report["drive"]["mpn"] == "ST-3250-C002"
        assert report["drive"]["bus_id"] == joint_id
        assert report["drive"]["long_cable_bus_ids"] == long_cable
        assert report["drive"]["simulation_joint"]["name"] == f"link{joint_id-1}_to_link{joint_id}"
        assert report["drive"]["motor_body_link"] == "link2_1"
        assert all(report["source_revision"] in src["url"] for src in report["sources"].values())
        assert len(report["supplier_offers_from_bom"]) == 2


def test_passive_leader_donor_cannot_drive_shoulder():
    swap = follower_drive("shoulder", passive_leader=True)["substitution"]
    check = next(row for row in swap["checks"] if row["code"] == "required_functions")
    assert check["missing_functions"] == ["powered_joint_drive"]
    assert swap["status"] == "blocked"


def test_same_target_angle_differs_between_joints_with_the_same_motor():
    assert not follower_drive("shoulder", angle_deg=120)["travel_check"]["within_joint_limits"]
    assert follower_drive("elbow", angle_deg=120)["travel_check"]["within_joint_limits"]
    assert follower_drive("shoulder", angle_deg=91)["travel_check"]["within_joint_limits"]
    assert not follower_drive("shoulder", angle_deg=91.000001)["travel_check"]["within_joint_limits"]
    with pytest.raises(ValueError, match="finite"):
        follower_drive("elbow", angle_deg=float("nan"))


def test_cli_custom_candidate_checks_voltage_and_keeps_fit_open(tmp_path, capsys):
    candidate = follower_drive("elbow")["reference_profile"]
    candidate.pop("source")
    candidate.update(part_id="salvaged-servo", mpn="test-donor")
    path = tmp_path / "donor.json"
    for allowed, expected in [([5, 8], "blocked"), ([10, 14], "unresolved")]:
        candidate["ports"][0]["voltage_range_v"] = allowed
        path.write_text(json.dumps(candidate))
        assert run(["so102-drive", "elbow", "--candidate", str(path)]) == 0
        swap = json.loads(capsys.readouterr().out)["report"]["substitution"]
        assert swap["status"] == expected
        assert not swap["direct_replacement_within_declared_scope"]
        assert not swap["construction_ready"]
    path.write_text("null")
    assert run(["so102-drive", "elbow", "--candidate", str(path)]) == 1


def test_rebuild_refuses_mixed_source_before_opening_cad(tmp_path):
    path = Path(__file__).resolve().parents[1] / "scripts/prepare_so102_drives.py"
    spec = importlib.util.spec_from_file_location("prepare_so102_drives", path)
    recipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recipe)
    report = follower_drive("shoulder")
    assert report["source_revision"] == recipe.REVISION
    for key, (_, digest) in recipe.FILES.items():
        assert report["sources"][key]["sha256"] == digest
    bom = tmp_path / recipe.FILES["bom"][0]
    bom.parent.mkdir()
    bom.write_text("other revision")
    with pytest.raises(ValueError, match="docs/bom.md"):
        recipe.build(tmp_path)
