# Post-freeze audit: 9 repair video diversity outcomes

This folder is on a **new branch**, following the frozen prediction in
commit 79d6620c9b8fc7f18ac5151e59683b7538024218 (PR #320).

- Locked predictions SHA-256:
  b966c3866051cd9c606b6fcacccb6d1b2be2bd474efc8e65af3f9a9ba0c9f4d8
- Later video excerpts: creator-spoken explanations recovered from the
  YouTube English auto-captions, with times in creator_narrative_outcomes.json.
  **The initial branch did not contain these labels.**
- Reviewer: the SAME ChatGPT assistant that authored the frozen predictions.
  This is a transparent exploratory adjudication, NOT independent or blind
  third-party outcome verification.
- No frame-by-frame video vision, independent electrical measurements,
  purchased spare parts, or physical repairs by HS.

This is deliberately a *fault-level* score, not "the model mentioned one
component somewhere, therefore 7/7 repairs solved." The DeLonghi has at
least two creator-reported independent faults; the tablet likewise has more
than one mechanism. Broad "controller failure" is only partial credit when
the real fault was a particular diode, not an exact diode diagnosis.

Preliminary 9-device, 9-fault result:
- 7 creator repairs have sufficiently described results for scoring.
- 2 cases remain unscored: Canon's ORIGINAL no-power mechanism was not
  established; the Xbox has not been adjudicated in this review.
- 9 reported fault mechanisms scored: 5 exact fault-family predictions,
  3 broad component-domain guesses, 1 missed mechanism.
- Only 2/9 exact faults first-ranked.
- Only 3/7 evaluable devices had ALL reported root causes matched at exact
  fault-family level.

These are *external GPT-6 text-control* numbers. HS native rule-based
triage still accepted 0/9 free-text inputs without manual observation codes.
No statistical generalization is supported by 7 curated cases; the creator
videos are weaker than independent instrument-verified truth.

Reproduce:
    python3 examples/restoration_video_bench/diversity/postreview/score_faults.py
    PYTHONPATH=src python3 -m pytest -q tests/test_restoration_diversity_postreview.py

A meaningful next experiment must wire a real inference-capable agent to the
native HS intake, with genuine source evidence from images/transcript and
instruments, then repeat against *new* cases without revising guesses after
outcome discovery. Do not tune the engine to achieve these seven creator fixes.
