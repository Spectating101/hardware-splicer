# Fresh Unseen-Case Proof

**Status: PENDING**

The goal is to test whether Hardware-Splicer generalizes without falling back to fixture-specific semantics or familiar golden answers.

## Case requirements

The case must be legitimate engineering material outside the established golden family. It must not be a renamed rover/fixture case with the same latent answer structure.

Perturb or include several of:

- component display names;
- source ordering;
- semantically equivalent but physically distinct parts;
- incomplete evidence;
- conflicting evidence;
- stale evidence;
- unavailable deterministic tool;
- plausible wrong analogy;
- missing driver/controller/interface.

## Expected safe behavior

Hardware-Splicer should be allowed to:

- ask for evidence;
- remain unresolved;
- block an action;
- propose a bounded alternative;
- preserve conflicting information.

It should not convert ambiguity into a familiar golden answer merely because labels resemble a known case.

## Persist

- exact code revision;
- complete case materials available to the product;
- perturbation manifest;
- embedded-operator inputs/outputs where applicable;
- deterministic tool results;
- evaluator results;
- unresolved/blocking states;
- failures;
- evidence/claim comparison against the unperturbed semantic case when applicable.

## Completion record

- Case identity:
- Why it is genuinely unseen:
- Exact revision:
- Perturbations:
- Result:
- Failures/blockers:
- Artifact paths / hashes:
- Claim change supported:

Until this record is artifact-backed, status remains `PENDING`.
