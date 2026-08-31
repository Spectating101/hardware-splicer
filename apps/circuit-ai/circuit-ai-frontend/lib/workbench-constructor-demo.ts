import type { AuthorityState } from './workbench-demo';

export type ConstructorResourceKind = 'owned' | 'salvaged' | 'procurable' | 'designed';
export type ConstructorDecision = 'reuse' | 'reuse_pending' | 'buy' | 'generate' | 'hold' | 'reject';
export type RequirementState = 'pass' | 'partial' | 'unknown' | 'blocked';
export type CandidateRisk = 'low' | 'medium' | 'high';
export type ProposalOperation = 'REUSE' | 'ADD' | 'REPLACE' | 'GENERATE' | 'CONNECT' | 'MEASURE' | 'REJECT';
export type ProposalState = 'ready' | 'held' | 'accepted' | 'rejected';

export type ConstructorResource = {
  id: string;
  name: string;
  kind: ConstructorResourceKind;
  role: string;
  decision: ConstructorDecision;
  authority: AuthorityState;
  costNtd: number;
  mappedEntityId?: string;
  capabilities: string[];
  note: string;
};

export type TargetRequirement = {
  id: string;
  label: string;
  target: string;
  hard: boolean;
};

export type ArchitectureCandidate = {
  id: 'balanced' | 'max-reuse' | 'low-risk';
  name: string;
  strategyMode: 'hybrid' | 'constrained' | 'open_procurement';
  tagline: string;
  costNtd: number;
  reusePercent: number;
  risk: CandidateRisk;
  blockerCount: number;
  unknownCount: number;
  requirementStates: Record<string, RequirementState>;
  resourceIds: string[];
  proposalIds: string[];
  note: string;
};

export type ConstructorProposal = {
  id: string;
  candidateId: ArchitectureCandidate['id'];
  operation: ProposalOperation;
  title: string;
  resourceId?: string;
  entityId?: string;
  state: ProposalState;
  rationale: string;
  consequence: string;
};

export const constructorTarget = {
  title: 'Portable Linux workstation',
  prompt: 'Build a serviceable portable x86 Linux workstation from available donor hardware, buying only where reuse is not defensible.',
};

export const constructorRequirements: TargetRequirement[] = [
  { id: 'compute', label: 'Linux-capable x86 compute', target: 'development-class x86', hard: true },
  { id: 'display', label: 'Integrated display', target: '13-inch class', hard: true },
  { id: 'input', label: 'Integrated keyboard', target: 'USB HID or validated equivalent', hard: true },
  { id: 'storage', label: 'Replaceable storage', target: 'NVMe', hard: true },
  { id: 'io', label: 'External I/O', target: '2× USB + networking', hard: true },
  { id: 'power', label: 'Rechargeable portable power', target: 'removable / serviceable', hard: true },
  { id: 'runtime', label: 'Runtime', target: '≥ 6 h target', hard: false },
  { id: 'mass', label: 'Mass', target: '≤ 2.8 kg target', hard: false },
  { id: 'cash', label: 'Additional cash', target: '≤ NT$12,000', hard: false },
  { id: 'service', label: 'Serviceability', target: 'non-destructive access', hard: true },
  { id: 'highspeed', label: 'High-speed link policy', target: 'retain validated native paths', hard: true },
];

