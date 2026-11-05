# HS approved worker pool and capability-aware admission

This is the next increment after PR #283, NOT proof of a general lab cluster.

## Operational scope

HS now admits remote jobs only when an approved logical execution pool grants
the exact engineering capability and has a free local in-flight slot. The
existing GitHub Actions ubuntu-24.04 pool is the only executable pool. It
remains pinned to the already-reviewed akcli and kdif engineering tools,
their fixed HS input designs, and the PR #283 hash verification flow.

New job records include an explicit worker assignment and capability; the
controller uses a POSIX file lock so two concurrent processes on the same
workstation cannot both consume the last slot. Ambiguous dispatches retain
their slot until reconciled; completed successful/failed jobs release it.

Old PR #283 ledgers remain compatible. Without a workers.json file, the
already-approved GitHub Actions pool is available with a two-job controller
limit. An operator-managed workers.json can pause or narrow this policy.

## Authorized workstation commands

Inspect worker pool without changing state:

    python3 scripts/dispatch_hs_workshop_task.py --ledger "$HOME/hs-approved-jobs" workers show

Explicitly approve the existing pool with one local in-flight slot:

    python3 scripts/dispatch_hs_workshop_task.py --ledger "$HOME/hs-approved-jobs" workers configure --approve --max-inflight 1

Restrict it to schematic review:

    python3 scripts/dispatch_hs_workshop_task.py --ledger "$HOME/hs-approved-jobs" workers configure --approve --allow-task review_schematic

Pause future submissions; this does not cancel existing jobs:

    python3 scripts/dispatch_hs_workshop_task.py --ledger "$HOME/hs-approved-jobs" workers configure --approve --state paused

Restore both capabilities and two slots:

    python3 scripts/dispatch_hs_workshop_task.py --ledger "$HOME/hs-approved-jobs" workers configure --approve --max-inflight 2 --allow-task review_schematic --allow-task compare_board_revisions

Regular submit/status/collect commands from PR #283 remain unchanged. A
submission still requires --execute. Read-only dry runs have no ledger writes.

## Limits and next gate

This is local capability admission, NOT cross-computer distributed leases,
physical runner discovery, GitHub cloud capacity guarantees or hardware control.
The GitHub-hosted pool is a logical job runner, not a fixed remote machine.
Unknown executor types, self-hosted labels, extra capabilities and physical
authority all fail closed. Merely editing a JSON file cannot enroll lab nodes.

Next: authenticated machine enrollment, capability attestation with bounded
heartbeats, lease-based scheduling/reconciliation, revocation, independent
artifact transport, and a real two-machine allocation test. Physical equipment
needs a separately reviewed safety and human-approval layer.

Dedicated CI covers unit admission checks, concurrent submissions and the
original source-native worker tests. These tests do not prove deployment to
a lab computer.
