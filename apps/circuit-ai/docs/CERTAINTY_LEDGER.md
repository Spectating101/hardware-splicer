# Evidence Certainty Ledger

The certainty ledger is the scan engine's truth boundary. It turns detections,
OCR markings, board-role inference, topology, defects, AOI checks, and salvage
opportunities into auditable claims.

## What It Adds

Every `/analyze` result now includes:

```json
{
  "certainty_ledger": {
    "overall": {
      "score": 0.398,
      "level": "possible",
      "summary": "The scan can suggest directions, but key claims need more evidence.",
      "claim_boundary": "Claims are evidence-weighted scan conclusions, not proof..."
    },
    "items": [],
    "missing_evidence": [],
    "next_actions": [],
    "training_queue": {
      "should_capture": true,
      "reasons": [],
      "candidate_labels": []
    },
    "counts": {
      "certain": 0,
      "likely": 0,
      "possible": 0,
      "unknown": 0,
      "total": 0
    }
  }
}
```

Each item states:
- the claim type, such as component, marking, board role, connector, topology,
  defect, AOI, or salvage
- the certainty level and numeric score
- the evidence used
- missing evidence
- next actions
- where the claim can be used, such as repair, salvage, splicing, AOI, or
  training

## Certainty Levels

- `certain`: strong evidence for operator-confirmed planning.
- `likely`: useful for repair, salvage, and next-action planning.
- `possible`: directional only; collect more evidence before acting.
- `unknown`: not reliable enough for action.

These are not magic truth labels. They are operational gates. A board can have a
useful possible result if it tells the operator exactly what to capture next.

## How To Use It

For repair:
- Start with likely or certain fault/defect/board-role claims.
- If the ledger asks for voltage, continuity, or current-limited startup data,
  collect that before replacing parts.

For salvage and splicing:
- Use likely component, marking, connector, and functional-block claims to choose
  candidate modules.
- Do not power or splice modules until pinout, polarity, rails, and isolation are
  verified.

For production AOI:
- Treat `pilot_ready` AOI as a planning state unless the ledger also has golden,
  reference, topology, and scan-quality evidence.
- Missing golden/reference evidence means the result is not a production release
  gate yet.

For training:
- If `training_queue.should_capture` is true, save the image/crop after operator
  review.
- `candidate_labels` are the labels worth turning into detector, OCR, defect, or
  functional-block examples.

## Live Check

With the dev server running:

```bash
curl -s -X POST http://127.0.0.1:8010/analyze \
  -H 'Authorization: Bearer dev' \
  -F 'file=@assets/samples/test_pcb.png' \
  -F 'backend=hybrid' \
  -F 'enable_ocr=false'
```

The Next proxy exposes the same payload through:

```bash
curl -s -X POST http://127.0.0.1:3000/api/proxy/analyze \
  -F 'file=@assets/samples/test_pcb.png' \
  -F 'backend=hybrid' \
  -F 'enable_ocr=false'
```

The scan UI shows the ledger as Evidence certainty, Missing evidence, and Next
actions.