export const constructorResources: ConstructorResource[] = [
  {
    id: 'res-mainboard-donor',
    name: 'Donor x86 mainboard',
    kind: 'salvaged',
    role: 'compute',
    decision: 'reuse_pending',
    authority: 'partial',
    costNtd: 0,
    mappedEntityId: 'cmp-mainboard',
    capabilities: ['x86 compute', 'NVMe', 'Wi-Fi', 'native display', 'USB'],
    note: 'Strong reuse candidate if board revision, DC input and mounting evidence close.',
  },
  {
    id: 'res-mainboard-documented',
    name: 'Documented modular x86 board',
    kind: 'procurable',
    role: 'compute',
    decision: 'buy',
    authority: 'verified',
    costNtd: 7200,
    mappedEntityId: 'cmp-mainboard',
    capabilities: ['x86 compute', 'NVMe', 'documented power', 'documented I/O'],
    note: 'Higher cash cost but materially reduces integration and service risk.',
  },
  {
    id: 'res-display-controlled',
    name: 'Donor display + validated controller',
    kind: 'salvaged',
    role: 'display',
    decision: 'reuse_pending',
    authority: 'partial',
    costNtd: 0,
    mappedEntityId: 'cmp-display',
    capabilities: ['display', 'validated video path'],
    note: 'Preferred donor path when controller, cable and panel stay together.',
  },
  {
    id: 'res-display-raw',
    name: 'Raw donor LCD panel',
    kind: 'salvaged',
    role: 'display',
    decision: 'hold',
    authority: 'unknown',
    costNtd: 0,
    mappedEntityId: 'cmp-display',
    capabilities: ['display'],
    note: 'Free hardware, but pinout, link type, supply and backlight remain unresolved.',
  },
  {
    id: 'res-display-documented',
    name: 'Documented portable display',
    kind: 'procurable',
    role: 'display',
    decision: 'buy',
    authority: 'verified',
    costNtd: 2900,
    mappedEntityId: 'cmp-display',
    capabilities: ['display', 'HDMI/USB-C'],
    note: 'Lower evidence burden and lower integration risk than a raw donor panel.',
  },
  {
    id: 'res-keyboard-donor',
    name: 'Donor USB keyboard assembly',
    kind: 'salvaged',
    role: 'input',
    decision: 'reuse_pending',
    authority: 'partial',
    costNtd: 0,
    mappedEntityId: 'cmp-keyboard',
    capabilities: ['keyboard', 'USB HID'],
    note: 'Reuse complete HID path first; deeper matrix transformation remains optional.',
  },
  {
    id: 'res-battery-old',
    name: 'Unknown old lithium pack',
    kind: 'salvaged',
    role: 'power',
    decision: 'reject',
    authority: 'blocked',
    costNtd: 0,
    mappedEntityId: 'cmp-battery',
    capabilities: ['battery'],
    note: 'Maximum-reuse policy cannot override unknown chemistry, protection and condition.',
  },
  {
    id: 'res-battery-new',
    name: 'Known removable battery pack',
    kind: 'procurable',
    role: 'power',
    decision: 'buy',
    authority: 'proposed',
    costNtd: 1900,
    mappedEntityId: 'cmp-battery',
    capabilities: ['battery', 'BMS'],
    note: 'Preferred power source once voltage/current envelope is matched to compute demand.',
  },
  {
    id: 'res-pd-module',
    name: 'Documented USB-C PD power path',
    kind: 'procurable',
    role: 'power',
    decision: 'buy',
    authority: 'blocked',
    costNtd: 850,
    mappedEntityId: 'cmp-pd',
    capabilities: ['charging', 'PD', 'power conversion'],
    note: 'Selection remains blocked until battery and compute envelopes are measured.',
  },
  {
    id: 'res-cooling-donor',
    name: 'Donor cooling assembly',
    kind: 'salvaged',
    role: 'thermal',
    decision: 'reuse_pending',
    authority: 'partial',
    costNtd: 0,
    mappedEntityId: 'cmp-cooling',
    capabilities: ['heatsink', 'fan'],
    note: 'Retain the original cooling island if fit, control and thermal evidence remain valid.',
  },
  {
    id: 'res-shell-generated',
    name: 'Generated serviceable chassis',
    kind: 'designed',
    role: 'structure',
    decision: 'generate',
    authority: 'proposed',
    costNtd: 1100,
    mappedEntityId: 'cmp-enclosure',
    capabilities: ['enclosure', 'mounting', 'service access'],
    note: 'Generated around measured donor geometry; exact B-rep and fabrication remain later gates.',
  },
];

