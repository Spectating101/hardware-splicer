"""Source-bound HS machine visualization via upstream Teardown's actual runtime.

The output is a 3D, offline, interactive analytic-geometry explainer, NOT
a kinematics, pressure, structural or physically approved simulation.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .multicad_toolchain import validate_manifest, check_native_outputs, canonical, digest, require

SCHEMA = "hardware_splicer.teardown_interactive_product.v1"


def _read(path: Path) -> dict:
    value = json.loads(path.read_text())
    require(isinstance(value, dict), "invalid JSON evidence " + path.name)
    return value


def source_model(multicad: Path) -> dict:
    root = Path(multicad)
    manifest = validate_manifest(root)
    evidence = check_native_outputs(root)
    partcad = _read(root / "PARTCAD_EXECUTION_RECEIPT.json")
    log = (root / "PARTCAD_CLI.log").read_bytes()
    require(
        partcad.get("schema_version") == "hardware_splicer.partcad_package_receipt.v1"
        and partcad.get("source_spec_sha256") == manifest["source_spec_sha256"]
        and partcad.get("native_partcad_cli_ran") is True
        and partcad.get("native_cad_part_count") == len(manifest["parts"])
        and partcad.get("fabrication_authorized") is False
        and partcad.get("all_native_parts_manufacturer_qualified") is False
        and digest(log) == partcad.get("partcad_log_sha256"),
        "missing actual same-revision PartCAD execution and provenance",
    )
    by_id = {p["id"]: p for p in evidence["parts"]}
    parts = []
    for row in manifest["parts"]:
        p = by_id[row["id"]]
        parts.append({
            "id": row["id"], "shape": row["shape"],
            "extents_mm": p["dimensions_mm"],
            "authored_step_sha256": p["authored_step_sha256"],
            "reference_step_sha256": row["reference_sha256"],
            "source_status": "analytic_concept_geometry_only",
        })
    return {
        "schema_version": SCHEMA,
        "product_id": manifest["product_id"],
        "source_spec_sha256": manifest["source_spec_sha256"],
        "geometry_basis": "source-bound independent CadQuery/build123d STEP dimension parity",
        "parts": parts,
        "physical_kinematics_verified": False,
        "physical_fit_verified": False,
        "operating_performance_verified": False,
        "fabrication_authorized": False,
    }


def export(multicad: Path, output: Path) -> dict:
    model = source_model(multicad)
    out = Path(output)
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "refusing to overwrite an existing Teardown machine")
    machine = out / "machine"
    machine.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parents[2] / "assets/teardown/hs_machine_main.js"
    require(source.is_file(), "HS Teardown source adapter absent")
    template = source.read_text()
    token = "__HS_TEARDOWN_MODEL_JSON__"
    require(template.count(token) == 1, "invalid native Teardown JS template")
    encoded = json.dumps(model, sort_keys=True, ensure_ascii=True, allow_nan=False).replace("</", "<\\/")
    (machine / "main.js").write_text(template.replace(token, encoded))
    studio_source=source.parent / "hs_product_studio.js"
    require(studio_source.is_file(), "native HS studio stage module missing")
    (machine/"hs_product_studio.js").write_bytes(studio_source.read_bytes())
    (out / "TEARDOWN_INPUT.json").write_bytes(canonical(model))
    receipt = {
        "schema_version": "hardware_splicer.teardown_export_receipt.v1",
        "source_spec_sha256": model["source_spec_sha256"],
        "native_html_built": False,
        "native_browser_run": False,
        "machine_source_sha256": digest((machine/"main.js").read_bytes()),
        "studio_source_sha256": digest((machine/"hs_product_studio.js").read_bytes()),
        "input_sha256": digest((out/"TEARDOWN_INPUT.json").read_bytes()),
        "physical_release_authorized": False,
    }
    (out / "TEARDOWN_EXPORT_RECEIPT.json").write_bytes(canonical(receipt))
    return receipt


def validate_native_browser(output: Path) -> dict:
    """Verify a completed, independent Playwright browser gate; reject fake claims.

    The JS browser harness must run independently and generate its screenshot,
    success JSON and inspected/offline HTML before we sign this receipt.
    """
    root = Path(output)
    source = _read(root/"TEARDOWN_INPUT.json")
    receipt = _read(root/"TEARDOWN_EXPORT_RECEIPT.json")
    proof = _read(root/"BROWSER_PROOF.json")
    html = root/"dist"/"machine.html"
    screenshot = root/"viewer.png"
    require(
        source.get("schema_version") == SCHEMA
        and source.get("source_spec_sha256") == receipt.get("source_spec_sha256")
        and receipt.get("input_sha256") == digest((root/"TEARDOWN_INPUT.json").read_bytes())
        and receipt.get("machine_source_sha256") == digest((root/"machine/main.js").read_bytes())
        and receipt.get("studio_source_sha256") == digest((root/"machine/hs_product_studio.js").read_bytes())
        and receipt.get("native_html_built") is False
        and receipt.get("native_browser_run") is False
        and receipt.get("physical_release_authorized") is False,
        "source or export receipt mutated",
    )
    require(html.is_file() and html.stat().st_size > 10000, "native Teardown offline HTML missing")
    raw = html.read_bytes()
    require(raw.lstrip().startswith(b"<!doctype html") and b"<script type=\"module\">" in raw,
            "Teardown did not produce the expected inlined application")
    require(source["source_spec_sha256"].encode() in raw,
            "generated offline HTML lost source revision binding")
    require(not any(x in raw.lower() for x in (b'<script src="http', b'<link href="http',
                                           b'<iframe', b'network.fetch(')),
            "unsupported remote script, CSS or frame dependency")
    require(screenshot.is_file() and screenshot.stat().st_size > 5000,
            "no actual rendered browser screenshot")
    require(proof.get("source_spec_sha256") == source["source_spec_sha256"]
            and proof.get("product_id") == source["product_id"]
            and proof.get("part_count") == len(source["parts"])
            and proof.get("native_browser_rendered") is True
            and proof.get("interactive_explode") is True
            and proof.get("selected_part") is True
            and proof.get("section_view") is True
            and proof.get("isolate_part") is True
            and proof.get("no_network_requests") is True
            and proof.get("no_browser_errors") is True
            and proof.get("assembled_first") is True
            and proof.get("guided_stages_operable") is True
            and proof.get("full_screen_cad_visible") is True
            and isinstance(proof.get("visible_cad_colored_samples"), int)
            and proof["visible_cad_colored_samples"] >= 400
            and isinstance(proof.get("css_canvas_height_px"), (int, float))
            and proof["css_canvas_height_px"] >= 600
            and proof.get("physical_simulation_verified") is False
            and proof.get("html_sha256") == digest(raw)
            and proof.get("screenshot_sha256") == digest(screenshot.read_bytes()),
            "browser proof incomplete or wrong source/output")
    passed = {
        "schema_version": "hardware_splicer.teardown_native_acceptance.v1",
        "source_spec_sha256": source["source_spec_sha256"],
        "product_id": source["product_id"],
        "native_runtime": "elvarofficial/teardown (pinned upstream source)",
        "native_browser_executed": True,
        "native_html_sha256": digest(raw),
        "native_screenshot_sha256": proof["screenshot_sha256"],
        "parts_verified": len(source["parts"]),
        "visual_exploded_inspection": True,
        "assembled_first_hero_and_guided_stages": True,
        "actual_cad_pixels_observed": proof["visible_cad_colored_samples"],
        "real_mechanism_or_physics_verified": False,
        "real_equipment_operated": False,
        "physical_release_authorized": False,
    }
    (root/"TEARDOWN_NATIVE_ACCEPTANCE.json").write_bytes(canonical(passed))
    return passed
