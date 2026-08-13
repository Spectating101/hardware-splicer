# SPI Flash Adapter — Independent Operator Runbook

**Status: PREPARED / NOT EXECUTED**

This runbook is used only after a real candidate and physical-validation evidence exist. It tests whether a technically competent outsider can use the normal Hardware-Splicer surface without repository-specific coaching.

It does not contain an expected schematic, preferred translator, golden answer, hidden evaluator conclusion, or instructions for how the operator “should” solve the case.

## 1. Operator eligibility

Prefer an operator who:

- has enough hardware/electronics competence to understand the task;
- did not author the Hardware-Splicer repository;
- did not design the unseen SPI-flash corpus;
- has not been shown the hidden evaluator notes or expected outcome;
- has not been coached on fixture-specific semantics.

Record why the operator is considered independent.

## 2. Materials the operator may receive

Provide only what a normal legitimate user would receive:

- normal Hardware-Splicer installation/setup instructions;
- normal UI/API/product surface;
- the engineering task statement;
- component/source materials normally available to the engineer;
- the physical artifact and normal instrument/setup instructions if the task includes bench interaction;
- safety rules that would be given to any operator.

## 3. Materials the operator must not receive

Do not provide:

- repository source code as a solution guide;
- hidden tests;
- golden answers;
- evaluator conclusions;
- the unseen-case perturbation rationale;
- a preferred translator/regulator/topology;
- expected measurements except where they are part of normal authoritative engineering evidence;
- live coaching intended to force a pass.

## 4. Task framing

Use a task statement that describes the engineering goal and available materials without encoding the solution.

A suitable generic form is:

> Use Hardware-Splicer through its normal product surface to review and advance this SPI-flash programming/validation adapter task as far as the available evidence safely permits. Preserve unresolved items and do not perform a physical action unless the system/procedure provides the evidence and authority required for that action.

Do not tell the operator which blockers the evaluator expects them to encounter.

## 5. Session record

Record:

- procedure ID;
- exact Hardware-Splicer source revision;
- project/candidate revision;
- operator identifier;
- start/end timestamps;
- materials provided;
- normal environment/setup;
- product interactions or trace references;
- questions asked by the operator;
- interventions provided by the facilitator;
- system errors;
- actions blocked by the system;
- actions the operator chose not to perform;
- completion state;
- final engineering/physical result.

## 6. Intervention policy

The facilitator may intervene for immediate safety or to resolve a generic environment/setup failure that any user would face.

Every intervention must be recorded with:

- time;
- reason;
- exact help provided;
- whether it disclosed project-specific knowledge;
- whether the task result depended on that intervention.

Do not convert coaching into an invisible success.

## 7. Metrics

At minimum capture:

- task completion: complete / partial / blocked / failed;
- elapsed time;
- number and type of interventions;
- unresolved items correctly preserved;
- incorrect assumptions made by operator or model;
- dangerous/unsupported action attempts blocked;
- confusion points in UI/workflow;
- evidence/provenance information the operator could or could not locate;
- whether source code was required;
- whether the operator could explain why physical authority was open or closed;
- actual physical result, if physical action was in scope.

Avoid collapsing these into one arbitrary score before the raw observations are preserved.

## 8. Required attestation

The operator record should explicitly state, where true:

- operator identity/stable pseudonym;
- independent of design authorship;
- followed the published procedure;
- source code was not required;
- procedure ID used.

This attestation is evidence of the declared protocol conditions; it is not proof of a person's real-world identity by itself.

## 9. Outer truth audit

After the session, the evaluator compares four views:

1. what the embedded model/operator believed;
2. what deterministic tools/evidence state reported;
3. what the independent user believed and did;
4. what the physical evidence actually showed.

Record mismatches explicitly.

Examples of useful mismatches include:

- model thought identity was resolved but evidence did not support it;
- user misunderstood a blocker despite correct deterministic state;
- system blocked an action that bench evidence later confirmed would have been unsafe/unsupported;
- system remained conservative where the bench later showed the candidate was fine;
- UI hid evidence that existed in the underlying package.

Do not rewrite these mismatches into a pass/fail narrative before they are documented.

## 10. Completion bar

Independent-operator proof is not complete until the record can answer:

- Who operated the system and why were they independent?
- What exact revision/product surface did they use?
- What task/materials were they given?
- What help did they receive?
- What did they complete or fail to complete?
- What incorrect assumptions/confusion occurred?
- What actions were blocked?
- Was source code required?
- What was the actual engineering/physical outcome?
- What did the outer truth audit conclude?

Until an evidence-backed session answers those questions, the status remains **PREPARED / NOT EXECUTED**.
