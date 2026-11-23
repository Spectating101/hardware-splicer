# HS remote engineering job controller — November 5, 2026

A narrow source-approved remote worker, not a general-purpose AI engineer
or a multi-node laboratory cluster.

## What this changes

HS can submit an approved engineering objective to its existing GitHub Actions
worker, persist the request, identify the correlated run by a unique ID and
the exact main-branch commit, then retrieve and check the raw engineering
artifact. The controller is operated explicitly from an authorized workstation.

Only two objectives are supported:
- Review an HS SPI flash adapter schematic: approved akcli version; JSON findings
- Compare the controlled revision of the real HS SPI adapter PCB: approved
  kdif version, KiCad 9 container; self-contained interactive HTML

The objective classifier is simple, explainable deterministic matching, NOT
LLM engineering reasoning. GitHub Signals is currently a normalized
source-backed discovery feed, not a live third-party API subscription.

The GitHub workflow accepts only specific task choices and the correlation
ID. It runs the preflight validation before any specialist job. Other
unrequested tools are skipped. It cannot receive arbitrary commands, repo
names, private file paths or physical-equipment instructions.

## Try it on the authorized Optiplex

Using a recent HS checkout that has the merge commit, with authenticated gh CLI:

    git fetch origin main
    LEDGER="$HOME/hs-approved-jobs"

Read-only planning (no dispatch, no job record):

    python3 scripts/dispatch_hs_workshop_task.py --ledger "$LEDGER" \
      submit --objective "Compare PCB revisions"

Explicit submission:

    python3 scripts/dispatch_hs_workshop_task.py --ledger "$LEDGER" \
      submit --objective "Compare PCB revisions" --execute

The JSON response includes the request ID. Use that exact ID for all follow-ups:

    python3 scripts/dispatch_hs_workshop_task.py --ledger "$LEDGER" \
      status --request-id hs-0123456789abcdef

    python3 scripts/dispatch_hs_workshop_task.py --ledger "$LEDGER" \
      collect --request-id hs-0123456789abcdef

The 16 hex digits in the sample are illustrative; each real submission gets
its own randomly generated ID.

Collection is permitted only after the corresponding, source-pinned worker
completes successfully and the other specialist is skipped. It checks the
registered source commit, original design hash, native artifact hash and task
selection; it rejects untrusted content, unexpected symlinks and excess size.

The ledger holds state as JSON. Network error after dispatch is recorded as
unknown rather than retried automatically; this avoids accidental duplicate
remote executions. Repeated collect returns the original verified result.

## Security and limitations

No machine motion, fabrication, printer, robot, arbitrary repository installs
or uncontrolled hardware actuation. Only inspected external source revisions
are eligible. Docker containers have networking disabled, read-only inputs
and no added privileges; Docker daemon access itself requires trusted hosts.

The remote jobs use fixed, publicly committed HS example engineering inputs
and a deliberately labeled test-only PCB silkscreen revision. This is not
user-supplied or private-design task distribution. Future workshop nodes
will require authorized worker enrollment, trust/permissions, encrypted
artifact transfer, bounded job leases, cancellation, independent measurement,
physical safety interlocks and separate human approval.
