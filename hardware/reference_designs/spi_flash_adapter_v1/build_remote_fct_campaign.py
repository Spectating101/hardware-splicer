#!/usr/bin/env python3
"""Build the deterministic rev-0.2 remote-FCT and Gauntlet campaign archive."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.project_physical_validation import (  # noqa: E402
    build_project_physical_validation_packet,
    project_candidate_boundary,
)
from hardware_splicer.remote_physical_validation import (  # noqa: E402
    build_remote_physical_handoff,
    build_remote_physical_handoff_archive,
    build_remote_physical_return_template,
    render_remote_physical_test_plan,
)


CAMPAIGN_SCHEMA = "hardware_splicer.spi_remote_fct_campaign.v1"
CAMPAIGN_ID = "spi-flash-adapter-v1-remote-fct-r1"
PROJECT_ID = "spi-flash-adapter-v1-physical-candidate"
REQUIRED_PRODUCTION_ROLES = {
    "assembly_drawing",
    "bom",
    "fabrication_archive",
    "pick_and_place",
    "schematic",
    "test_firmware",
}
FIXED_ZIP_TIME = (2026, 9, 16, 0, 0, 0)
SOURCE_PACKET = (
    ROOT
    / "docs"
    / "physical_validation_handoffs"
    / "astra-v4-proposed-seeed-fusion"
    / "SOURCE_PHYSICAL_VALIDATION_PACKET.json"
)
KICAD_PYTHON = os.environ.get(
    "HARDWARE_SPLICER_KICAD_PYTHON",
    "/usr/bin/python3" if Path("/usr/bin/python3").is_file() else sys.executable,
)


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe campaign path: {value}")
    return str(path)


def archive_bytes(payloads: dict[str, bytes], *, prefix: str = "") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(payloads.items()):
            resolved = safe_path(f"{prefix}/{name}" if prefix else name)
            info = zipfile.ZipInfo(resolved, FIXED_ZIP_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload, compresslevel=9)
    return output.getvalue()


def run(*args: str, cwd: Path = HERE) -> None:
    subprocess.run(list(args), cwd=cwd, check=True)


def member(archive: zipfile.ZipFile, name: str) -> bytes:
    safe_path(name)
    try:
        return archive.read(name)
    except KeyError as exc:
        raise ValueError(f"review package lacks required member: {name}") from exc


def normalize_native_report(name: str, payload: bytes) -> bytes:
    if name.endswith(".json"):
        value = json.loads(payload)
        if isinstance(value, dict) and "date" in value:
            value["date"] = "2026-09-16T00:00:00+0800"
        return canonical_bytes(value)
    text = payload.decode()
    text = re.sub(
        r"Saved (ERC|DRC) Report to .*?/(erc|drc)\.json",
        lambda match: f"Saved {match.group(1)} Report to reports/{match.group(2)}.json",
        text,
    )
    return text.encode()


def artifact_row(role: str, artifact_id: str, path: str, payload: bytes) -> dict[str, object]:
    return {
        "role": role,
        "artifact_id": artifact_id,
        "filename": safe_path(path),
        "content_hash": digest(payload),
        "size_bytes": len(payload),
    }


def build_gauntlet_state(packet: dict[str, object], handoff: dict[str, object]) -> dict[str, object]:
    """Project the only truthful pre-physical Gauntlet state for this campaign."""

    return {
        "schema_version": "hardware_splicer.gauntlet_physical_candidate.v1",
        "campaign_id": CAMPAIGN_ID,
        "candidate_revision": packet["candidate_revision"],
        "candidate_snapshot_hash": packet["candidate_snapshot_hash"],
        "handoff_id": handoff["handoff_id"],
        "state": "PACKAGED_NOT_PHYSICAL",
        "proof_class": "exact_reference_implementation_remote_fct_preparation",
        "source_blind_independent_design_claim": False,
        "production_artifact_set_complete": True,
        "backend_candidate_synchronized": False,
        "provider_status": "proposed_not_engaged",
        "submitted": False,
        "ordered": False,
        "fabricated": False,
        "assembled": False,
        "powered": False,
        "physical_gates": "not_run",
        "physical_correctness": "UNPROVEN",
        "fabrication_release_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
        "next_transition": "human review of exact quote payload and fabrication authorization",
    }


def build_campaign() -> bytes:
    with tempfile.TemporaryDirectory(prefix="hs-spi-remote-fct-") as temporary:
        temp = Path(temporary)
        review_zip_path = temp / "design-review.zip"
        run(KICAD_PYTHON, "build_package.py", "--output", str(review_zip_path))
        report_dir = temp / "native-reports"
        run(KICAD_PYTHON, "verify_design.py", "--report-dir", str(report_dir))

        payloads: dict[str, bytes] = {}
        with zipfile.ZipFile(review_zip_path) as review:
            base = "spi_flash_adapter_v1"
            manufacturing_members = {
                Path(name).name: review.read(name)
                for name in review.namelist()
                if name.startswith(f"{base}/manufacturing/") and not name.endswith("/")
            }
            fabrication_members = {
                name: value
                for name, value in manufacturing_members.items()
                if not name.endswith("-positions.csv")
            }
            fabrication_zip = archive_bytes(fabrication_members, prefix="fabrication")
            payloads["production/SPI_FLASH_ADAPTER_FABRICATION.zip"] = fabrication_zip
            payloads["production/BOM.csv"] = member(review, f"{base}/BOM.csv")
            payloads["production/PICK_AND_PLACE.csv"] = member(
                review, f"{base}/manufacturing/spi_flash_adapter_v1-positions.csv"
            )
            payloads["production/SCHEMATIC.pdf"] = member(
                review, f"{base}/review/spi_flash_adapter_v1-schematic.pdf"
            )
            payloads["production/ASSEMBLY_DRAWING.pdf"] = member(
                review, f"{base}/review/spi_flash_adapter_v1-front-assembly.pdf"
            )
        payloads["production/CANONICAL_DESIGN_PACKAGE.zip"] = review_zip_path.read_bytes()

        host_test = archive_bytes(
            {
                "scripts/run_spi_read_only_jedec_id.py": (
                    ROOT / "scripts" / "run_spi_read_only_jedec_id.py"
                ).read_bytes(),
                "src/hardware_splicer/spi_remote_fct.py": (
                    ROOT / "src" / "hardware_splicer" / "spi_remote_fct.py"
                ).read_bytes(),
                "src/hardware_splicer/__init__.py": b"",
                "README.md": (HERE / "remote_fct" / "HOST_TEST_README.md").read_bytes(),
            },
            prefix="host_test",
        )
        payloads["production/HOST_TEST_SOFTWARE.zip"] = host_test

        acceptance_bytes = (HERE / "remote_fct" / "ACCEPTANCE_CRITERIA.json").read_bytes()
        provider_plan_bytes = (HERE / "remote_fct" / "PROVIDER_TEST_PLAN.md").read_bytes()
        payloads["campaign/ACCEPTANCE_CRITERIA.json"] = acceptance_bytes
        payloads["campaign/PROVIDER_TEST_PLAN.md"] = provider_plan_bytes

        artifacts = [
            artifact_row("schematic", "spi-v1-schematic", "production/SCHEMATIC.pdf", payloads["production/SCHEMATIC.pdf"]),
            artifact_row("fabrication_archive", "spi-v1-fabrication", "production/SPI_FLASH_ADAPTER_FABRICATION.zip", fabrication_zip),
            artifact_row("bom", "spi-v1-bom", "production/BOM.csv", payloads["production/BOM.csv"]),
            artifact_row("pick_and_place", "spi-v1-placement", "production/PICK_AND_PLACE.csv", payloads["production/PICK_AND_PLACE.csv"]),
            artifact_row("assembly_drawing", "spi-v1-assembly", "production/ASSEMBLY_DRAWING.pdf", payloads["production/ASSEMBLY_DRAWING.pdf"]),
            # PR #99 names this required role test_firmware. This MCU-less board uses
            # bounded host test software; the artifact ID prevents semantic laundering.
            artifact_row("test_firmware", "spi-v1-bounded-host-test-software", "production/HOST_TEST_SOFTWARE.zip", host_test),
            artifact_row("canonical_design_package", "spi-v1-canonical-design", "production/CANONICAL_DESIGN_PACKAGE.zip", review_zip_path.read_bytes()),
            artifact_row("acceptance_criteria", "spi-v1-fct-acceptance-r1", "campaign/ACCEPTANCE_CRITERIA.json", acceptance_bytes),
            artifact_row("provider_test_plan", "spi-v1-provider-test-plan-r1", "campaign/PROVIDER_TEST_PLAN.md", provider_plan_bytes),
        ]
        artifacts = sorted(artifacts, key=lambda row: (str(row["role"]), str(row["artifact_id"])))

        source_packet_bytes = SOURCE_PACKET.read_bytes()
        source_packet = json.loads(source_packet_bytes)
        verification = json.loads((HERE / "verification.json").read_text())
        design_manifest = json.loads((HERE / "design_manifest.json").read_text())
        candidate_snapshot = {
            "schema_version": "hardware_splicer.spi_reference_candidate.v1",
            "name": "SPI Flash Adapter v1 physical candidate",
            "mission": "Physically evaluate the revision-bound 3.3 V to 1.8 V read-only SPI adapter.",
            "engineering_status": "packaged_for_remote_fct_not_released",
            "preFabricationPlan": {
                "design_id": design_manifest["design_id"],
                "design_revision": design_manifest["revision"],
                "result_status": design_manifest["result_status"],
                "selected_components": design_manifest["selected_components"],
                "target": design_manifest["target"],
                "authority": design_manifest["authority"],
            },
            "manufacturingArtifacts": artifacts,
            "verification": verification,
            "source_evaluation_boundary": {
                "source_packet_id": source_packet["packet_id"],
                "source_candidate_revision": source_packet["candidate_revision"],
                "source_packet_sha256": digest(source_packet_bytes),
                "relationship": "implementation_derived_after_source_evaluation",
                "backend_candidate_synchronized": False,
                "note": "The family-level source packet is preserved, not relabeled as this implementation.",
            },
        }
        packet = build_project_physical_validation_packet(
            candidate_snapshot, project_id=PROJECT_ID, revision=1
        )
        handoff = build_remote_physical_handoff(
            packet,
            provider={
                "provider_id": "proposed-pcba-fct-provider",
                "provider_name": "Proposed PCBA + FCT Provider",
                "engagement_mode": "pcba_production_and_test",
                "service_url": "",
                "capabilities_requested": [
                    "pcba_functional_test",
                    "electrical_performance_test",
                    "custom_test_fixture_review",
                    "original_raw_measurement_export",
                ],
            },
            manufacturing_artifacts=artifacts,
        )
        if not handoff["release_readiness"]["production_artifact_set_complete"]:
            raise ValueError("production artifact role set is incomplete")

        payloads.update(
            {
                "campaign/ACCEPTANCE_CRITERIA.json": acceptance_bytes,
                "campaign/PROVIDER_TEST_PLAN.md": provider_plan_bytes,
                "campaign/CANDIDATE_BOUNDARY.json": canonical_bytes(candidate_snapshot),
                "campaign/PHYSICAL_VALIDATION_PACKET.json": canonical_bytes(packet),
                "campaign/MANUFACTURING_ARTIFACTS.json": canonical_bytes(artifacts),
                "campaign/HISTORICAL_SOURCE_PACKET.json": source_packet_bytes,
                "handoff/REMOTE_TEST_REQUEST.json": canonical_bytes(handoff),
                "handoff/REMOTE_TEST_PLAN.md": render_remote_physical_test_plan(handoff).encode(),
                "handoff/EVIDENCE_RETURN_MANIFEST.template.json": canonical_bytes(build_remote_physical_return_template(handoff)),
                "handoff/REMOTE_PHYSICAL_HANDOFF.zip": build_remote_physical_handoff_archive(handoff),
            }
        )
        for name in ("erc.json", "drc.json", "erc.stdout.txt", "drc.stdout.txt"):
            payloads[f"reports/{name}"] = normalize_native_report(
                name, (report_dir / name).read_bytes()
            )
        payloads["reports/REPORT_NORMALIZATION.json"] = canonical_bytes(
            {
                "schema_version": "hardware_splicer.native_cad_report_normalization.v1",
                "changes": [
                    "KiCad wall-clock date normalized to 2026-09-16T00:00:00+0800",
                    "temporary output paths in stdout normalized to reports/<name>",
                ],
                "semantic_result_changed": False,
                "native_schema_and_violation_arrays_preserved": True,
                "toolchain": verification["toolchain"],
            }
        )

        gauntlet = build_gauntlet_state(packet, handoff)
        payloads["gauntlet/GAUNTLET_STATE.json"] = canonical_bytes(gauntlet)

        manifest = {
            "schema_version": CAMPAIGN_SCHEMA,
            "campaign_id": CAMPAIGN_ID,
            "design_id": design_manifest["design_id"],
            "design_revision": design_manifest["revision"],
            "candidate_revision": packet["candidate_revision"],
            "candidate_snapshot_hash": packet["candidate_snapshot_hash"],
            "handoff_id": handoff["handoff_id"],
            "manifest_self_hash_excluded": True,
            "files": [
                {"path": name, "sha256": digest(value), "size_bytes": len(value)}
                for name, value in sorted(payloads.items())
            ],
            "production_artifacts": artifacts,
            "production_artifact_bytes_verified": True,
            "backend_candidate_synchronized": False,
            "provider_status": "proposed_not_engaged",
            "fabrication_release_ready": False,
            "power_on_ready": False,
            "physical_correctness": "UNPROVEN",
            "physical_authority_granted": False,
            "authority_effect": "none",
        }
        payloads["CAMPAIGN_MANIFEST.json"] = canonical_bytes(manifest)
        return archive_bytes(payloads, prefix="SPI_FLASH_ADAPTER_REMOTE_FCT")


def audit_campaign(payload: bytes) -> dict[str, object]:
    blockers: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                blockers.append("duplicate archive paths")
            for name in names:
                try:
                    safe_path(name)
                except ValueError as exc:
                    blockers.append(str(exc))
            manifest_path = "SPI_FLASH_ADAPTER_REMOTE_FCT/CAMPAIGN_MANIFEST.json"
            manifest = json.loads(archive.read(manifest_path))
            expected = {
                f"SPI_FLASH_ADAPTER_REMOTE_FCT/{row['path']}": row
                for row in manifest.get("files", [])
            }
            actual = set(names) - {manifest_path}
            if actual != set(expected):
                blockers.append("archive paths do not equal the manifest")
            for name, row in expected.items():
                if name not in actual:
                    continue
                item = archive.read(name)
                if digest(item) != row.get("sha256") or len(item) != row.get("size_bytes"):
                    blockers.append(f"hash or size mismatch: {name}")
            artifact_roles: set[str] = set()
            for row in manifest.get("production_artifacts", []):
                role = str(row.get("role") or "")
                filename = str(row.get("filename") or "")
                if role in artifact_roles:
                    blockers.append(f"duplicate production artifact role: {role}")
                artifact_roles.add(role)
                archive_name = f"SPI_FLASH_ADAPTER_REMOTE_FCT/{filename}"
                if archive_name not in actual:
                    blockers.append(f"production artifact bytes missing: {role}")
                    continue
                item = archive.read(archive_name)
                if digest(item) != row.get("content_hash") or len(item) != row.get("size_bytes"):
                    blockers.append(f"production artifact identity mismatch: {role}")
            missing_roles = REQUIRED_PRODUCTION_ROLES - artifact_roles
            if missing_roles:
                blockers.append(
                    "missing production artifact roles: " + ", ".join(sorted(missing_roles))
                )
            def load_json(relative: str) -> dict[str, object]:
                value = json.loads(
                    archive.read(f"SPI_FLASH_ADAPTER_REMOTE_FCT/{relative}")
                )
                if not isinstance(value, dict):
                    raise ValueError(f"{relative} must contain an object")
                return value

            candidate = load_json("campaign/CANDIDATE_BOUNDARY.json")
            packet = load_json("campaign/PHYSICAL_VALIDATION_PACKET.json")
            handoff = load_json("handoff/REMOTE_TEST_REQUEST.json")
            gauntlet = load_json("gauntlet/GAUNTLET_STATE.json")
            criteria = load_json("campaign/ACCEPTANCE_CRITERIA.json")
            historical_bytes = archive.read(
                "SPI_FLASH_ADAPTER_REMOTE_FCT/campaign/HISTORICAL_SOURCE_PACKET.json"
            )
            historical = json.loads(historical_bytes)
            provider_plan_bytes = archive.read(
                "SPI_FLASH_ADAPTER_REMOTE_FCT/campaign/PROVIDER_TEST_PLAN.md"
            )
            expected_boundary = project_candidate_boundary(
                candidate, project_id=PROJECT_ID
            )
            expected_schemas = {
                "manifest": (manifest, CAMPAIGN_SCHEMA),
                "candidate": (
                    candidate,
                    "hardware_splicer.spi_reference_candidate.v1",
                ),
                "packet": (
                    packet,
                    "hardware_splicer.project_physical_validation_packet.v1",
                ),
                "handoff": (handoff, "hardware_splicer.remote_physical_handoff.v1"),
                "gauntlet": (
                    gauntlet,
                    "hardware_splicer.gauntlet_physical_candidate.v1",
                ),
                "criteria": (
                    criteria,
                    "hardware_splicer.spi_remote_fct_acceptance.v1",
                ),
            }
            for name, (projection, expected_schema) in expected_schemas.items():
                if projection.get("schema_version") != expected_schema:
                    blockers.append(f"{name} schema mismatch")
            for key in ("candidate_revision", "candidate_snapshot_hash"):
                values = {
                    str(manifest.get(key)),
                    str(packet.get(key)),
                    str(handoff.get(key)),
                    str(gauntlet.get(key)),
                    str(expected_boundary.get(key)),
                }
                if len(values) != 1:
                    blockers.append(f"candidate identity disagreement: {key}")
            if {
                manifest.get("campaign_id"),
                gauntlet.get("campaign_id"),
                criteria.get("campaign_id"),
            } != {CAMPAIGN_ID}:
                blockers.append("campaign identity disagreement")
            if handoff.get("handoff_id") != manifest.get("handoff_id") or handoff.get(
                "handoff_id"
            ) != gauntlet.get("handoff_id"):
                blockers.append("handoff identity disagreement")
            if handoff.get("manufacturing_artifacts") != manifest.get(
                "production_artifacts"
            ):
                blockers.append("handoff production artifacts disagree with campaign")
            if candidate.get("manufacturingArtifacts") != manifest.get(
                "production_artifacts"
            ):
                blockers.append("candidate production artifacts disagree with campaign")
            expected_packet = build_project_physical_validation_packet(
                candidate, project_id=PROJECT_ID, revision=1
            )
            if packet != expected_packet:
                blockers.append("physical packet is not the canonical candidate projection")
            expected_handoff = build_remote_physical_handoff(
                expected_packet,
                provider=handoff.get("provider") or {},
                manufacturing_artifacts=manifest.get("production_artifacts") or [],
            )
            if handoff != expected_handoff:
                blockers.append("remote handoff is not the canonical packet projection")
            if gauntlet != build_gauntlet_state(expected_packet, expected_handoff):
                blockers.append("Gauntlet projection is not the canonical closed state")
            expected_criteria = json.loads(
                (HERE / "remote_fct" / "ACCEPTANCE_CRITERIA.json").read_text()
            )
            if criteria != expected_criteria:
                blockers.append("acceptance criteria differ from the frozen campaign contract")
            if provider_plan_bytes != (
                HERE / "remote_fct" / "PROVIDER_TEST_PLAN.md"
            ).read_bytes():
                blockers.append("provider test plan differs from the frozen campaign contract")
            source_boundary = candidate.get("source_evaluation_boundary")
            if not isinstance(source_boundary, dict):
                blockers.append("candidate lacks source evaluation boundary")
            elif (
                source_boundary.get("source_packet_sha256") != digest(historical_bytes)
                or source_boundary.get("source_packet_id") != historical.get("packet_id")
                or source_boundary.get("source_candidate_revision")
                != historical.get("candidate_revision")
                or source_boundary.get("backend_candidate_synchronized") is not False
            ):
                blockers.append("historical source boundary disagreement")
            if gauntlet.get("state") != "PACKAGED_NOT_PHYSICAL" or gauntlet.get(
                "source_blind_independent_design_claim"
            ) is not False:
                blockers.append("Gauntlet truth state is invalid")
            if any(
                gauntlet.get(key) is not False
                for key in ("submitted", "ordered", "fabricated", "assembled", "powered")
            ):
                blockers.append("Gauntlet claims an unperformed physical transition")
            for projection_name, projection in (
                ("manifest", manifest),
                ("handoff.policy", handoff.get("policy") or {}),
                ("gauntlet", gauntlet),
            ):
                if (
                    projection.get("physical_correctness") != "UNPROVEN"
                    or projection.get("physical_authority_granted") is not False
                    or projection.get("authority_effect") != "none"
                ):
                    blockers.append(f"{projection_name} crosses physical authority")
            if manifest.get("production_artifact_bytes_verified") is not True:
                blockers.append("production artifact bytes not verified")
            if (
                manifest.get("manifest_self_hash_excluded") is not True
                or manifest.get("backend_candidate_synchronized") is not False
                or manifest.get("provider_status") != "proposed_not_engaged"
            ):
                blockers.append("campaign control state is invalid")
            if any(
                manifest.get(key) is not expected_value
                for key, expected_value in (
                    ("fabrication_release_ready", False),
                    ("power_on_ready", False),
                    ("physical_authority_granted", False),
                )
            ):
                blockers.append("campaign attempts an authority transition")
    except (KeyError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        blockers.append(f"invalid campaign archive: {exc}")
    return {
        "schema_version": "hardware_splicer.spi_remote_fct_campaign_audit.v1",
        "audit_pass": not blockers,
        "blockers": blockers,
        "campaign_sha256": digest(payload),
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_campaign()
    audit = audit_campaign(payload)
    if not audit["audit_pass"]:
        raise SystemExit(json.dumps(audit, indent=2, sort_keys=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
