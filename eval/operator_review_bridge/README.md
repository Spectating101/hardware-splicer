# Provider-neutral engineering review bridge

The `hardware_splicer.operator_review_bridge` module accepts an injectable
`operator(prompt)` function. It first computes HS's independent engineering
analysis, then provides the returned findings and declared intake to a
model for advisory interpretation. A Copilot CLI adapter is provided as a
temporary Optiplex proof of concept; any future LLM provider can implement
the same interface without rewriting HS's engineering analysis.

## Live integration proof, October 20, 2026

Input: `eval/source_agnostic_pilot/public_drv8833_donor_motion_repair.json`
(using its `intake` object). The model was invoked with read-only/no-tool
Copilot arguments. The result was `operator_status=reviewed`,
`decision=hold`, `physical_authority=not_authorized`. HS independently
identified blocking current-margin and actuator-torque findings. Copilot
produced suggested measurements and a technical explanation without claiming
measurements had been taken. The transient raw run result was saved under
`/tmp/hs_operator_bridge_live_20261020.json` on Optiplex; no account tokens
or generated transcripts were committed.

## Repeat

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
import json
from pathlib import Path
from hardware_splicer.operator_review_bridge import review_engineering_case, copilot_text_operator
intake=json.loads(Path('eval/source_agnostic_pilot/public_drv8833_donor_motion_repair.json').read_text())['intake']
result=review_engineering_case(intake, operator=copilot_text_operator)
print(json.dumps(result,indent=2))
PY
```

## Safety and interpretation

The operator is **advisory only**, and may neither set release status nor
write measurement evidence. HS's deterministic analysis always has final
precedence. Malformed, unavailable, timed-out or fabricated-measurement model
answers fail closed. `physical_authority` remains `not_authorized` in all
cases—even when engineering checks are nonblocking—because this bridge is a
review tool, not a release workflow.

Limitations: no live vendor-document fetching, no full source-graph review,
no model-generated engineering artifact compilation, no physical testing,
no autonomous tool loop. The bridge supports one model analysis pass over an
HS-generated analysis packet, not unrestricted repair or fabrication.
