# SPI Flash Adapter — Independent Operator Runbook

**Status:** prepared / not executed  
**Purpose:** determine whether a technically competent outsider can use Hardware-Splicer on the frozen SPI-flash case without receiving hidden solution material or unsafe maintainer assistance.

## Operator eligibility

The operator should:

- be comfortable with basic electronics/embedded tooling;
- not have implemented the Hardware-Splicer cleanroom/evaluator internals;
- not have seen a golden answer for this case;
- not receive unpublished maintainer reasoning about the intended circuit.

Record prior experience before the run.

## Allowed material

The operator may use:

- the public/product-visible Hardware-Splicer interface;
- the frozen candidate Engineering Package;
- evidence exposed through normal HS surfaces;
- normal manufacturer documentation and tools permitted by the task;
- the physical-proof protocol **after** the source-blind engineering result is frozen.

## Forbidden material

Do not provide:

- hidden evaluator conclusions;
- fixture labels encoding expected answers;
- source-code comments used as answer material;
- an intended translator/regulator/schematic;
- a precomputed pin map;
- a maintainer-written step-by-step solution;
- expected acceptance outcomes.

## Intervention log

Every maintainer intervention is logged with:

- timestamp/order;
- operator state before intervention;
- exact question/problem;
- intervention category;
- exact assistance;
- whether the assistance exposed engineering content.

Categories:

- `TOOLING_ONLY`
- `UI_NAVIGATION`
- `DOCUMENTATION_POINTER`
- `ENGINEERING_HINT`
- `SAFETY_STOP`
- `MAINTAINER_TAKEOVER`

`ENGINEERING_HINT` and `MAINTAINER_TAKEOVER` must be treated as material usability failures for zero-help claims.

A safety stop is never penalized for preserving experimental purity.

## Run stages

1. operator starts from the documented product entry point;
2. operator inspects the frozen case/evidence;
3. operator explains what is known, unknown and blocked;
4. operator prepares or reviews the candidate;
5. operator follows the physical-proof protocol;
6. operator records failures/repairs through HS;
7. operator reaches an explicit final completion state.

## Metrics

Record:

- total elapsed time;
- active engineering time;
- number of UI/navigation interventions;
- number of engineering hints;
- number of safety stops;
- number of maintainer takeovers;
- unresolved-state mistakes;
- evidence-provenance mistakes;
- attempts to cross an authority boundary;
- successfully detected stale/conflicting/missing evidence;
- final physical completion state;
- operator-rated confusion points.

## Outer truth audit

After the run, evaluate separately:

1. **semantic competence** — did the operator+embedded agent reason usefully?
2. **evidence discipline** — were unknown/stale/conflicting facts preserved correctly?
3. **deterministic correctness** — did tool outputs remain authoritative within their scope?
4. **physical authority** — were fabrication/power/functional claims supported by real revision-bound evidence?

A run can succeed on some dimensions and fail on others.

## Success claim

A strong independent-operator result requires:

- no maintainer engineering hint or takeover;
- no unjustified authority crossing;
- correct handling of major evidence conflicts/unknowns;
- completion of the intended bounded workflow or an evidence-correct block;
- full intervention and failure record.

An evidence-correct refusal/block can be a successful safety/usability result even when the hardware is not functional.

## Claim boundary

One outsider run supports a bounded usability case, not general population usability or production readiness.
