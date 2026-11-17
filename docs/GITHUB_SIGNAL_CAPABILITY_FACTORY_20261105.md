# GitHub Signals → HS Tool Capability: first native execution

**Status:** Proven with a single reviewed adapter and a source-pinned upstream
repository on the Optiplex. No claim of general-purpose AI tool synthesis.

This demonstrates something stronger than appending another promising GitHub URL
to a catalogue: HS can ingest a discovery record, refuse an unsupported
candidate, fetch a reviewed repository at an immutable commit, verify its
LICENSE, run a real engineering command with no sandbox network access, retain
source-file and output hashes, and expose the **project-used** capability in
HS's existing capability report.

## External-source boundary

There is **no authenticated live githubsignals.io or githubsignals.com API
integration here**. The normalized feed can be produced by GitHub search,
manual GitHub Signals research, or a later Signals connector.

The evidence file at examples/github_signals/live_reviewed_candidates_20261105.json
records two real repos discovered on GitHub with commit and SPDX license facts:

1. tipoLi5890/akcli — MIT. Approved read-only CLI adapter for KiCad schematic
   diagnostics. Revision 2126c328402fa77f8f6bf2114f052595f86f14aa.
2. 0x12net/kdif — MIT. Discovered but no reviewed HS adapter, so **NOT
   executed or installed**.

**An unrecognized repository is never executed because it appears in a
discovery feed.** A human must review and add a fixed adapter before HS can use
it. In this v1, only akcli is approved.

## Reproduce the actual design review

Linux with git, Python ≥3.12 and bubblewrap (bwrap):

    python3 scripts/evaluate_github_signal_tool.py \
      --feed examples/github_signals/live_reviewed_candidates_20261105.json \
      --schematic hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
      --checkout /tmp/hs-github-signals/akcli \
      --out /tmp/hs-github-signals/out \
      --fetch

    PYTHONPATH=src python3 -m scripts.report_capabilities \
      --build-dir /tmp/hs-github-signals/out

The importer checks the exact **approved**, full Git SHA, verifies the
checkout is clean, and independently inspects the checked-out MIT license.
It does **not** run pip postinstall scripts or arbitrary user-specified commands.

Two explicit, fail-closed Linux execution backends are supported:
- Default: bubblewrap with --unshare-net, read-only mounts, sanitized environment
  and no user home.
- CI-compatible: Docker with a pinned Python image digest, --pull=never,
  --network=none, --read-only, --cap-drop=ALL, --security-opt=no-new-privileges,
  process/memory/CPU ceilings, and **only** read-only source/input volumes.
  Pre-pull the approved image from the administrator-controlled environment,
  then add --sandbox docker to the evaluation command. There is no automatic
  fallback from bubblewrap to Docker or to the host process.

The Docker version has been executed on the Optiplex with identical 27 findings;
GitHub's hosted runner disallows bubblewrap's requested network namespace in
its environment, so the CI job explicitly selects Docker instead. Docker daemon
access and container/kernel escape remain trusted-host considerations; this
does **not** provide VM-grade isolation for malicious repositories.
The host **must** approve the exact repository/revision and adapter.

Machine output:

- 40 schematic components and 83 pins counted by native akcli.
- 27 total static findings: 6 info, 5 note, **16 warning**.
- Most warnings are geometric label-overlap heuristics requiring review, NOT
  independently confirmed electrical defects.
- Native installed kicad-cli sch erc on the same schematic reports **0 errors,
  0 warnings**. This is not a contradiction: the analysis scopes differ.
- kdif remained discovered_only, with no command execution.
- The verified execution adds signal-akcli-schematic-review to the canonical
  capability report as project_used with the source input and diagnostic
  artifact SHA-256 hashes.

Preserved example evidence:
evidence/github_signals/akcli_20261105/.

## What this proves and what it does NOT

| Gate | Status |
| --- | --- |
| Discover real open-source candidates | Yes; GitHub source-backed feed |
| Verify exact repo revision & license | Yes |
| Reject unknown/unapproved executable adapters | Yes |
| Fetch and run a native external engineering CLI | Yes, akcli |
| Non-network tool execution | Yes, bwrap --unshare-net |
| Hash diagnostic output and HS project input | Yes |
| Register actual execution in existing HS capability report | Yes |
| Automatically create an adapter for any GitHub project | **No** |
| Automatically subscribe to a GitHub Signals feed | **No** |
| Autonomous multi-model engineering decisions | **No** |
| Approve CAD revisions or physical fabrication | **No** |

The next planned capability is an adapter-review queue: repository diff,
license obligations, command/API inspection, test fixture, sandbox acceptance,
and rollback/disable control before any integration enters the approved set.

**No physical device, firmware, printer, machine or other hazardous actuator is
ever controlled in this experiment.**

## Report-only candidate vetting

`scripts/vet_github_signal_candidates.py --feed <feed.json> --out <review.json>`
adds a `vetting` record beside each candidate. Alternatively, use
`--kicad-pcm <packages.json or repository.json or URL>` to import KiCad PCM
metadata; repository descriptors require a matching packages SHA-256. Package
licences, resources, all versions, archive URLs and `download_sha256` remain
provenance. No package archive is downloaded. PCM provides no Git source pin;
the importer leaves it unset, and the existing execution gate rejects such
records until an independently reviewed source pin and adapter exist.

Evidence sources are OpenSSF Scorecard (overall score, scored commit and eight
security checks), repos.ecosyste.ms (SPDX licence and repository activity), and
the feed's declared licence. `--offline` skips all HTTP and marks remote sources
`unavailable`; remote PCM metadata must first be saved locally. Source errors
and retrieval timestamps are retained for review. Scorecard evidence for a
different or missing candidate commit is marked `different_commit` and never
applied to candidate flags. The License check establishes presence only, not
an SPDX expression. Licence disagreement and maintenance/security flags are
review prompts, not licence clearance or security guarantees.

The Python API also accepts an explicit already-fetched checkout for optional
local ScanCode licence evidence. It verifies the full pin and clean checkout,
then runs only the installed ScanCode scanner in a read-only, network-isolated
bubblewrap process with a timeout. Missing ScanCode or bubblewrap is recorded
as `unavailable`; there is no host-execution fallback or source fetch. The CLI
does not select checkout paths from untrusted feed metadata.

Vetting is **evidence only**: every result has `approval_effect: "none"` and
`requires_human_review: true`. Discovery and task reports display it beside the
candidate. It never adds approved adapters, changes approval decisions,
installs software, or runs candidate code. Human adapter/revision review and
all existing execution gates remain required.
