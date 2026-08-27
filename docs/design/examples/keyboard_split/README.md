# Synthetic Lifecycle Walkthrough — Commodity Keyboard → Split Keyboard

> **DESIGN FIXTURE ONLY.** No physical keyboard has been transformed or verified by these files. All identifiers, measurements, prices, warranty terms, and outcomes are illustrative. These artifacts exist to validate the lifecycle/passport/recipe design before implementation.

## Purpose

Exercise the proposed lifecycle architecture end-to-end without pretending the platform exists:

1. one donor keyboard is frozen as an input asset;
2. a transformation record links that donor to a new split-keyboard output identity;
3. unit claims resolve to explicit synthetic test/evidence references;
4. a recipe is emitted at `OBSERVED` maturity only;
5. a buyer-facing listing is projected from the same claim state;
6. an agent-service walkthrough consumes exact unit context rather than generic split-keyboard assumptions.

## Files

- `passport.example.json` — item-level machine-readable passport projection.
- `transformation.example.json` — donor-input → transformed-output lineage.
- `recipe.example.json` — versioned transformation-family knowledge at `OBSERVED` maturity.
- `listing.example.json` — non-authoritative buyer/listing projection.
- `AGENT_SERVICE_WALKTHROUGH.md` — example of unit-aware service reasoning.

## Design questions this fixture tests

- Can a transformed object have a new identity without losing donor lineage?
- Can customer-visible claims remain weaker than or equal to engineering evidence?
- Can failures remain visible after a repair succeeds?
- Can one completed unit seed reusable recipe knowledge without implying universality?
- Can an agent retrieve useful troubleshooting context without inventing architecture?
- Can listing/warranty language stay downstream of evidence rather than becoming truth?

## Expected design verdict

If these five views require mutually inconsistent facts or duplicate authoritative state, the lifecycle architecture is wrong and should be revised before coding.
