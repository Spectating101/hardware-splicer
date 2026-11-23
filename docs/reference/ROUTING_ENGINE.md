# Capability-gated autoroute engine

**Module:** `src/hardware_splicer/routing_engine.py`

Routing turns PCB text into **candidate** PCB text for review. It never writes
into a project, never touches a revision, and never treats a routed board as
verified. Authority is never implicitly upgraded.

A later task may attach this candidate to `POST /v1/build-files/autoroute`.
This engine does not add API routes. The existing FreeRouting and tscircuit
bridges remain skip-safe opt-in tools.

## What a routed candidate is not

- **Not DRC-clean.** If DRC is run later, the report is evidence to attach, not
  approval.
- **Not fab-ready.** Placement is unchanged by contract; copper is a proposal.
- **Not a project revision.** Callers receive text. They decide whether to store
  it.

## Capability probe

`capability_probe()` returns whether the FreeRouting pipeline can run. The
result is cached for 60 seconds.

```text
{
  "available": bool,
  "reason": str | None,
  "components": {
    "kicad_python": {"ok": bool, "version": str | None, "path": str | None},
    "java": {"ok": bool, "version": str | None},
    "freerouting_jar": {"ok": bool, "path": str | None, "sha256_prefix": str | None}
  }
}
```

Each missing component yields an actionable reason, for example
`set HARDWARE_SPLICER_FREEROUTING_JAR to a FreeRouting jar`.

## Environment variables

| Variable | Meaning |
|----------|---------|
| `HARDWARE_SPLICER_KICAD_PYTHON` | Python that can `import pcbnew`. Default: `/usr/bin/python3`, then `python3`/`python` on `PATH`. The project venv is not assumed to have pcbnew. |
| `HARDWARE_SPLICER_JAVA` | Java binary. Default: `java` on `PATH`. |
| `HARDWARE_SPLICER_FREEROUTING_JAR` | Path to a FreeRouting jar. **Required.** The engine never downloads a jar. |
| `HARDWARE_SPLICER_FREEROUTING_DE_FLAG` | DSN-in flag (default `-de`) |
| `HARDWARE_SPLICER_FREEROUTING_DO_FLAG` | SES-out flag (default `-do`) |
| `HARDWARE_SPLICER_FREEROUTING_MP_FLAG` | Max-passes flag (default `-mp`) |

pcbnew work always runs in a **subprocess** of the KiCad-capable interpreter,
never in-process in the API/venv.

## Pipeline (FreeRouting)

1. Temp directory, mode `0700`.
2. Write `board.kicad_pcb`.
3. Subprocess: KiCad Python + `src/hardware_splicer/_pcbnew_helpers/export_dsn.py`
   (`pcbnew.LoadBoard`, `pcbnew.ExportSpecctraDSN`).
4. Subprocess: `java -jar $JAR -de board.dsn -do board.ses -mp <max_passes>`.
   Timeout kills the process group.
5. Subprocess: `import_ses.py` (`LoadBoard`, `ImportSpecctraSES`, `SaveBoard`).
6. Read routed text. Re-tokenize with the `kicad_diff` tokenizer. Diff against
   the input with `diff_kicad_text`. Footprints must be byte-identical as
   canonical s-expression tokens (uuid-matched, or a Counter of whole nodes when
   uuid is absent). Zones may change only `filled_polygon` / `fill_segments`.
   Segments, vias, and those zone fills may be added. Existing tracks may be
   removed only when `keep_existing_tracks` is false.

   Board-level identity is fail-closed and independent of `kicad_diff`: every
   top-level `(kicad_pcb ...)` child whose head is not in `{segment, via, zone,
   footprint, generator, generator_version, version, uuid}` must match as a
   `Counter` of canonical token sequences. A real `pcbnew.SaveBoard` rewrite
   may reformat or insert harmless nodes (`setup`, `layers`, `embedded_fonts`,
   `group`, …). That is treated as a rejection (`routing changed more than
   copper tracks`), not as an accepted candidate.

All subprocess calls are list-form, no shell, with `PATH` + `HOME=<tmpdir>`
only. Stdout/stderr are capped. Input and output PCB/SES text over 16 MiB is
refused (`HARDWARE_SPLICER_MAX_KICAD_CONTENT_BYTES` / default 16 MiB).

`route_pcb(..., engine=...)` accepts a `RoutingEngine` fake for tests.
`FreeRoutingEngine` is the real implementation.

## How to install FreeRouting (operator, not the engine)

The engine does not download anything. An operator who wants live routing:

1. Install KiCad 9 so `/usr/bin/python3` can `import pcbnew` (or set
   `HARDWARE_SPLICER_KICAD_PYTHON`).
2. Install a JRE (`java -version`).
3. Download a FreeRouting release jar from the upstream project
   (https://github.com/freerouting/freerouting/releases) into a local path.
4. `export HARDWARE_SPLICER_FREEROUTING_JAR=/path/to/freerouting.jar`.

kicad-cli 9 has no DSN export; that is why the pcbnew helpers exist.

## Safety rules

1. Routing reports a candidate. It does not promote an engineering claim.
2. A functional analogy never inherits an electrical contract; a routed board
   never inherits “verified” or “fab-ready”.
3. Exceptions (`RoutingUnavailable`, `RoutingError`) use short messages and
   never echo board text.
4. Do not reuse this module to write `apps/` or `scripts/` side effects.
