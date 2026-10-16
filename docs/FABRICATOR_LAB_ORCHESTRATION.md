# Fabricator lab orchestration

This layer turns the capability registry into a multi-tool fabrication-lab scheduler. It allocates registered resources to dependency-linked tasks but never grants physical authority.

## Workflow planning

A `FabricationWorkflowTask` declares:

- stable task id;
- required capabilities;
- optional operator kind;
- public numeric minimums such as build volume;
- relative duration estimate;
- dependency task ids;
- whether the eventual task will require separate physical authority;
- whether simulation-only resources are acceptable.

`FabricationWorkflowPlanner` validates the dependency DAG, rejects cycles/missing dependencies, asks the server-owned capability registry for matching resources, and constructs a deterministic relative schedule.

Independent tasks can run in parallel. Shared resources are serialized. Downstream tasks cannot be scheduled when a dependency was not allocated.

The resulting plan is content-addressed with SHA-256. A scheduled task may say `requires_physical_authority=true`, but every allocation retains `physical_authority_granted=false`.

## Plan-bound resource leases

`WorkflowPlanRegistry` retains exact schedule plans. `ResourceLeaseStore` can then reserve only the resource that the retained plan assigned to a specific task.

Only one active lease is allowed per resource. Leases expire automatically.

Acquisition returns a random `lease_token` to the caller. Public lease listings never include that token; release requires it. The token is only a reservation capability and explicitly does not authorize machine actuation.

## Agent surface

`/v1/fabricator/lab/*` is fail-closed until a server-owned `FabricatorLabWorkbench` is configured.

Agent operations:

- list registered resources;
- plan a capability-driven dependency workflow;
- read the retained plan;
- acquire/release short-lived plan-bound resource leases;
- inspect active public leases.

Actual physical work still uses `/v1/fabrication/*`, its exact execution plan, and its separate human grant.

The bounded MCP/OpenAPI projection is `fabricator_lab_manifest()`.
