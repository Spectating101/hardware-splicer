# Jev AI control plane

Hardware Splicer already has a bounded System-2 layer: `run_ai_project_orchestrator()` asks the configured LLM to interpret the engineering mission/context and emit schema-shaped, proposal-only actions. Those actions are validated against a closed action vocabulary and explicitly carry no automatic or physical authority.

Jev now fits immediately after that step:

```text
engineering mission + sanitized evidence
              |
              v
      System-2 LLM orchestrator
   language / synthesis / proposals
              |
              v
             Jev
 select/review bounded proposed action
              |
      +-------+--------+
      |                |
high confidence   low confidence
      |                |
 proposal only     System-2 review
      |
 existing executor / verification gates
```

`hardware_splicer.ai_project_decision.select_next_proposed_action()` chooses among the action IDs already produced by the LLM. `review_proposed_action()` returns `accept | revise | reject | escalate` for a proposed action.

Neither function executes tools or changes action authority. The state sent to Jev reiterates the existing invariants: no automatic execution, fabrication, flashing, power, motion, operational, or release authority.

## Configuration

Set `TYPESAFE_API_KEY` locally. `TYPESAFE_MODEL` and `TYPESAFE_API_URL` are optional overrides. No key is required for the unit tests.

## Rollout

Use the selector initially as advisory control over proposal ordering. A low-confidence or unavailable Jev result returns `needs_supervisor`, which is the handoff point for another LLM engineering pass. The existing action parser, tool executor, bench gates, and physical-authority restrictions remain authoritative regardless of Jev confidence.
