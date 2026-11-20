# Policy Lab layer over saved HS studies

HS supplies revision-bound engineering evidence. Policy Lab evaluates declared
targets over those modeled facts and returns explicit numeric requirements for
another HS study. Both engines keep their existing project and assessment stores.

## Export an existing project

The installed `hs-policy` command also runs as
`python -m hardware_splicer.policy_layer_cli` from a checkout with `PYTHONPATH=src`.

```bash
hs-policy --project-root /path/to/projects --jobs-db /path/to/jobs.sqlite3 \
  export PROJECT_ID evidence.json --revision 1
```

The `hardware_splicer.policy_evidence.v1` document retains the complete validated
study, its source and artifact hashes, original engineering constraints, and
explicit numeric facts with units. Export uses the existing stored-artifact audit;
it does not rerun native CAD. Intact failed designs remain exportable with their
original failing checks. Its CLI receipt reports the SHA-256 of the exact file
bytes; supply that hash to Policy Lab rather than hashing a reserialized object.

## Review and return requirements

From the corresponding Policy Lab checkout:

```bash
node applications/hardware-policy/run.mjs review \
  --evidence evidence.json --sha256 ORIGINAL_EXPORT_SHA256 \
  --policy policy.json --out review --job-id design-review-001 --workspace workspace

node applications/hardware-policy/run.mjs verify \
  --review review/review.json --evidence evidence.json
```

The policy declares its digital or physical scope and named numeric targets with
explicit units. A digital design can satisfy a digital review; a requested
physical-operation decision stays blocked. Missing measurements remain missing.
Verification reexecutes Policy Lab's installed domain adapter and foundation over
the original evidence and compares the complete assessment.

After replay, validate the returned proposal in HS:

```bash
hs-policy --project-root /path/to/projects --jobs-db /path/to/jobs.sqlite3 \
  feedback evidence.json review/review.json proposal.json
```

HS binds feedback to the exact original export bytes, project, revision and run;
reopens the stored artifacts; and validates numeric overrides through its existing
registered-case resolver. It emits resolved requirements without changing the
project or queuing a job. A later explicit `DigitalStudyEngine.run_revision` uses
that proposal for a new digital calculation. Feedback for an earlier revision is
rejected after the project changes.

HS's feedback validator does not itself replay JavaScript policy logic. Its
receipt labels the review as supplied, with source binding and HS requirements
validated. The separate Policy Lab verifier establishes reproduction.

## Reproduce the Fielddeck experiment

From Policy Lab, with the installed HS native Python runtime:

```bash
python applications/hardware-policy/fielddeck-pilot.py \
  --hs /path/to/hardware-splicer --out /tmp/fielddeck-policy-pilot
```

The finite runner builds Fielddeck 7 and Fielddeck 5, compares the same runtime
target, tests stricter and physical-scope policies, validates feedback, executes
one higher-load digital revision, and replays the resulting blocked review. It
also checks cross-repository schema/unit parity, stale feedback, altered evidence
and incorrect expected hashes. `--resume` verifies and reuses retained project
revisions; changed source bytes or unrelated revision history are rejected.

This connection exchanges design evidence and modeled performance. It does not
create meter observations, certify physical behavior, authorize hardware operation,
or establish economic outcomes. A future measured-evidence adapter needs its own
measurement and source-custody contract.

## Carry an applied change to a Cite dossier

`hardware_splicer.change_dossier.build_change_evidence` packages one reviewed and
applied change as `hardware_splicer.engineering_change_evidence.v1`: the base and
new revision identities (run, snapshot, seal and package hashes), the Policy Lab
review and HS proposal, the study check delta, and the SHA-256 of every covered
file. It refuses a candidate that is not the latest revision, does not descend
from the base, or does not carry the proposal's resolved requirements. Failing
rerun checks are listed as unresolved; nothing is marked ready.
`export_revision_head` reports the latest revision so a receiver can tell when a
dossier it issued has gone stale.

Cite-Refinery's `cite-refinery-change-dossier issue` rechecks those bytes and
issues a revision-bound edition; `check` compares the edition with a newer head
and reports it stale. Replay the whole chain, including the negative and stale
controls:

```bash
HARDWARE_SPLICER_DIGITAL_PYTHON=/path/to/digital-native-venv/bin/python \
PYTHONPATH=src python scripts/demo_change_dossier.py \
  --policy-lab /path/to/policy-lab --cite /path/to/cite-refinery
```

Results go to `docs/status/generated/change-dossier-<tag>.{log,json,md}`, with the
readable dossier and the exact exchanged bytes beside them.
