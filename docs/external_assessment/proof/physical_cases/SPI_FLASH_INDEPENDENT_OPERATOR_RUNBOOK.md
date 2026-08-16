# SPI Flash Adapter — Independent Operator Runbook

**Status:** prepared for execution. This document defines usability/safety evidence collection, not an expected circuit solution.

## Goal

Test whether a technically competent outsider can use Hardware-Splicer on a bounded real hardware-preparation task while the evidence/authority architecture prevents unjustified confidence.

## Operator eligibility

The operator should:

- not have authored the candidate design or hidden evaluator logic;
- have enough electronics familiarity to safely follow bench procedures;
- not have access to golden answers, hidden tests, evaluator conclusions, or unpublished design rationale;
- use only product-visible documentation, artifacts, and allowed bench equipment.

Record prior experience in broad bands rather than treating expertise as binary.

## Allowed materials

- Hardware-Splicer UI/CLI/API surfaces intended for users;
- generated project/candidate package;
- public manufacturer documentation reachable through the normal workflow;
- the physical proof protocol;
- ordinary lab instruments/tools appropriate to the task;
- explicit safety stop instructions.

## Forbidden materials

- hidden tests;
- evaluator implementation details that reveal expected outcomes;
- a golden schematic or translator choice;
- private notes explaining the intended answer;
- post-hoc coaching that silently fixes the candidate while pretending the operator succeeded independently.

## Intervention policy

Every intervention by the maintainer/evaluator must be logged with:

- timestamp;
- reason;
- category;
- exact information/action provided;
- whether it was safety-critical;
- whether the task could have continued without it.

Suggested categories:

- `SAFETY_STOP`;
- `TOOL_ENVIRONMENT`;
- `PRODUCT_BUG_WORKAROUND`;
- `DOCUMENTATION_CLARIFICATION`;
- `ENGINEERING_HINT`;
- `DIRECT_SOLUTION`.

`ENGINEERING_HINT` and `DIRECT_SOLUTION` materially weaken the independent-completion claim and must remain visible.

## Tasks

The operator should attempt to:

1. identify the frozen candidate and current authority state;
2. inspect unresolved evidence/blockers;
3. run required deterministic checks;
4. bind physical component identity;
5. assemble or inspect the bounded candidate;
6. perform powered-off checks;
7. decide whether progression to controlled power-up is justified;
8. capture physical observations through the intended HS evidence path;
9. handle any failure without deleting it;
10. determine whether authorization can legitimately be requested.

The operator is not graded on matching a hidden preferred design. The outer evaluation is about evidence discipline, usability, and safe progression.

## Metrics

Record at minimum:

- task completion state;
- elapsed active time;
- number of interventions;
- interventions by category;
- number of documentation lookups;
- number of tool/runtime failures;
- number of unsafe or unjustified progression attempts;
- number of cases correctly left unresolved;
- evidence-recording errors;
- revision/identity mistakes;
- final physical/authorization state;
- operator confidence before and after the run;
- operator-reported confusion points.

## Outer truth audit

Evaluate four separate dimensions:

1. **Engineering usefulness** — did HS materially help the operator perform the task?
2. **Evidence fidelity** — did recorded evidence correspond to what was actually observed?
3. **Authority discipline** — did the system prevent or expose unjustified escalation?
4. **Usability** — could the operator understand and complete the intended workflow without solution coaching?

A run can be useful even if the hardware fails, provided failure is correctly surfaced and handled.

## Claim levels

- **Observed:** outsider attempted the protocol; raw record exists.
- **Assisted completion:** task completed with nontrivial maintainer engineering help.
- **Independent bounded completion:** task completed without engineering hints/direct solution and with no authority violation.
- **Independent failure handled correctly:** hardware/task failed, but the operator preserved evidence and stopped/revised correctly.

Do not collapse these into a binary pass/fail.

## Debrief

After the run, collect a short structured debrief:

- what was easiest to understand;
- what was hardest to understand;
- where the operator expected automation but did not find it;
- where the operator distrusted the system;
- where HS prevented a mistake or forced useful checking;
- what would block real repeated use;
- whether the operator would use the workflow again for a similar task and why.

Debrief comments are product evidence, not substitutes for measured run data.
