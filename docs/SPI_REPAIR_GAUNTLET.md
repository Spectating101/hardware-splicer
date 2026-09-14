# SPI Repair Gauntlet v1

Status: zero-inference challenge pack stacked on Derived Virtual Lab v1.

The gauntlet exists to make a future frontier-model repair experiment small, bounded, and
scorable. No live model is needed to build or validate it.

## What is frozen

Twelve challenges are derived from the green 512-case virtual lab:

- seven clean-background local defects where a correct repair should return the candidate to
  derived `safe`;
- five mixed challenges where the injected local defect is repairable but an independent
  timing/current constraint must remain visible, so the correct post-repair outcome is still
  derived `unsafe`.

The actor-facing packet does **not** contain the hidden fault profile, expected post-repair
outcome, or scripted repair action.

## Actor packet

Each packet contains only:

- a bounded mission;
- the engineering candidate state;
- currently failing/blocking verifier findings;
- allowed mutation paths;
- the authority boundary; and
- the output contract.

The actor must return a complete candidate object, preserve every unlisted field, avoid adding
fields, and stay inside the declared mutation scope.

The v1 resource ceiling is:

```text
max packet: 12,000 UTF-8 JSON bytes
all 12 packets combined: 96,000 bytes
```

This is deliberately tiny compared with the prior raw-document Astra runs. It allows a future
model evaluation to test repair behavior rather than spend hundreds of thousands of tokens
rediscovering experiment plumbing.

## Scoring

`score_repair()` fails closed unless all conditions hold:

1. candidate schema is exact;
2. at least one engineering field changed;
3. every changed path is inside the challenge-specific mutation scope;
4. the injected defect's deterministic check becomes `pass`;
5. the resulting overall outcome matches the hidden expected post-repair outcome; and
6. physical/manufacturer-model authority remains closed.

A mixed challenge can therefore receive full repair credit while still being globally
`unsafe`. This is intentional: an actor must repair the requested defect without hiding an
independent timing/current blocker.

## Scripted control

The existing deterministic repair control is run against all twelve challenges before any
model is permitted to use the pack. It demonstrates that the scorer and challenge definitions
are internally solvable.

Passing this control is not evidence of AI competence.

## Artifacts

Run:

```bash
python scripts/run_spi_repair_gauntlet.py \
  --out-dir artifacts/spi_repair_gauntlet_v1
```

Outputs:

- `actor_packets.json` — the only challenge material intended for an evaluated model;
- `private_gold_manifest.json` — scorer/operator gold metadata; do not expose to the actor;
- `scripted_control_report.json` — non-AI baseline;
- `summary.json` — resource and pass/fail summary.

## Future live-model use

A live model experiment should operate in a clean room with repository/gold access denied. For
one challenge, provide only the selected actor packet. The model proposes a candidate repair;
Hardware Splicer then scores that proposal deterministically.

The first live run should be **one challenge**, not all twelve. The matrix can expand only after
one complete repair transaction is captured and audited.

## Claim boundary

The gauntlet is derived/surrogate evidence. It does not establish manufacturer-model behavior,
physical correctness, fabrication readiness, power-on readiness, or physical authority.

No Astra execution is part of this tranche.
