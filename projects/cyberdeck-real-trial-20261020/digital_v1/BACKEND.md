# Reproduce this device through the HS backend

The `fielddeck-7` case executes the CAD author, calculation model, render and independent exported-file verifier. It uses the shared project revisions, jobs, comparison, audit and ZIP export services. It is a bounded registered case, with a fixed authored module layout and explicit numeric study goals.

From the Hardware-Splicer repository, use `hs-digital cases` to inspect supported keys. `hs-digital init --case fielddeck-7` builds a fresh baseline and returns its project ID. Supply the same `--project-root` and `--jobs-db` options for all commands if overriding their defaults.

To study heavier work and a longer runtime target, save a JSON file:

```json
{"pi_work_current_a": 1.8, "minimum_work_runtime_h": 3}
```

Run `hs-digital revise PROJECT_ID --base-revision 1 --requirements changes.json`. Then use `compare PROJECT_ID --before 1 --after 2`, `audit PROJECT_ID --revision 2 --native`, and `export PROJECT_ID output.zip --revision 2` with the same CLI. A completed computation can preserve an intact design that misses its goals; the `requirements_met` field and failed constraints make that explicit. The failed-target `revise` command exits 2. Export refuses to replace an existing file.

Runtime and supply margin, case width/depth/height limits, printer-bed X/Y targets and Pi/keyboard load assumptions are supported. Geometry edits outside the fixed layout require a separately authored design change. Thermal acceptance, real cable routing, physical fits and ARM boot remain unvalidated.

The backend ZIP's entry point is `STUDY_README.md`. It includes only the frozen sources and generated artifacts needed for that study. The standalone package also contains optional HS source-import/material-history records. Both workflows use the same native device scripts; no browser, frontend or model-provider credential is needed to rerun them.
