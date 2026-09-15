from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    shutil.which("kicad-cli") is None,
    reason="campaign generation requires KiCad 9; dedicated workflow installs it",
)


ROOT = Path(__file__).resolve().parents[1]
BUILDER = (
    ROOT
    / "hardware"
    / "reference_designs"
    / "spi_flash_adapter_v1"
    / "build_remote_fct_campaign.py"
)
SPEC = importlib.util.spec_from_file_location("spi_remote_fct_campaign", BUILDER)
assert SPEC and SPEC.loader
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


def test_campaign_archive_is_deterministic_byte_bound_and_non_authorizing(
    tmp_path: Path,
) -> None:
    first = campaign.build_campaign()
    second = campaign.build_campaign()
    assert first == second

    audit = campaign.audit_campaign(first)
    assert audit["audit_pass"] is True
    assert audit["physical_authority_granted"] is False

    with zipfile.ZipFile(BytesIO(first)) as archive:
        prefix = "SPI_FLASH_ADAPTER_REMOTE_FCT/"
        manifest = json.loads(archive.read(prefix + "CAMPAIGN_MANIFEST.json"))
        gauntlet = json.loads(archive.read(prefix + "gauntlet/GAUNTLET_STATE.json"))
        handoff = json.loads(archive.read(prefix + "handoff/REMOTE_TEST_REQUEST.json"))
        assert manifest["production_artifact_bytes_verified"] is True
        assert len(manifest["production_artifacts"]) == 9
        assert handoff["release_readiness"]["production_artifact_set_complete"] is True
        assert handoff["release_readiness"]["fabrication_release_ready"] is False
        assert gauntlet["state"] == "PACKAGED_NOT_PHYSICAL"
        assert gauntlet["source_blind_independent_design_claim"] is False
        assert gauntlet["powered"] is False
        with zipfile.ZipFile(BytesIO(archive.read(prefix + "production/HOST_TEST_SOFTWARE.zip"))) as host:
            assert host.read("host_test/src/hardware_splicer/__init__.py") == b""
            assert "host_test/src/hardware_splicer/spi_remote_fct.py" in host.namelist()
            host.extractall(tmp_path)
    local_src = tmp_path / "host_test" / "src"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join((str(local_src), str(ROOT / "src")))
    resolution = subprocess.run(
        [
            sys.executable,
            "-c",
            "import hardware_splicer.spi_remote_fct as module; print(module.__file__)",
        ],
        cwd=tmp_path / "host_test",
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    assert Path(resolution.stdout.strip()).resolve() == (
        local_src / "hardware_splicer" / "spi_remote_fct.py"
    ).resolve()


def test_campaign_audit_rejects_tampered_bytes() -> None:
    original = campaign.build_campaign()
    with zipfile.ZipFile(BytesIO(original)) as source:
        members = {name: source.read(name) for name in source.namelist()}
    target = next(name for name in members if name.endswith("production/BOM.csv"))
    members[target] += b"tampered"
    rebuilt = campaign.archive_bytes(
        {
            name.removeprefix("SPI_FLASH_ADAPTER_REMOTE_FCT/"): payload
            for name, payload in members.items()
        },
        prefix="SPI_FLASH_ADAPTER_REMOTE_FCT",
    )
    audit = campaign.audit_campaign(rebuilt)
    assert audit["audit_pass"] is False
    assert any("hash or size mismatch" in value for value in audit["blockers"])


def test_campaign_audit_rejects_internally_inconsistent_gauntlet_projection() -> None:
    original = campaign.build_campaign()
    with zipfile.ZipFile(BytesIO(original)) as source:
        members = {name: source.read(name) for name in source.namelist()}
    target = next(name for name in members if name.endswith("gauntlet/GAUNTLET_STATE.json"))
    gauntlet = json.loads(members[target])
    gauntlet["state"] = "PHYSICAL_EVIDENCE_PERSISTED"
    members[target] = campaign.canonical_bytes(gauntlet)
    manifest_name = next(name for name in members if name.endswith("CAMPAIGN_MANIFEST.json"))
    manifest = json.loads(members[manifest_name])
    row = next(
        item for item in manifest["files"] if item["path"] == "gauntlet/GAUNTLET_STATE.json"
    )
    row["sha256"] = campaign.digest(members[target])
    row["size_bytes"] = len(members[target])
    members[manifest_name] = campaign.canonical_bytes(manifest)
    rebuilt = campaign.archive_bytes(
        {
            name.removeprefix("SPI_FLASH_ADAPTER_REMOTE_FCT/"): payload
            for name, payload in members.items()
        },
        prefix="SPI_FLASH_ADAPTER_REMOTE_FCT",
    )
    audit = campaign.audit_campaign(rebuilt)
    assert audit["audit_pass"] is False
    assert "Gauntlet truth state is invalid" in audit["blockers"]


@pytest.mark.parametrize(
    ("target_suffix", "field", "value"),
    [
        ("handoff/REMOTE_TEST_REQUEST.json", "release_readiness.fabrication_release_ready", True),
        ("gauntlet/GAUNTLET_STATE.json", "power_on_ready", True),
        ("gauntlet/GAUNTLET_STATE.json", "physical_gates", "passed"),
    ],
)
def test_campaign_audit_rejects_rehashed_authority_contradictions(
    target_suffix: str, field: str, value: object
) -> None:
    original = campaign.build_campaign()
    with zipfile.ZipFile(BytesIO(original)) as source:
        members = {name: source.read(name) for name in source.namelist()}
    target = next(name for name in members if name.endswith(target_suffix))
    projection = json.loads(members[target])
    keys = field.split(".")
    destination = projection
    for key in keys[:-1]:
        destination = destination[key]
    destination[keys[-1]] = value
    members[target] = campaign.canonical_bytes(projection)
    manifest_name = next(name for name in members if name.endswith("CAMPAIGN_MANIFEST.json"))
    manifest = json.loads(members[manifest_name])
    relative = target.removeprefix("SPI_FLASH_ADAPTER_REMOTE_FCT/")
    row = next(item for item in manifest["files"] if item["path"] == relative)
    row["sha256"] = campaign.digest(members[target])
    row["size_bytes"] = len(members[target])
    members[manifest_name] = campaign.canonical_bytes(manifest)
    rebuilt = campaign.archive_bytes(
        {
            name.removeprefix("SPI_FLASH_ADAPTER_REMOTE_FCT/"): payload
            for name, payload in members.items()
        },
        prefix="SPI_FLASH_ADAPTER_REMOTE_FCT",
    )
    audit = campaign.audit_campaign(rebuilt)
    assert audit["audit_pass"] is False
    assert any("canonical" in blocker for blocker in audit["blockers"])


def test_campaign_audit_rejects_rehashed_acceptance_substitution() -> None:
    original = campaign.build_campaign()
    with zipfile.ZipFile(BytesIO(original)) as source:
        members = {name: source.read(name) for name in source.namelist()}
    prefix = "SPI_FLASH_ADAPTER_REMOTE_FCT/"
    criteria_name = prefix + "campaign/ACCEPTANCE_CRITERIA.json"
    handoff_name = prefix + "handoff/REMOTE_TEST_REQUEST.json"
    manifest_name = prefix + "CAMPAIGN_MANIFEST.json"
    criteria = json.loads(members[criteria_name])
    criteria["spi"]["expected_response_hex"] = "ffffff"
    members[criteria_name] = campaign.canonical_bytes(criteria)
    new_hash = campaign.digest(members[criteria_name])
    new_size = len(members[criteria_name])

    manifest = json.loads(members[manifest_name])
    artifact = next(
        row for row in manifest["production_artifacts"] if row["role"] == "acceptance_criteria"
    )
    artifact["content_hash"] = new_hash
    artifact["size_bytes"] = new_size
    handoff = json.loads(members[handoff_name])
    handoff_artifact = next(
        row for row in handoff["manufacturing_artifacts"] if row["role"] == "acceptance_criteria"
    )
    handoff_artifact["content_hash"] = new_hash
    handoff_artifact["size_bytes"] = new_size
    members[handoff_name] = campaign.canonical_bytes(handoff)
    for relative, payload in (
        ("campaign/ACCEPTANCE_CRITERIA.json", members[criteria_name]),
        ("handoff/REMOTE_TEST_REQUEST.json", members[handoff_name]),
    ):
        row = next(item for item in manifest["files"] if item["path"] == relative)
        row["sha256"] = campaign.digest(payload)
        row["size_bytes"] = len(payload)
    members[manifest_name] = campaign.canonical_bytes(manifest)
    rebuilt = campaign.archive_bytes(
        {name.removeprefix(prefix): payload for name, payload in members.items()},
        prefix="SPI_FLASH_ADAPTER_REMOTE_FCT",
    )
    audit = campaign.audit_campaign(rebuilt)
    assert audit["audit_pass"] is False
    assert "acceptance criteria differ from the frozen campaign contract" in audit["blockers"]
    assert "candidate production artifacts disagree with campaign" in audit["blockers"]