export const constructorProposals: ConstructorProposal[] = [
  { id: 'p-balanced-compute', candidateId: 'balanced', operation: 'REUSE', title: 'Reuse donor x86 compute island', resourceId: 'res-mainboard-donor', entityId: 'cmp-mainboard', state: 'ready', rationale: 'Preserves high-value donor compute without redesigning native high-speed links.', consequence: 'Requires board identity, input-power and mounting evidence before release.' },
  { id: 'p-balanced-display', candidateId: 'balanced', operation: 'REUSE', title: 'Retain donor display controller path', resourceId: 'res-display-controlled', entityId: 'cmp-display', state: 'held', rationale: 'Reuses the display while avoiding a raw-panel interface redesign.', consequence: 'Held until panel/controller identity and power contract are observed.' },
  { id: 'p-balanced-power', candidateId: 'balanced', operation: 'ADD', title: 'Add known battery + documented PD path', resourceId: 'res-battery-new', entityId: 'ss-power', state: 'held', rationale: 'Avoids ambiguous lithium reuse and provides a bounded power architecture.', consequence: 'Cannot close until peak compute demand and PD profiles are measured.' },
  { id: 'p-balanced-shell', candidateId: 'balanced', operation: 'GENERATE', title: 'Generate serviceable chassis around measured geometry', resourceId: 'res-shell-generated', entityId: 'cmp-enclosure', state: 'ready', rationale: 'Lets donor components remain replaceable and preserves service access.', consequence: 'Geometry is only a proposal until fit/clearance evidence exists.' },

  { id: 'p-reuse-compute', candidateId: 'max-reuse', operation: 'REUSE', title: 'Reuse donor x86 mainboard', resourceId: 'res-mainboard-donor', entityId: 'cmp-mainboard', state: 'ready', rationale: 'Highest retained donor value for compute.', consequence: 'Same evidence gates as every other strategy.' },
  { id: 'p-reuse-display', candidateId: 'max-reuse', operation: 'MEASURE', title: 'Characterize raw donor LCD before reuse', resourceId: 'res-display-raw', entityId: 'cmp-display', state: 'held', rationale: 'Potentially raises reuse materially if the panel can be identified safely.', consequence: 'Candidate remains blocked on pinout, supply and backlight evidence.' },
  { id: 'p-reuse-battery', candidateId: 'max-reuse', operation: 'REJECT', title: 'Reject unknown lithium despite reuse objective', resourceId: 'res-battery-old', entityId: 'cmp-battery', state: 'rejected', rationale: 'Reuse preference cannot weaken hazard/evidence gates.', consequence: 'A known battery must still be procured.' },
  { id: 'p-reuse-shell', candidateId: 'max-reuse', operation: 'GENERATE', title: 'Adapt shell around maximum donor retention', resourceId: 'res-shell-generated', entityId: 'cmp-enclosure', state: 'ready', rationale: 'Structural design absorbs donor geometry rather than replacing working modules.', consequence: 'Higher integration burden and more geometry evidence.' },

  { id: 'p-risk-compute', candidateId: 'low-risk', operation: 'REPLACE', title: 'Replace uncertain donor compute with documented board', resourceId: 'res-mainboard-documented', entityId: 'cmp-mainboard', state: 'ready', rationale: 'Trades cash for documented power, mounting and I/O.', consequence: 'Lower reuse and higher procurement cost.' },
  { id: 'p-risk-display', candidateId: 'low-risk', operation: 'REPLACE', title: 'Use documented portable display', resourceId: 'res-display-documented', entityId: 'cmp-display', state: 'ready', rationale: 'Removes the raw-panel evidence burden.', consequence: 'Adds procurement cost but materially lowers integration risk.' },
  { id: 'p-risk-power', candidateId: 'low-risk', operation: 'ADD', title: 'Use known battery and documented PD path', resourceId: 'res-battery-new', entityId: 'ss-power', state: 'held', rationale: 'Keeps the power system on documented components.', consequence: 'Still requires whole-machine load and runtime evidence.' },
  { id: 'p-risk-shell', candidateId: 'low-risk', operation: 'GENERATE', title: 'Generate modular service chassis', resourceId: 'res-shell-generated', entityId: 'cmp-enclosure', state: 'ready', rationale: 'Makes future component replacement and selective evidence invalidation cheaper.', consequence: 'New fabrication work replaces some donor reuse.' },
];

