# GitHub source-native workshop: task-based tool selection (Nov 2026)

This builds on the merged source acquisition pipeline (PR #281) without
replacing either upstream engineering engine.

## What is now working

A transparent objective classifier chooses one of two **exactly approved**
external tools, checks whether the appropriate engineering input exists, and
runs the original program in a non-networked sandbox:

| Engineering objective | HS-selected tool | Actual upstream deliverable |
|---|---|---|
| Review a KiCad schematic | tipoLi5890/akcli | JSON schematic diagnostics |
| Compare two PCB Git revisions | 0x12net/kdif | Interactive KiCad-rendered HTML diff |

Tool selection is explicit **rules_v1**, not a language-model agent. Ambiguous
tasks such as "review changes" fail closed rather than arbitrarily running
multiple tools or guessing.

The source candidates come from a **normalized, real GitHub repository
discovery feed**, not a claimed live githubsignals.io subscription. Unknown
repos or newer upstream revisions stay discovery-only until adapter review.

## Real-work execution

See evidence/github_signals/workshop_task_router_20261105/README.md.

- Existing HS SPI flash adapter schematic: akcli generated **27 native findings**,
  of which 16 are layout warnings. KiCad ERC for the same design reports 0
  errors/0 warnings. Different checks, not a new electrical failure.
- Existing HS SPI flash adapter PCB: kdif generated an **interactive 92,459-byte
  diff** showing a known, fixture-only F.SilkS label change. The baseline was
  byte-identical to the actual HS source design. The amended design is NOT a
  production HS revision.
- Both outputs pass a digest check and are registered as optional,
  project-used specialist capabilities in HS's canonical report.
- akcli runs in bwrap or an explicitly selected, reviewed Python container.
  kdif runs in bwrap or official KiCad v9 container at pinned image digest
  f36b185970d398b84c095ace896046798ff60d458ce59d49669c4633c304cfbd.
- Sandbox execution has no network, read-only source volume(s), no physical
  devices mounted, and no privileges added. Docker access itself assumes a
  trusted local daemon; this is NOT safe execution for arbitrary malicious
  repositories. The allowlist remains mandatory.

## Reproduce a real visual comparison

1. Pull the reviewed KiCad Docker image before executing the tool:

    docker pull kicad/kicad@sha256:f36b185970d398b84c095ace896046798ff60d458ce59d49669c4633c304cfbd

2. Generate two controlled Git revisions from the real HS PCB (in an isolated
   scratch directory, NOT in the production project):

    python3 examples/github_signals/make_kdif_fixture.py --out /tmp/hs-kdif-history

3. Read revision_a and revision_b from /tmp/kdif_fixture_manifest.json.
   Then invoke the router, not a hard-coded external tool command:

    python3 scripts/run_github_signal_task.py \
      --feed examples/github_signals/live_reviewed_candidates_20261105.json \
      --objective "Compare the committed PCB revisions" \
      --board-repo /tmp/hs-kdif-history \
      --board /tmp/hs-kdif-history/spi_flash_adapter_v1.kicad_pcb \
      --revision-a FULL_BASELINE_SHA \
      --revision-b FULL_CONTROLLED_SHA \
      --checkout-base /tmp/hs-approved-source-checkouts \
      --out /tmp/hs-kdif-evidence \
      --fetch --sandbox docker

The HTML, task choice, evidence hashes and capability verification appear under
/tmp/hs-kdif-evidence. Run the standard HS capability report with
--build-dir /tmp/hs-kdif-evidence to see the project-used kdif specialist.

For design review, switch the objective to "Inspect this schematic for issues"
and supply --schematic <path-to-existing-kicad_sch>. The same source feed and
router select the approved akcli tool. Both calls are exercised by the tests.

## Known limitations and next gates

- Currently two pre-reviewed pinned adapters, not arbitrary plugin synthesis.
- Task classification uses simple explainable rules, not model reasoning.
- kdif fixture only proves a visualization pipeline, not engineering changes.
- No cross-machine work dispatcher or multi-node job scheduler yet.
- No physical measurement, repair, robot, printer, instrument or authorized
  fabrication is performed.
- A genuine later engineering-agent test must compare model-only versus
  model-with-HS planning/selection and demonstrate better verified decisions.

Reusing upstream programs is preferred: the HS contribution is source approval,
tool selection, compatibility checks, execution isolation, provenance, artifact
verification, project registry, and eventually multi-device orchestration.

## Proposed adapters and explicit offline trials

`github_signal_proposals.PROPOSED_ADAPTERS` is a review queue separate from
`ADAPTERS`. The approved set remains akcli and kdif. A discovered repository,
vetting evidence, or successful trial never approves a tool. Approving a
proposal remains a **human code change to ADAPTERS**, with adapter/revision
review and tests; the proposal must also leave the proposed-only guards.

The rules_v1 objective table additionally reports these proposals:

| Objective | Proposal | Router result |
|---|---|---|
| interactive assembly BOM / placement viewer for a KiCad board | openscopeproject/InteractiveHtmlBom | `tool_proposed_pending_approval` |
| panelisation / fab outputs | yaqwsx/KiKit | `tool_blocked` with dependency blocker |

Neither result executes or acquires source. The normal signal pipeline also
refuses proposal execution, even at the proposed commit. Proposal evidence is
never registered as an approved project-used capability.

InteractiveHtmlBom is `proposed_pending_human_approval`: release v2.12.0,
commit `5c192e794cd66fde04bab11810601b711bf8581b`, MIT licence claim.
The operator-established offline trial used host KiCad 9 `/usr/bin/python3`
with `pcbnew` and `wx`, no other dependencies and no installation. On
`hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb`,
it exited 0, wrote `/output/ibom.html` (about 229 KB), and left the checkout
clean. Its `var pcbdata = JSON.parse(LZString.decompressFromBase64("..."))`
data contained exactly the board's 40 references; `bom` had keys `both`,
`skipped`, `fields`, `F`, `B`, with 10 rows in `both`. These are recorded
operator observations, not measurements from the unit tests.

An operator can explicitly trial an already available clean checkout:

```sh
python3 scripts/trial_github_signal_proposal.py \
  --adapter openscopeproject/InteractiveHtmlBom \
  --checkout /path/to/pinned/InteractiveHtmlBom \
  --board hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb \
  --out /path/to/empty/trial-output
```

This CLI checks the full HEAD, clean Git root (including ignored/untracked
files), LICENSE claim, entrypoint, host Python modules and KiCad major version.
It runs the exact registered argv template with `bwrap --unshare-all`, read-only
source and board, and only the separate output directory writable. Missing
bubblewrap or capabilities fail closed; there is no host/Docker fallback,
fetch, or runtime dependency installation. The output directory must be empty.

The independent checker parses board footprint references with HS's KiCad
s-expression parser, decodes LZString in pure Python, and compares them to
`pcbdata.footprints[].ref`, requiring `bom` to be present. It never executes
page JavaScript. Missing and extra references are reported; a matching set
proves this limited data check, not assembly correctness or HTML safety.
`HS_SIGNAL_PROPOSAL_TRIAL.json` retains the argv, host capability report,
input/output SHA-256, exit code, stderr tail, timing and output check, including
failed executions. Every trial states `approval_effect: "none"`.

KiKit is `proposed_blocked`: release v1.8.1, commit
`d1957c535781371db5a2f507f8154d460095f9f1`. The MIT licence claim follows the
existing HS tool catalogue and is not newly verified trial evidence. The
operator established that host packages `shapely`, `markdown2`, `pybars`,
`commentjson`, and `solidpython` are absent. Runtime installation is forbidden;
a pinned, reviewed dependency environment is required before a trial can be
designed and accepted. Its recorded candidate panelisation argv and expected
output are untrialled; neither panelisation nor fabrication exports have
execution evidence here. The explicit trial runner refuses this blocked
proposal before any subprocess is invoked.
