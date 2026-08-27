# Synthetic Agent-Service Walkthrough

> **DESIGN FIXTURE ONLY.** This transcript describes a hypothetical transformed keyboard and must not be cited as physical evidence.

## User symptom

> The right half of my split keyboard stopped responding. What should I check?

## Generic-agent failure mode

A generic assistant might assume common split-keyboard details such as QMK, TRRS, a particular serial transport, or a conventional dual-Pro-Micro architecture. Those assumptions may be wrong for the actual unit.

## Passport-aware retrieval

The service agent first calls read-only lifecycle functions conceptually equivalent to:

```text
get_unit_summary(urn:hs:unit:split-kb-0001)
get_unit_configuration(urn:hs:unit:split-kb-0001)
get_unit_history(urn:hs:unit:split-kb-0001, service_relevant)
get_current_claims(urn:hs:unit:split-kb-0001)
get_recipe_lineage(urn:hs:unit:split-kb-0001)
check_warranty(urn:hs:unit:split-kb-0001, right_half_unresponsive)
```

The retrieved synthetic context says:

- unit was created by major transformation of donor `donor-kb-0001`;
- selected architecture is dual controller;
- both PCB regions are retained donor material;
- inter-half communication uses `new:inter-half-harness`;
- original controller region was removed;
- ROW4 previously failed after the cut and was repaired with jumper J04;
- final synthetic fixture recorded successful USB enumeration, key coverage, and inter-half stability at revision R4;
- no evidence exists for any later physical modification.

## Bounded reasoning

The agent can now prioritize unit-specific hypotheses:

1. Determine whether the left half still enumerates over USB.
2. Inspect/reseat the **actual recorded inter-half harness**, rather than assuming TRRS.
3. Check whether right-controller power is present using the service procedure associated with the installed controller.
4. Inspect the transformation/rework region around J04 only if symptom scope implicates ROW4 or nearby retained traces; do not treat an old repaired failure as automatically causal.
5. If the harness/controller state changed after revision R4, invalidate the prior inter-half-stability claim until the relevant protocol is rerun.

## What the agent must not do

It must not write a lifecycle fact such as `right_controller_failed=true` based on conversation alone.

Instead it may open a proposed service session:

```text
service_session:
  symptom: right_half_unresponsive
  proposed_observations:
    - usb_enumeration_left
    - inter_half_harness_visual
    - right_controller_supply_measurement
  authority: human_observation_required
```

Only instrument/human-backed observations can later create the corresponding lifecycle events through the normal HS evidence/authority path.

## Warranty behavior

The synthetic listing carries an illustrative 90-day warranty. A real implementation would distinguish:

- symptom plausibly covered;
- warranty period active/expired;
- user-permitted troubleshooting before service;
- interventions that would change warranty state.

The agent may explain the warranty state but cannot authorize a commercial warranty payout or silently modify warranty history.

## Design verdict

The lifecycle record materially improves service reasoning only when it contains unit-specific transformation/configuration/history that a generic model could not safely infer. If the passport contains merely marketing copy, the agent layer adds little value.
