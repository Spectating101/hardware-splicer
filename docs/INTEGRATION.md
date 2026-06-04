# Hardware-Splicer Integration

This dump currently keeps three apps as separate runtimes:

- `apps/circuit-ai`: electronics and machine-system analysis.
- `apps/mecha-splicer`: mechanical bundle generation from mechanism/electronics specs.
- `apps/3d-splicer`: optional CadQuery/STL service for PCB-style enclosures.

## Runtime Flow

1. Circuit-AI compiles board, interconnect, power, and actuation context.
2. Circuit-AI calls Mecha-Splicer through `run_mecha_bridge()`.
3. Mecha-Splicer writes a bundle containing OpenSCAD, BOM, DFM, simulation, control, and safety artifacts.
4. When `use_3d_splicer=true`, Mecha-Splicer calls 3D-Splicer over HTTP for CadQuery script or STL generation.

## Configuration

- `MECHA_SPLICER_ROOT`: optional absolute path to `apps/mecha-splicer`. If unset, Circuit-AI discovers both the old standalone `Mecha-Splicer` sibling layout and the consolidated `apps/mecha-splicer` layout.
- `SPLICER_API_URL`: base URL for 3D-Splicer, default `http://127.0.0.1:8000` in Mecha-Splicer and `http://localhost:8000` in Circuit-AI's direct client.
- `SPLICER_ENDPOINT`: primary 3D-Splicer endpoint for Circuit-AI's direct client, default `/v1/splice`.
- `SPLICER_SCRIPT_ENDPOINT`: optional script-only fallback endpoint. If unset, `/v1/splice` maps to `/v1/splice/script` and `/generate` maps to `/generate/script`.
- `SPLICER_TIMEOUT_S`: timeout for Circuit-AI direct HTTP calls to 3D-Splicer, default `30`.
- `HARDWARE_SPLICER_OUTPUT_ROOT`: API output root, default `/tmp/hardware_splicer_api`.
- `HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR`: set to `1` only for trusted local development if the API should write outside `HARDWARE_SPLICER_OUTPUT_ROOT`.
- `HARDWARE_SPLICER_MAX_BOARD_FILE_BYTES`: maximum board design file size accepted by top-level spec validation, default `52428800`.
- `HARDWARE_SPLICER_STATE_DIR`: root for persistent API state, default `/tmp/hardware_splicer_state`.
- `HARDWARE_SPLICER_JOB_DB`: SQLite job database path, default `$HARDWARE_SPLICER_STATE_DIR/jobs.sqlite3`.
- `HARDWARE_SPLICER_JOB_WORKERS`: in-process async compile workers, default `1`.
- `HARDWARE_SPLICER_JOB_POLL_INTERVAL_S`: worker polling interval, default `0.2`.
- `HARDWARE_SPLICER_REQUEUE_INTERRUPTED_JOBS`: set to `1` to requeue jobs that were `running` when the backend restarted; by default they are marked failed to avoid silent partial-output reuse.

## Production Surface

- Specs are validated before expensive Circuit-AI/Mecha-Splicer work starts.
- API compile outputs are rooted under `HARDWARE_SPLICER_OUTPUT_ROOT` by default.
- Every compile has a `request_id`, `generated_at`, `MANIFEST.json`, and `BUILD_METADATA.json`.
- `POST /v1/jobs` persists compile jobs in SQLite and runs them through a bounded background worker.
- `GET /v1/jobs/{job_id}`, `/result`, `/artifacts`, and `/bundle` expose durable job state and downloadable outputs.
- `POST /v1/jobs/{job_id}/retry` reruns terminal jobs; `POST /v1/jobs/{job_id}/cancel` cancels queued jobs.
- Reusing the same `request_id` on `POST /v1/jobs` is idempotent and returns the existing job record.
- Jobs that were `running` during a backend restart are recovered on startup.
- Managed 3D-Splicer startup failures include service output tail when available.
- `python3 scripts/hardware_splicer.py validate --spec ...` and `POST /v1/validate` provide CI-safe validation without starting the compile chain.
- `python3 scripts/hardware_splicer.py doctor --json` and `GET /v1/status` expose root/dependency status.

## Contract Checks

- Circuit-AI to Mecha-Splicer is covered by `apps/circuit-ai/tests/unit/test_hardware_splicer_integration.py`.
- Mecha-Splicer to 3D-Splicer payload shape is covered by `apps/mecha-splicer/tests/test_splicer3d_payload.py`.
- Canonical bundle compiler: `python3 scripts/hardware_splicer.py demo --out /tmp/hardware_splicer_demo`.
  - The demo spec uses `examples/main_ctrl_esp32_servo.net`, so controller identity, USB-UART programming, servo outputs, and power connectors come from extracted board evidence.
  - The expected current status is `sim_ready`; remaining findings should be actionable engineering warnings, not intake blockers.
  - `--render-stl` may report `script_fallback` when CadQuery is unavailable, while still extracting `splicer3d_script.py`.
- Compiler API: `python3 scripts/hardware_splicer.py serve --port 8090`, then `POST /v1/compile`.
- Package shortcuts: `make demo`, `make smoke`, `make test`, `make test-apps`.
- Full local chain smoke: `python3 scripts/hardware_splicer_e2e.py`.
- Pytest wrapper for the full chain: `cd apps/circuit-ai && pytest -q tests/integration/test_hardware_splicer_e2e.py`.
- 3D-Splicer template packaging is covered by the install smoke command used during this cleanup.
