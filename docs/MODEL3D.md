# 3D model views of retained PCB revisions

Hardware Splicer can serve a GLB of a retained PCB revision so the web UI can
show a 3D tab next to Schematic and PCB. Generation is server-side
(`kicad-cli pcb export glb`). The bytes come from the content-addressed
artifact store — never from a live build directory.

**Authority is never implicitly upgraded.** A rendered model is a *view* of
retained bytes. Generating or serving it changes no snapshot, revision,
review, thread, artifact pin, or engineering claim.

## What is generated, and from which bytes

`GET /v1/projects/{id}/revisions/{revision}/model3d` and
`GET /v1/projects/{id}/revisions/{revision}/model3d/glb` read the pinned PCB
through `read_pinned_artifact`. If the revision has no retained PCB, the JSON
route returns HTTP 200 `{ok:true, available:false, reason:"no retained pcb"}`
and the binary route returns `404 {detail:{type:"not_found",…}}`. That is not
an engineering error.

The PCB text is written to a mode-700 temp directory as `board.kicad_pcb`.
`kicad-cli` runs with a minimal environment (`PATH` plus `HOME` set to that
temp dir) so KiCad writes no config into the user home.

## Defaults and flags

Flags were taken from `kicad-cli pcb export glb --help` (KiCad 9.0.2) and are
the documented defaults:

```text
kicad-cli pcb export glb
  --output <tmp>/board.glb
  --force
  --subst-models
  --include-tracks
  --include-pads
  --include-zones
  --include-silkscreen
  --include-soldermask
  board.kicad_pcb
```

`--subst-models` swaps VRML for same-name STEP/IGS when present. Tracks,
pads, zones, silkscreen, and soldermask are included; inner copper, origin
overrides, board-only, and net filters stay off. The binary path is
`HARDWARE_SPLICER_KICAD_CLI` or `shutil.which("kicad-cli")`. pcbnew is not
used.

## Cache

Models are content-addressed by the retained PCB blob sha256 plus an options
fingerprint of the default flags:

```text
projects/<id>/models/<pcb_hex[:2]>/<pcb_hex>-<optfp8>.glb
projects/<id>/models/<pcb_hex[:2]>/<pcb_hex>-<optfp8>.json
```

Writes use `mkstemp` + `fsync` + `os.replace` in the cache directory. The
previous pair is never unlinked first: the GLB is installed, then the sidecar.
A sidecar install failure leaves the prior pair or a hash mismatch that
regenerates. The sidecar records `sha256` of the GLB; a read verifies it.
Symlinked cache paths are not followed. Two uncached `kicad-cli` runs of the
same PCB can differ by an embedded export timestamp; the cached object for a
PCB digest plus options fingerprint is stable.

## Limits

| Limit | Value |
|-------|--------|
| Generation timeout | 60s (`killpg` on the `Popen` session, then reap) |
| Maximum GLB | 64 MiB |
| Captured stdout/stderr in errors | 2 KiB (never PCB file text) |
| Capability probe | `kicad-cli --version`, cached 60s |

The result must start with GLB magic `glTF`, version 2, and a header length
that matches the file.

## Failure modes

| Condition | JSON `/model3d` | Binary `/model3d/glb` |
|-----------|-----------------|------------------------|
| Project or revision missing | `404` `not_found` | `404` `not_found` |
| No retained PCB | `200` `available:false` `no retained pcb` | `404` `not_found` |
| kicad-cli missing | `200` `available:false` with install reason | `404` `not_found` |
| Nonzero exit, timeout, empty/garbage/truncated/oversize GLB | `502` `model3d_error` | `502` `model3d_error` |
| Tampered cache | regenerate once, then `502` | same |
| Concurrent requests for the same PCB+options | one `kicad-cli` spawn (per-key lock) | same |

Successful binary responses use `media_type` `model/gltf-binary`,
`ETag: "sha256:<hex>"`, and `Cache-Control: private, max-age=3600`.
`If-None-Match` matching that ETag returns `304`.

## Related

- [`ARTIFACT_RETENTION.md`](ARTIFACT_RETENTION.md) — retained bytes this view reads
- [`MACHINE_PROJECT_SPINE.md`](MACHINE_PROJECT_SPINE.md) — revisions are immutable
- `src/hardware_splicer/model3d.py`
- `src/hardware_splicer/project_model3d_api.py`
