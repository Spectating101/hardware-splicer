# AWS Cloud Credit for Research — Hardware-Splicer Route Note

**Route state:** VERIFY GEOGRAPHY → FIRE ONLY IF WORKLOAD IS REAL  
**Verified:** 2026-09-04  
**Official program:** https://aws.amazon.com/government-education/research-and-technical-computing/cloud-credit-for-research/  
**FAQ:** https://aws.amazon.com/government-education/research-and-technical-computing/cloud-credit-for-research/faqs/  
**Application page:** https://pages.awscloud.com/aws-cloud-credit-for-research.html

## Verified eligibility/mechanics

AWS currently states that eligible applicants include graduate, post-graduate and PhD students enrolled at accredited research institutions. Student awards are capped at **US$5,000 in AWS Promotional Credit**.

AWS expects a finite project in one of these categories:

1. proof of concept / benchmark comparison;
2. repeatable, shareable research solution;
3. advanced workshop/tutorial.

A complete project proposal is expected to describe:

- problem and project summary;
- specific AWS products/services;
- project timeline and milestones;
- plan for sharing outcomes;
- potential future AWS use;
- AWS contacts if any (not mandatory);
- AWS Public Data Sets if used.

An official institution-issued email and an AWS account number are required.

### Geographic blocker

The official global FAQ currently says AWS cannot process applications from the **“greater China region.”** The same AWS site also maintains a Taiwan-facing research/grants page. These facts do not resolve whether a Taiwan-based YZU applicant is accepted under this specific program.

**Do not prepare/final-submit a full application until AWS confirms Taiwan eligibility for this program in writing.**

### Review-time discrepancy

Current official AWS pages are inconsistent about typical review time: the main/FAQ material has stated longer review cycles while the application page can display a shorter range. Treat the live application page as operationally current, but do not base a time-critical project on a rapid decision.

## Portfolio-routing note

Across the broader portfolio, **Research Drive is probably the stronger primary asset** for this route because AWS explicitly values repeatable/shareable research solutions and cloud research workflows.

Hardware-Splicer should lead only if the proposed AWS workload is genuinely one of:

- a reproducible cloud-hosted agent-evaluation benchmark;
- a cloud-hosted research service/tool for executing and sharing the benchmark;
- a benchmark comparing cloud deployment/runtime approaches for the external-agent harness.

Do not force AWS services into Hardware-Splicer merely to obtain credits.

## Hardware-Splicer project option

### Working title

**Cloud-Reproducible Benchmarking of Evidence-Constrained AI Agents for Consequential Engineering Workflows**

### Problem

Agentic-system evaluations are often difficult to reproduce because model calls, tool state, evidence revisions and adjudication are distributed across ephemeral execution environments. Hardware-Splicer already persists model/tool traces and exact revision/evidence state. The proposed project would test whether the benchmark can be deployed as a repeatable cloud research workload with controlled execution, artifact persistence and reproducible run manifests.

### Project type

Primary: **proof of concept / benchmark**  
Secondary: **repeatable/shareable solution** if public research tooling is actually delivered.

## AWS service map — fill only after architecture is real

Do not submit a service salad.

Potential components, **only if actually selected**:

- `[COMPUTE SERVICE]` — benchmark runner / API service;
- `[OBJECT STORAGE]` — run manifests, traces, non-confidential artifacts;
- `[DATABASE]` — experiment metadata if needed;
- `[CONTAINER REGISTRY/ORCHESTRATION]` — only if containerized reproducibility is part of the design;
- `[OBSERVABILITY]` — only if measurements require it.

For every selected service state:

> why this service is needed + estimated usage + what output depends on it.

## Proposal skeleton

### 1. Problem statement

Explain reproducibility and state/evidence requirements for tool-using-agent research.

### 2. Existing foundation

Hardware-Splicer already provides:

- frozen adversarial corpus;
- canonical MCP/API surface;
- trace persistence;
- exact revision/evidence state;
- adjudication infrastructure.

### 3. Proposed cloud work

Deploy a bounded benchmark runner and artifact pipeline on AWS, execute a finite set of experiments, and publish reusable deployment/evaluation artifacts where permitted.

### 4. Milestones

**M1 — architecture + reproducible deployment**  
**M2 — pilot benchmark + cost measurement**  
**M3 — full bounded run + failure analysis**  
**M4 — public/shareable research artifact + report**

### 5. Sharing plan

Prefer concrete outputs:

- infrastructure/deployment manifest;
- benchmark runner;
- non-confidential trace schema/examples;
- technical report;
- reproducibility instructions.

### 6. Future AWS use

Do not promise indefinite AWS dependence. Explain only credible follow-on uses by the research group/community.

## Cost-budget rule

Use the AWS Pricing Calculator or measured pilot usage. Request only the amount justified by:

`compute + storage + data transfer + supporting services + modest failure/retry allowance`

Do not automatically request US$5,000.

## Pre-application eligibility email

The eligibility question should be narrow:

> I am a graduate student enrolled at Yuan Ze University in Taiwan. The Cloud Credit for Research FAQ states that applications from the “greater China region” cannot currently be processed, while AWS also maintains Taiwan-specific research program pages. For this specific program, are applicants enrolled at accredited universities in Taiwan currently eligible to apply?

Do not send project marketing in the eligibility email; get a yes/no jurisdiction answer first.

## Pre-submit checklist

- [ ] written Taiwan eligibility confirmation;
- [ ] institutional email available;
- [ ] AWS account created and appropriate for promotional credits;
- [ ] project is finite, not general lab funding;
- [ ] exact AWS architecture selected;
- [ ] service-level usage/budget calculated;
- [ ] milestones and sharing plan fixed;
- [ ] cloud deployment is genuinely part of the research question/output;
- [ ] no pending live/physical evidence overstated;
- [ ] preserve application and decision receipts.
