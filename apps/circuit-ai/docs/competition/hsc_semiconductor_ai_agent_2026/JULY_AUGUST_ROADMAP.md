# July-August Roadmap

## Goal

Convert the current backend-ready prototype into a competition-ready AI-agent
demo with live visual intake, measured evidence closure, bilingual presentation,
and real-board evaluation.

## Before Shortlist Announcement

Dates: June 3-June 30, 2026

- finalize proposal package
- record a short local demo video or GIF
- keep Qwen disabled while quota is exhausted
- avoid large frontend rewrites
- prepare small set of board photos and sample payloads
- identify official proposal formatting requirements from attachments

## July Week 1 - Demo Stabilization

- freeze the main demo route
- add local sample data loader
- add bilingual labels for main demo states
- improve visual flow for reference -> measured -> release
- write final evaluator checklist

## July Week 2 - Multi-Photo Intake

- implement or polish multi-photo intake UI
- support wide shot, connector closeup, marking closeup, damage closeup
- fuse observations into `board_evidence.v1`
- preserve source refs per observation
- generate next-capture requests when evidence is weak

## July Week 3 - Qwen/Vision Trial

- re-enable Qwen only if provider-side free-quota stop is confirmed
- use low-cost Qwen VL models first
- run only cached, budgeted board evidence tests
- compare Qwen output against local/Copilot/DeepSeek-assisted baseline
- document where native vision helps and where it does not

## July Week 4 - Real Board Case Corpus

- collect at least 5 controlled low-voltage board cases
- for each case, record:
  - photos
  - candidate board evidence
  - bench topology capture
  - terminal outcome
  - release or blocked decision
- update screenshots and demo flow

## August Week 1 - Measurement Workflow

- polish continuity/resistance/voltage/current/thermal evidence entry
- improve authority ladder explanations
- add exportable production casefile view
- verify weak evidence remains blocked

## August Week 2 - Final AI Agent Flow

- connect visual intake to measured authority demo
- add model status and budget status to demo
- add bilingual presentation labels
- add final 10-minute demo mode

## August Week 3 - Evaluation

- run corpus evaluation
- record before/after authority scores
- write final report:
  - what the model extracted
  - what measurements closed
  - what remained blocked
  - where the agent improved workflow speed or safety

## August Week 4 - Presentation Freeze

- freeze code used for final demo
- record fallback video
- prepare final slides
- prepare Q&A answers
- test local/offline fallback
- prepare printed architecture one-pager

## Final Presentation

Date: September 2, 2026

Deliver:

- 10-minute live demo
- 5-minute Q&A
- short technical architecture
- real-board case evidence
- final roadmap beyond competition

