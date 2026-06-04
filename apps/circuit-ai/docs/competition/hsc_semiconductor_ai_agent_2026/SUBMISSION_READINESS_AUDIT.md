# Submission Readiness Audit

This audit is based on the competition announcement text provided in chat. It
does not include hidden requirements from the official PDF attachments because
those attachments are not in this repo.

## Announcement Requirements

| Requirement | From Announcement | Current Status | Action |
| --- | --- | --- | --- |
| Applicant eligibility | Participants must be enrolled at Yuan Ze University in September 2026 | Not proven in package | Fill school/program/student ID and confirm enrollment status |
| Team size | Teams of 1-3 members | Covered as solo applicant | Keep `solo` unless adding teammates |
| Application deadline | June 20, 2026, Saturday | Tracked in README | Submit before June 20, ideally by June 18-19 |
| Submission email | Send proposal and authorization agreement PDF to `carrielee@saturn.yzu.edu.tw` | Email draft exists | Fill personal fields and attach PDFs |
| Proposal PDF | Required | Draft and styled PDF generated | Replace `<fill in>` fields before final export |
| Authorization agreement PDF | Required | Checklist exists only | Complete the official attachment PDF manually |
| Shortlist result | June 30, 2026 | Tracked | Prepare light demo polish before this date |
| Development work | Complete AI Agent project during July-August 2026 | Roadmap exists | Use roadmap if shortlisted |
| Subsidy | NT$ 6,000/month, July and August, reimbursed by receipt and credit card slip | Mentioned in notes | Keep all token receipts and card transaction slips |
| Final presentation | September 2, 2026, 10:00-12:00 | Demo script exists | Build final 10-minute presentation after shortlist |
| Presentation format | 10-minute presentation + 5-minute Q&A | Demo script exists | Convert demo script into slides later |

## Current Package Readiness

Ready:

- proposal draft
- styled proposal PDF
- architecture one-pager PDF
- Traditional Chinese summary PDF
- email draft
- application snippets, including under-100-word project introduction
- July-August roadmap
- 10-minute demo script
- live showcase screenshots
- local demo route and backend proof

Not ready until user fills:

- applicant legal name
- department / program
- student ID
- contact email
- phone number, if official form asks
- enrollment confirmation for September 2026
- official authorization/consent form PDF
- public repo or project website field, if the form requires one

## Recommended Submission Attachments

Minimum required attachments:

```text
Proposal_CircuitAI_HardwareSplicer.pdf
Authorization_and_Consent_Form.pdf
```

Optional if the email allows extra attachments:

```text
Architecture_OnePager_CircuitAI.pdf
Executive_Summary_ZH_TW_CircuitAI.pdf
```

Do not overload the first email if the announcement only asks for two PDFs.
Mention that architecture/demo screenshots are included inside the proposal PDF.

## Proposal Fix Before Sending

The current proposal PDF still contains placeholders:

```text
<fill in>
```

Before final export, update:

- `PROPOSAL_CIRCUIT_AI_HARDWARE_SPLICER.md`
- `EMAIL_TO_CARRIE_LEE_DRAFT.md`
- official authorization PDF

Then regenerate:

```bash
npx playwright pdf \
  file:///home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai/docs/competition/hsc_semiconductor_ai_agent_2026/Proposal_CircuitAI_HardwareSplicer.html \
  docs/competition/hsc_semiconductor_ai_agent_2026/Proposal_CircuitAI_HardwareSplicer.pdf
```

If editing only Markdown, regenerate the HTML first using the local export
script/process used for this package.

## Form Field Strategy

If the application form asks for a short project/business introduction, use:

```text
Circuit.AI Hardware Splicer is an AI-agent workflow for understanding, repairing, and reusing circuit boards. It combines board photos, IC markings, public references, measured pinouts, voltage/current/thermal evidence, and bench test outcomes into a structured production authority casefile. Unlike a simple visual PCB labeler, it refuses unsafe overclaims: model output can suggest candidates and measurement tasks, but repair/reuse authority requires trusted physical evidence. The July-August work will extend the current live backend and frontend showcase into a multi-photo, bilingual semiconductor/electronics repair AI-agent demo.
```

If the form asks for a project website:

```text
GitHub: <public repo URL>
```

If GitHub is not accepted as a website, create a simple public project page
later. Do not block the proposal on this unless the official form requires it.

## Demo Preparation Before Submission

Do before sending if time allows:

- open `/showcase?state=release`
- record a 45-90 second screen capture
- click `Reference only`, show blocked authority
- click `Release ready`, show production repair authorized
- keep Qwen disabled while Alibaba quota/resources are exhausted

This gives a fallback artifact if they ask for proof after receiving the
proposal.

## After Submission

June 20-30:

- avoid major rewrites
- keep demo stable
- improve docs/screenshots if needed
- prepare bilingual labels lightly

After shortlist on June 30:

- spend serious engineering time
- use token subsidy only with receipts
- improve multi-photo intake and Qwen/native vision evaluation
- prepare final 10-minute presentation

## Main Risk

The biggest submission risk is not technical readiness. The package is already
credible. The biggest risks are administrative:

- missing official authorization PDF
- missing student/enrollment fields
- sending after deadline
- submitting too many optional attachments if they only expect two PDFs
- not keeping receipts if shortlisted

