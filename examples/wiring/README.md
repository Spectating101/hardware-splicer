# HS-3G-B receiver harness: digital review

This continues the existing digital drone's retained UART1/CRSF assignment. It does not introduce a new device, select a replacement controller or establish physical compatibility. The [specification](hs3g_b_receiver.json) expands the receiver row in [WIRING.csv](../drone_proving_ground/revision_b/reference/WIRING.csv) into four explicit conductors, using pad names checked against the manufacturer diagrams:

| Flight controller | RadioMaster RP1 V2 |
| --- | --- |
| T1 | RX |
| R1 | TX |
| nominal 5V | nominal 5V |
| G | G |

The [source notes](hs3g_b_receiver_sources.json) record the inspected manuals and their hashes. On the FC component side with USB-C at right, the selected T1/R1 pads are near the DJI connections. Use the separate 5V/G pads directly above them; the nearby 9V pad is not selected. The manual's default ELRS diagram uses UART2, while this project's retained firmware assignment keeps the receiver on UART1 and GPS on UART2. No firmware assignment was changed.

The RP1 manual's top view identifies RX/TX/5V/G, but its pictured PCB is V1.2 and matching the selected RP1 V2 physical revision remains unresolved. Supply tolerances, receiver current, signal thresholds and exact wire selection also remain unresolved. The FC's 2A 5V nameplate is a shared regulator budget, not a measured per-pad guarantee. Each **0.10 m** conductor is a provisional design allowance, not a routed CAD length or a measured cut instruction. Wire colors and gauge are unspecified. These are selected solder pads, not numbered connector positions or a complete connector/contact/crimp BOM.

The new engine actually produced the [cut-list draft](../../docs/status/generated/hs3g-b-receiver-wiring-2026-11-17.csv) and a [native WireViz drawing](../../docs/status/generated/hs3g-b-receiver-wiring-2026-11-17.svg) on the previously saved digital drone. Its result is **unresolved**, with 24 explicit issues. The discontinued controller sourcing issue remains open. The existing design revision and simulation study were checked before and after and remained identical. No parts were bought, owned, fabricated, flashed or energized.

To use the example on an existing project, prepare a fresh material assessment on the current revision. Preserve the bundled allowance and add a separate provisional conductor line; the original allowance still covers unitemized accessories and remains an open issue:

```python
from datetime import datetime, timezone
import json
from pathlib import Path
from hardware_splicer.sdk import assess_materials, assess_wiring, export_wiring

project_id = "YOUR_EXISTING_PROJECT"
project_root = "/tmp/hs-projects"
revision = 1  # use the actual current revision
harness = json.loads(Path("examples/wiring/hs3g_b_receiver.json").read_text())
requirements = json.loads(Path("examples/materials/hs3g_b_requirements.json").read_text())
requirements.append({
    "material_id": "receiver_conductors",
    "description": "Four provisional receiver conductors; exact wire not selected",
    "specification": harness["wires"][0]["contract"]["specification"],
    "quantity": "0.40", "unit": "m",
    "source_ref": "examples/wiring/hs3g_b_receiver.json",
    "unresolved": ["Wire identity and ratings unresolved; lengths provisional."],
})
materials = assess_materials(project_id, project_root=project_root,
    expected_revision=revision, requirements=requirements,
    inventory={"source": "declared", "captured_at": datetime.now(timezone.utc).isoformat(), "lots": []})
wiring = assess_wiring(project_id, project_root=project_root,
    expected_revision=revision,
    material_assessment_id=materials["assessment"]["assessment_id"],
    specification=harness, render=False)
with Path("new-receiver-review.zip").open("xb") as output:
    output.write(export_wiring(project_id, wiring["assessment"]["assessment_id"],
                               project_root=project_root))
```

Set `render=True` after configuring the optional local WireViz CLI and Graphviz to include the SVG and native BOM. See [ENGINE.md](../../docs/ENGINE.md#project-wiring-and-harness-review) for the headless CLI, source-binding format, electrical check scope and API routes. The inline contracts are manually extracted declarations, not contracts registered in the original digital project's source snapshot. They remain flagged as unbound. The external manual hashes in the source notes preserve the review basis without modifying that project's revision history or asserting physical validation. A digital-project evidence attachment workflow compatible with the frozen simulation snapshot is still needed to bind new contract sources there; the current generic ingestion route advances the project revision.