export const constructorCandidates: ArchitectureCandidate[] = [
  {
    id: 'balanced',
    name: 'Balanced',
    strategyMode: 'hybrid',
    tagline: 'Reuse proven islands, buy only the risky gaps.',
    costNtd: 3850,
    reusePercent: 58,
    risk: 'medium',
    blockerCount: 3,
    unknownCount: 8,
    resourceIds: ['res-mainboard-donor', 'res-display-controlled', 'res-keyboard-donor', 'res-battery-new', 'res-pd-module', 'res-cooling-donor', 'res-shell-generated'],
    proposalIds: ['p-balanced-compute', 'p-balanced-display', 'p-balanced-power', 'p-balanced-shell'],
    requirementStates: { compute: 'partial', display: 'unknown', input: 'partial', storage: 'pass', io: 'partial', power: 'blocked', runtime: 'unknown', mass: 'unknown', cash: 'pass', service: 'partial', highspeed: 'pass' },
    note: 'Current working candidate. It maximizes rational reuse without forcing uncertain battery or raw-panel assumptions.',
  },
  {
    id: 'max-reuse',
    name: 'Maximum reuse',
    strategyMode: 'constrained',
    tagline: 'Push donor retention until evidence or safety says stop.',
    costNtd: 2950,
    reusePercent: 76,
    risk: 'high',
    blockerCount: 5,
    unknownCount: 13,
    resourceIds: ['res-mainboard-donor', 'res-display-raw', 'res-keyboard-donor', 'res-battery-new', 'res-pd-module', 'res-cooling-donor', 'res-shell-generated'],
    proposalIds: ['p-reuse-compute', 'p-reuse-display', 'p-reuse-battery', 'p-reuse-shell'],
    requirementStates: { compute: 'partial', display: 'blocked', input: 'partial', storage: 'pass', io: 'partial', power: 'blocked', runtime: 'unknown', mass: 'unknown', cash: 'pass', service: 'partial', highspeed: 'blocked' },
    note: 'Useful exploration candidate, but it cannot authorize the raw display or unknown lithium simply because they are free donor parts.',
  },
  {
    id: 'low-risk',
    name: 'Lowest integration risk',
    strategyMode: 'open_procurement',
    tagline: 'Prefer documented modules where they beat uncertain reuse.',
    costNtd: 11950,
    reusePercent: 27,
    risk: 'low',
    blockerCount: 1,
    unknownCount: 4,
    resourceIds: ['res-mainboard-documented', 'res-display-documented', 'res-keyboard-donor', 'res-battery-new', 'res-pd-module', 'res-cooling-donor', 'res-shell-generated'],
    proposalIds: ['p-risk-compute', 'p-risk-display', 'p-risk-power', 'p-risk-shell'],
    requirementStates: { compute: 'pass', display: 'pass', input: 'partial', storage: 'pass', io: 'pass', power: 'partial', runtime: 'unknown', mass: 'unknown', cash: 'pass', service: 'pass', highspeed: 'pass' },
    note: 'Near the cash ceiling, but the architecture removes most undocumented high-speed and identity risk.',
  },
];

export const constructorCandidateMap = new Map(constructorCandidates.map((candidate) => [candidate.id, candidate]));
export const constructorResourceMap = new Map(constructorResources.map((resource) => [resource.id, resource]));
export const constructorProposalMap = new Map(constructorProposals.map((proposal) => [proposal.id, proposal]));
