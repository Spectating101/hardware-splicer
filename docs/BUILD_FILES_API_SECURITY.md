# Build-files API security (`/v1/build-files/*`)

**Purpose:** The build-files endpoints are a **bounded local file viewer** for compile outputs. This doc defines the trust boundary.

**Applies to:** `v1.1-interface-preview` on `main` (not tagged `v1.0.2`).

---

## Threat model

| Risk | Mitigation |
|------|------------|
| Read arbitrary server paths via `build_dir` | `resolve_build_dir()` requires directory under `HARDWARE_SPLICER_OUTPUT_ROOT` unless dev override |
| Path traversal via `relative` | Reject `..` in path parts; resolve + `relative_to(build_dir)` |
| Serve unexpected file types | Allow-list suffixes on download/artifact read |
| Read huge files (DoS) | `HARDWARE_SPLICER_MAX_BUILD_FILE_BYTES` (default 8 MiB); KiCad content cap 16 MiB |
| Leak secrets from unrelated dirs | Output-root allow-list (same as compose `out_dir` policy) |

---

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `HARDWARE_SPLICER_OUTPUT_ROOT` | `/tmp/hardware_splicer_api` | Primary allowed root for `build_dir` |
| `HARDWARE_SPLICER_BUILD_FILE_ROOTS` | (empty) | Extra allowed roots (`:`-separated on Unix) |
| `HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR` | `0` | Set `1` for trusted local dev (allows any existing `build_dir`) |
| `HARDWARE_SPLICER_MAX_BUILD_FILE_BYTES` | `8388608` | Max download/artifact size |
| `HARDWARE_SPLICER_MAX_KICAD_CONTENT_BYTES` | `16777216` | Max inline KiCad text served to KiCanvas |

---

## Allowed suffixes

**KiCanvas content:** `.kicad_pcb`, `.kicad_sch`, `.kicad_pro`

**Download / artifact:** above + `.json`, `.csv`, `.md`, `.txt`, `.zip`, `.net`, `.pdf`, `.svg`, `.png`

---

## Implementation

- `src/hardware_splicer/build_files_security.py` — root + size guards
- `src/hardware_splicer/build_files.py` — calls guards in `resolve_build_dir`, `read_build_file`, `read_artifact_file`
- `tests/test_build_files_security.py` — traversal + out-of-root rejection

---

## Operations guidance

**Production / pilot hosts:** leave `HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR` unset. Run API with a dedicated output root.

**Developer laptop:** may set `HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1` when pointing the UI at ad-hoc compile dirs.

---

*Review this doc before any build-files endpoint expansion.*
