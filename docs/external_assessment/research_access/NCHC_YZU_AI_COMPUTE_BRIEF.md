# NCHC University AI Compute Program — YZU Internal Brief

**Route state:** FIRE AFTER INSTITUTIONAL GATE  
**Official program:** https://www.nchc.org.tw/Active/ActiveView?id=1795&menutype=0&mid=47&sitemenuid=3  
**Application window:** through 2026-10-31  
**Verified:** 2026-09-04

## What this program actually is

The National Center for High-performance Computing (NCHC) currently offers a **university-level AI compute discount program**. The university, not an individual student, is the applicant. The program explicitly lists faculty, researchers, doctoral students, master's students, AI research teams and AI courses as intended users.

Current advertised resources include:

- NANO 4 / H200 GPU compute at **NT$30 per GPU-hour**;
- Forerunner 1 CPU at **NT$0.1 per core-hour**;
- Slurm scheduling;
- TWAREN research network;
- training and technical support.

This is discounted institutional compute, **not a free student GPU grant**.

## Why Hardware-Splicer can be a legitimate internal workload

Hardware-Splicer's next evidence tranche includes repeated local/open-model evaluation against a frozen adversarial corpus. If YZU has or obtains NCHC access, local/open-model runs could support:

1. reproducible comparison of multiple open-weight multimodal/agent-capable models;
2. repeated stochastic runs over the frozen corpus;
3. offline trace generation where appropriate;
4. model/runtime benchmarking under identical evidence and authority constraints;
5. future multimodal/vision evaluation related to physical engineering evidence.

Do not claim H200 compute is required for API-only OpenAI/Anthropic evaluations. The NCHC case is strongest when tied to **actual local/open-model inference, fine-tuning or evaluation workloads** that have been selected before the internal request.

## One-page internal pitch

### Proposed project

**Reproducible Evaluation of Evidence-Constrained AI Agents for Consequential Engineering Workflows**

### Research objective

Evaluate whether deterministic evidence and authorization constraints reduce unsupported consequential actions by tool-using AI agents while preserving useful engineering task completion. Hardware-Splicer supplies a frozen adversarial hardware-engineering corpus, canonical MCP tool surface, revision/evidence state and trace/replay infrastructure.

### Proposed NCHC use

Use university AI compute for repeated local/open-model evaluation across a fixed benchmark. Candidate workloads include inference across multiple open-weight models/configurations, repeated runs for variance estimation, multimodal evidence processing and reproducible comparison against externally hosted API models.

### Expected outputs

- reproducible benchmark results;
- technical report / academic manuscript;
- model/tool trace dataset where licensing permits;
- reusable evaluation tooling;
- potential competition/conference evidence;
- internal demonstration of YZU AI research use of national compute infrastructure.

### Why university compute is useful

A university allocation allows the evaluation to move beyond one developer machine, execute repeatable model comparisons, preserve controlled runtime configurations and potentially support future lab/research users using the same benchmark infrastructure.

## Information YZU/NCHC will need from us

Before an internal request is sent, resolve:

- `[FACULTY / UNIT SPONSOR]`
- `[YZU CAMPUS CONTACT OR EXISTING NCHC WINDOW]`
- `[OPEN-WEIGHT MODEL(S)]`
- `[GPU MEMORY REQUIREMENT]`
- `[MEASURED OR BENCHMARK-DERIVED GPU-HOURS]`
- `[CPU/STORAGE REQUIREMENTS]`
- `[PROJECT START/END]`
- `[EXPECTED PUBLICATION / OUTPUT]`

These are real blockers, not cosmetic form blanks. Do not route the request until the workload can be named and costed.

## Compute estimate template

Do not guess a large number. Estimate from measured pilot/runtime or vendor/model benchmarks that match the intended serving setup.

For inference:

`models × cases × repeats × average runtime per case / effective GPU concurrency`

Then add:

- setup/validation runs;
- failed/replayed runs;
- reasonable sensitivity analysis.

For any fine-tuning/training, create a separate budget based on the actual method, precision, sequence length and dataset size.

At the advertised rate, the monetary request should be transparent:

`estimated H200 GPU-hours × NT$30`

The program is valuable because of access, reproducibility and institutional infrastructure—not because a larger GPU-hour number is inherently better.

## Internal email/memo points

A faculty or university contact should be able to understand the request in under one page:

1. current master's researcher/project affiliation;
2. exact research question;
3. why local GPU/HPC compute is needed;
4. approximate GPU-hours and estimated program cost;
5. expected research output;
6. how the workload supports YZU research/AI capacity;
7. links to the existing repository/evidence package.

## Claim-safe positioning

> Hardware-Splicer already has the deterministic software/MCP evaluation infrastructure and a frozen adversarial corpus. NCHC compute would be used to execute repeatable local/open-model evaluations; it is not being requested to substitute compute scale for missing research design.

## Pre-route checklist

- [ ] determine whether YZU already has an NCHC university-program contact/window;
- [ ] identify faculty/unit sponsor;
- [ ] identify actual open-weight model workload;
- [ ] benchmark or estimate real GPU-hour requirement;
- [ ] convert GPU-hours to the advertised NT$30/hour cost;
- [ ] do not describe API-provider runs as H200 workloads;
- [ ] preserve institutional correspondence/approval as a Gauntlet receipt;
- [ ] update package if YZU's institutional application imposes additional internal rules.
