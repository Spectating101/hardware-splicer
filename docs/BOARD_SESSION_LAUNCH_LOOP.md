# Board Session Launch Loop

Circuit-AI is now structured around board-in-hand sessions rather than one-shot
image answers.

## Launch Workflow

1. Start a case from `/start`.
2. The scan and context create a persistent board session.
3. The certainty ledger becomes open evidence tasks.
4. The operator adds follow-up captures, measurements, and outcomes in
   `/review`.
5. Reviews or corrections resolve the remaining evidence tasks.
6. Reviewed sessions export training packages.
7. The benchmark report tracks whether the product is becoming useful enough to
   launch.

## Normal Capture Budget

The default target is 2-6 evidence items:

- front photo
- back photo when traces/components require it
- 1-3 closeups for IC markings, connector labels, defects, or board labels
- optional voltage/continuity/current measurements when repair or splice safety
  depends on them

The system should ask for more only when a deeper mode is selected, such as
reverse engineering, production AOI, or a safety-critical repair.

## API Surface

- `GET /board-sessions`
- `POST /board-sessions`
- `POST /board-sessions/from-scan`
- `GET /board-sessions/review-queue`
- `GET /board-sessions/benchmark`
- `GET /board-sessions/aoi-calibration`
- `GET /board-sessions/{session_id}`
- `GET /board-sessions/{session_id}/evidence-graph`
- `GET /board-sessions/{session_id}/dossier`
- `POST /board-sessions/{session_id}/captures`
- `POST /board-sessions/{session_id}/review`
- `POST /board-sessions/{session_id}/measurement`
- `POST /board-sessions/{session_id}/outcome`
- `POST /board-sessions/{session_id}/training-export`

The local store defaults to:

```text
data/board_sessions/sessions.json
```

Training exports are written under:

```text
data/board_sessions/training_exports/
```

Follow-up evidence files are written under:

```text
data/board_sessions/{session_id}/evidence/
```

## Live Smoke Test

Start the API, then run:

```bash
TEST_API_KEYS=dev python3 -m uvicorn src.api.v1.main:app --host 127.0.0.1 --port 8010
scripts/smoke_board_session_workflow.py --base-url http://127.0.0.1:8010 --api-key dev
```

The smoke test creates a session from a real sample image, adds follow-up
evidence, logs a measurement, reviews a task, records an outcome, exports a
training package, and prints the benchmark summary.

## Launch Benchmark

The benchmark endpoint tracks:

- session count
- open and resolved evidence tasks
- review completion
- average capture burden per session
- training export count
- useful session count
- launch readiness score

The AOI calibration endpoint tracks:

- production AOI cases with operator-recorded actual pass/fail status
- false accepts, false rejects, release precision, and release recall
- recurring gate blockers and recommended profile patches
- next actions before loosening or tightening automatic release thresholds

The evidence graph endpoint turns a board session into source nodes, claim
nodes, support edges, weak claims, grounded claims, and next grounding actions.
Use it when a scan or repair/AOI result needs to explain exactly what evidence
supports each claim.

The dossier endpoint packages the same evidence into an operator-facing board
brief: identity, AOI state, component counts, repair/reuse summary, grounded
claims, weak claims, open tasks, and next actions. The review page links each
session to `/dossier/{session_id}`.

Pilot target:

- 50 real sessions
- review completion above 60%
- average capture burden at or below 6
- at least 5 training exports
- at least 10 outcomes with time saved or value recovered

Paid beta target:

- 150 real sessions
- review completion above 75%
- 5 repeat users/operators
- 20 measured value/time-saving cases

## Competitive Measurement

Compare against reverse-engineering, AOI, and repair-assistant tools on:

- time to useful answer
- capture burden
- certainty honesty and missing-evidence quality
- part/marking correction rate
- review-to-training throughput
- measured repair/salvage/resale value

Circuit-AI should win by being the best lightweight board-in-hand evidence
workflow, not by claiming universal circuit truth from one photo.
