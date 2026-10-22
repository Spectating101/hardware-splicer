# External specialist engines — HS orchestration v1

HS remains the system-level device and evidence orchestrator. Existing experts
provide specialist computation. **No upstream code is copied or vendored into
HS.** Every executable is a separately installed dependency; see original
upstream licensing and distribution terms.

## Provider contract, exactly as used

| Engine | Supported source | Executed command | Evidence |
| --- | --- | --- | --- |
| SolidCraft | reviewed JSON command script | `solidcraft-cli run SOURCE --out MODEL.step --json-out RESULTS.json` | Native STEP and JSON results |
| FreeCAD | STEP, or preceding SolidCraft STEP | `FreeCADCmd GENERATED_INSPECTION.py` | STEP shape validity, volume, bounding box |
| atopile | existing reviewed `.ato` project | `ato build` in project directory | Explicit expected compiled artifacts (KiCad) |
| tscircuit | existing `.tsx/.ts` project | `tsci build` or `tsci check` in project directory | Explicit expected circuit JSON / exports |

Sources: https://docs.solidcraft.io/guide/getting-started.html ;
https://github.com/atopile/atopile ;
https://docs.tscircuit.com/category/command-line-interface ;
https://github.com/FreeCAD/FreeCAD-documentation

The first provider chain is **SolidCraft → STEP → FreeCAD inspection**.
This is actual artifact routing, not a restatement of a task list. Different
electronics DSLs are **not** interchangeable: HS will not silently translate
atopile .ato into tscircuit TSX or treat either as a substitute for native
KiCad/ERC/DRC sign-off.

## Check modules and preview (no execution)

```bash
python scripts/run_external_engine_plan.py \
  examples/external_engines/sensor_box_workflow.json \
  --workspace examples/external_engines
```

`GET /v1/external-engines` and `POST /v1/external-engines/preview` expose
availability and the contract to both engine and product APIs. **There is no
HTTP execution endpoint.**

## Opt in on a trusted local or isolated runner

Install the specialist programs separately. Review upstream licenses and
the source scripts/projects before allowing execution. For example,
`solidcraft-cli`, `FreeCADCmd`, `ato`, and `tsci` each run different
code and may have optional network access. Merely listing a program does
not mean the binary was verified or installed.

```bash
python scripts/run_external_engine_plan.py \
  examples/external_engines/sensor_box_workflow.json \
  --workspace examples/external_engines \
  --out /tmp/hs-external-engine-run \
  --execute
```

The example's 85 × 55 × 25 mm SolidCraft model is a **bounding envelope solid**,
not a hollow injection-molded case. FreeCAD computes its shape bounds.
Neither validates material, wall thickness, board standoffs, connector openings,
thermal conditions or actual physical fit.

For atopile / tscircuit, point a task at an existing reviewed `.ato` or
`.tsx` entrypoint and specify artifact paths the native project is expected
to generate. HS does **not** synthesize valid atopile/TSX code from a
plain-language prompt yet. Successful execution alone is not accepted:
required files must be nonempty and are SHA-256 recorded.

## Report and release authority

`ENGINE_ORCHESTRATION_REPORT.json` records the exact approved plan digest,
provider identity, task dependency status, exit code, bounded diagnostics, and
artifact paths, sizes and content hashes. A failed/missing provider blocks only
its task and dependent tasks; unrelated tasks may still run.

The runner requires `--execute`, is **local only**, accepts only a fixed
command allowlist, rejects absolute/traversing input file paths, rejects
unknown task keys, limits execution time, checks declared outputs and never
silently falls back between incompatible DSLs. It does not provide process-level
sandboxing; for untrusted third-party projects use an isolated container or
machine with network restrictions and least-privilege filesystem access.

Every report preserves `fabrication_authorized`, `power_on_authorized` and
`release_authorized` as false. An apparently valid STEP or KiCad file is
not an independently validated, manufacturable, physically tested device.

## Scope of verification

- **Tested:** Python plan validation, provider discovery, mocked executable
  contracts and chained SolidCraft→FreeCAD artifact transfer, dependency failure
  propagation, API preview security and artifact hashing.
- **Native evidence confirmed:** pinned SolidCraft 0.18.4 actually exported
  an 85 × 55 × 25 mm STEP solid, and headless FreeCAD independently accepted
  it as one valid positive-volume solid. Two native tasks passed, with
  volume 116,875 mm³. See GitHub Actions run 39744814099.
- **Native electronics evidence currently blocked:** a real tsci build ran
  and emitted Circuit JSON but rejected a wrong LED polarity assumption in
  the originally authored sample. It correctly failed rather than conferring
  false engineering success. A neutral passive fixture and electrical
  identity import gate have been committed; final native smoke pending.
- **Not yet claimed:** successful real atopile compiler execution, successful
  real tsci→HS electrical import on the new fixture, manufacturer-authenticated
  materials, a verified enclosure with standoffs, or physical device operation.
- **Future:** Pin tested provider versions, add native integration CI smoke
  and expose linked outputs in the retained project evidence graph after
  verifying lineage, authorization and upstream output schemas.
