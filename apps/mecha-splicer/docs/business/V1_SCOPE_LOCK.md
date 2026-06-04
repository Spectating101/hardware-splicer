# V1 Scope Lock

## Scope Rule
No new mechanism classes for V1 unless blocked by a paid buyer use case.

## Included
- Fixture-focused templates from existing stable primitives
- Deterministic bundle outputs
- Export package (`PARTS.json`, `PRINT_PLAN.md`, BOM, SCAD/STL)
- Listing assets and onboarding docs

## Explicitly Excluded (V1)
- New solver research
- Full CAD kernel integration
- FEA/simulation features
- Complex multi-axis robotics expansion
- Marketplace integrations beyond listing + delivery

## Quality Gates Before Launch
- `pytest` all green
- 3 end-to-end generation smoke tests
- 1 print-and-assemble verification per fixture family
- Documentation reviewed for limits and expected tolerances

## Change Control
Any out-of-scope request must pass this check:
1. Does it unblock immediate conversion?
2. Does it reduce support burden materially?
3. Can it be shipped in <1 day?

If any answer is "no", defer to V2 backlog.
