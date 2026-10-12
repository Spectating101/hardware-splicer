/**
 * Claim boundary shown on the front door.
 *
 * Mirrors docs/product/claims-and-nonclaims.v1.json (schema hardware_splicer.claim_boundary.v1).
 * Do not edit wording here without editing the JSON: tests/test_frontend_claim_boundary_sync.py
 * fails when the two drift apart.
 */
export const CLAIM_BOUNDARY = {
  asOf: '2026-09-17',
  design: 'spi-flash-adapter-v1',
  commit: 'f892facd67c5124e2362860ebc999625afedc5d5',
  packageSha256: '6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd',
  physicalState: 'PACKAGED_NOT_PHYSICAL',
  supported: [
    {
      claim: 'The frozen SPI remote-FCT package is reproducible from the frozen source revision.',
      evidence: 'A fresh deterministic rebuild matched the published package SHA-256.',
    },
    {
      claim: 'The candidate includes editable CAD, manufacturing and assembly outputs, bounded host-test software, acceptance criteria, and an evidence-return contract.',
      evidence: 'The published remote-FCT package contains 24 audited outer ZIP members.',
    },
    {
      claim: 'Deterministic CAD/package checks pass for the frozen candidate.',
      evidence: 'Reference-design verification and remote-FCT campaign tests pass.',
    },
    {
      claim: 'One bounded primary-source Astra agent demonstration exists.',
      evidence: 'Canonical evidence ledger and run receipt; this is an existence demonstration only.',
    },
  ],
  notEstablished: [
    'The board has been fabricated, assembled, powered, or physically measured.',
    'Physical correctness or production readiness is established.',
    'An independent engineer, manufacturer, user, reviewer, or venue has validated the candidate.',
    'The full ten-case cross-condition agent reliability evaluation is complete.',
    'Hardware Splicer is OSHWA-certified, peer-reviewed, externally deployed, or universally safe.',
    'Model confidence, green CI, ERC/DRC, simulation, or package integrity grants physical authority.',
  ],
  promotion: [
    {
      stage: 'Physical evidence',
      requires: [
        'fabricated-unit revision identity',
        'cold inspection and continuity receipt',
        'controlled power and OE bring-up receipt',
        'read-only identification result with raw evidence',
      ],
    },
    {
      stage: 'Independent validation',
      requires: [
        'external evaluator identity and scope',
        'unaltered artifact identity',
        'durable verdict or review receipt',
      ],
    },
    {
      stage: 'Production readiness',
      requires: [
        'repeat-unit evidence',
        'environmental and reliability qualification',
        'documented manufacturing and operational limits',
      ],
    },
  ],
} as const;
