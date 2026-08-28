export type AuthorityState = 'verified' | 'partial' | 'unknown' | 'blocked' | 'proposed';
export type WorkbenchEntityKind = 'machine' | 'subsystem' | 'component';
export type ResourceSource = 'output' | 'donor' | 'new' | 'generated' | 'external';

export type SpatialEntity = {
  position: [number, number, number];
  size: [number, number, number];
};

export type WorkbenchEntity = {
  id: string;
  name: string;
  kind: WorkbenchEntityKind;
  parentId: string | null;
  source: ResourceSource;
  authority: AuthorityState;
  summary: string;
  domain: string;
  spatial?: SpatialEntity;
  facts: Array<{ label: string; value: string }>;
  unresolved: string[];
  children: string[];
};

export type WorkbenchInterface = {
  id: string;
  name: string;
  from: string;
  to: string;
  kind: string;
  authority: AuthorityState;
  unresolved: string[];
};

export type WorkbenchEvidence = {
  id: string;
  title: string;
  entityId: string;
  state: AuthorityState;
  method: string;
  note: string;
};

export type WorkbenchConstraint = {
  id: string;
  title: string;
  entityId: string;
  severity: 'blocking' | 'warning';
  state: 'open' | 'satisfied';
  note: string;
};

export type WorkbenchVerification = {
  id: string;
  title: string;
  entityId: string;
  state: 'planned' | 'passed' | 'blocked';
  method: string;
};

export type WorkbenchHistoryEvent = {
  id: string;
  at: string;
  entityId: string;
  title: string;
  note: string;
};

export const deck001Entities: WorkbenchEntity[] = [
  {
    id: 'deck-001',
    name: 'DECK-001',
    kind: 'machine',
    parentId: null,
    source: 'output',
    authority: 'blocked',
    summary: 'Synthetic modular Linux cyberdeck used to exercise machine-scale HS interaction and evidence semantics.',
    domain: 'system',
    facts: [
      { label: 'Revision', value: 'R0 / architecture' },
      { label: 'Release request', value: 'concept' },
      { label: 'Machine class', value: 'portable Linux workstation' },
    ],
    unresolved: ['battery / PD architecture', 'display electrical contract', 'thermal envelope'],
    children: ['ss-compute', 'ss-display', 'ss-input', 'ss-power', 'ss-storage', 'ss-io', 'ss-thermal', 'ss-enclosure'],
  },
  {
    id: 'ss-compute',
    name: 'Compute',
    kind: 'subsystem',
    parentId: 'deck-001',
    source: 'output',
    authority: 'partial',
    summary: 'x86 compute, firmware and native high-speed I/O anchor.',
    domain: 'electrical / software',
    facts: [{ label: 'Candidate', value: 'donor x86 mini-PC mainboard' }],
    unresolved: ['exact board revision', 'sustained power envelope'],
    children: ['cmp-mainboard'],
  },
  {
    id: 'cmp-mainboard',
    name: 'Donor x86 mainboard',
    kind: 'component',
    parentId: 'ss-compute',
    source: 'donor',
    authority: 'partial',
    summary: 'Preferred validated island: retain native CPU/RAM/NVMe/Wi-Fi/display interfaces and cooling attachment.',
    domain: 'electrical',
    spatial: { position: [-1.6, 0.45, 0.35], size: [4.2, 0.35, 2.8] },
    facts: [
      { label: 'Reuse decision', value: 'REUSE_PENDING' },
      { label: 'High-speed policy', value: 'retain manufacturer-native paths' },
    ],
    unresolved: ['board identity', 'DC input profile', 'mount coordinates'],
    children: [],
  },
  {
    id: 'ss-display',
    name: 'Display',
    kind: 'subsystem',
    parentId: 'deck-001',
    source: 'output',
    authority: 'unknown',
    summary: 'Integrated display with evidence-bounded electrical and mechanical interfaces.',
    domain: 'electrical / mechanical',
    facts: [{ label: 'Target', value: '13-inch class integrated display' }],
    unresolved: ['panel identity', 'link type', 'supply voltage', 'backlight power'],
    children: ['cmp-display'],
  },
  {
    id: 'cmp-display',
    name: 'Donor display assembly',
    kind: 'component',
    parentId: 'ss-display',
    source: 'donor',
    authority: 'unknown',
    summary: 'Prefer a donor portable-monitor assembly with its validated HDMI/USB-C controller; raw panel stays held until characterized.',
    domain: 'electrical / mechanical',
    spatial: { position: [0, 4.15, -3.2], size: [9.7, 5.4, 0.28] },
    facts: [
      { label: 'Reuse decision', value: 'REUSE_PENDING' },
      { label: 'Preferred path', value: 'validated controller + cable' },
    ],
    unresolved: ['panel identity', 'connector pinout', 'lane count', 'panel voltage', 'backlight power'],
    children: [],
  },
  {
    id: 'ss-input',
    name: 'Input',
    kind: 'subsystem',
    parentId: 'deck-001',
    source: 'output',
    authority: 'partial',
    summary: 'Integrated keyboard and pointing input.',
    domain: 'electrical / mechanical',
    facts: [{ label: 'Preferred transport', value: 'USB HID' }],
    unresolved: ['final physical adaptation'],
    children: ['cmp-keyboard'],
  },
  {
    id: 'cmp-keyboard',
    name: 'Donor keyboard assembly',
    kind: 'component',
    parentId: 'ss-input',
    source: 'donor',
    authority: 'partial',
    summary: 'Reuse complete USB HID path where practical; deeper matrix transformation is optional, not assumed.',
    domain: 'electrical',
    spatial: { position: [0.6, 0.72, 2.65], size: [8.1, 0.24, 2.45] },
    facts: [{ label: 'Reuse decision', value: 'REUSE_PENDING' }],
    unresolved: ['mounting geometry', 'pointing-device choice'],
    children: [],
  },
  {
    id: 'ss-power',
    name: 'Power',
    kind: 'subsystem',
    parentId: 'deck-001',
    source: 'output',
    authority: 'blocked',
    summary: 'Rechargeable removable battery, charging and system power path.',
    domain: 'electrical / safety',
    facts: [{ label: 'Physical authority', value: 'BLOCKED' }],
    unresolved: ['battery chemistry/BMS', 'PD profiles', 'peak current', 'charge-while-operating behavior'],
    children: ['cmp-battery', 'cmp-pd'],
  },
  {
    id: 'cmp-battery',
    name: 'New battery pack',
    kind: 'component',
    parentId: 'ss-power',
    source: 'new',
    authority: 'proposed',
    summary: 'Known-good removable rechargeable pack; old ambiguous lithium donor is intentionally rejected.',
    domain: 'electrical / safety',
    spatial: { position: [2.7, 0.48, 0.25], size: [3.6, 0.48, 2.6] },
    facts: [{ label: 'Donor alternative', value: 'REJECT — insufficient battery evidence' }],
    unresolved: ['pack selection', 'BMS limits', 'thermal boundary'],
    children: [],
  },
  {
    id: 'cmp-pd',
    name: 'USB-C PD / power-path module',
    kind: 'component',
    parentId: 'ss-power',
    source: 'new',
    authority: 'blocked',
    summary: 'Charging and rail bridge. Selection remains blocked until compute and battery envelopes are known.',
    domain: 'electrical / safety',
    spatial: { position: [4.0, 0.58, -1.65], size: [1.3, 0.3, 0.8] },
    facts: [{ label: 'Selection state', value: 'BLOCKED_BY_INPUTS' }],
    unresolved: ['PD profile', 'connector current', 'power-on sequence'],
    children: [],
  },
  {
    id: 'ss-storage',
    name: 'Storage',
    kind: 'subsystem',
    parentId: 'deck-001',
    source: 'output',
    authority: 'verified',
    summary: 'Replaceable NVMe storage using the donor board native slot.',
    domain: 'electrical',
    facts: [{ label: 'Policy', value: 'reuse native M.2 path' }],
    unresolved: [],
    children: ['cmp-nvme'],
  },
  {
    id: 'cmp-nvme',
    name: 'NVMe SSD',
    kind: 'component',
    parentId: 'ss-storage',
    source: 'external',
    authority: 'verified',
    summary: 'Known-good storage on an existing validated interface.',
    domain: 'electrical',
    spatial: { position: [-1.35, 0.78, 0.2], size: [1.7, 0.1, 0.65] },
    facts: [{ label: 'Interface', value: 'native M.2 / NVMe' }],
    unresolved: [],
    children: [],
  },
  {
    id: 'ss-io',
    name: 'External I/O',
    kind: 'subsystem',
    parentId: 'deck-001',
    source: 'output',
    authority: 'partial',
    summary: 'USB expansion and networking through native or documented adapters.',
    domain: 'electrical',
    facts: [{ label: 'Minimum', value: '2× USB + networking' }],
    unresolved: ['final downstream USB power budget'],
    children: ['cmp-hub'],
  },
  {
    id: 'cmp-hub',
    name: 'USB hub / breakout',
    kind: 'component',
    parentId: 'ss-io',
    source: 'new',
    authority: 'proposed',
    summary: 'Documented hub or breakout; no novel USB3 routing in v0 architecture.',
    domain: 'electrical',
    spatial: { position: [-4.2, 0.58, -1.3], size: [1.2, 0.25, 0.85] },
    facts: [{ label: 'High-speed policy', value: 'documented adapter only' }],
    unresolved: ['upstream power budget'],
    children: [],
  },
  {
    id: 'ss-thermal',
    name: 'Thermal',
    kind: 'subsystem',
    parentId: 'deck-001',
    source: 'output',
    authority: 'blocked',
    summary: 'Retain donor cooling when compatible; sustained-operation claim requires measured thermal evidence.',
    domain: 'mechanical / verification',
    facts: [{ label: 'Automated design depth', value: 'bounded / empirical' }],
    unresolved: ['workload envelope', 'battery-adjacent temperature', 'airflow path'],
    children: ['cmp-cooling'],
  },
  {
    id: 'cmp-cooling',
    name: 'Donor cooling assembly',
    kind: 'component',
    parentId: 'ss-thermal',
    source: 'donor',
    authority: 'partial',
    summary: 'Reuse original heatsink/fan if fit and fan control remain compatible.',
    domain: 'mechanical',
    spatial: { position: [-2.6, 0.82, -0.8], size: [1.6, 0.45, 1.5] },
    facts: [{ label: 'Reuse decision', value: 'REUSE_PENDING' }],
    unresolved: ['chassis clearance', 'airflow opening'],
    children: [],
  },
  {
    id: 'ss-enclosure',
    name: 'Enclosure',
    kind: 'subsystem',
    parentId: 'deck-001',
    source: 'output',
    authority: 'proposed',
    summary: 'Generated serviceable chassis with evidence-bound clearances and access paths.',
    domain: 'mechanical',
    facts: [{ label: 'Serviceability', value: 'non-destructive opening required' }],
    unresolved: ['final measured geometry', 'hinge/cable bend region'],
    children: ['cmp-enclosure'],
  },
  {
    id: 'cmp-enclosure',
    name: 'Generated chassis',
    kind: 'component',
    parentId: 'ss-enclosure',
    source: 'generated',
    authority: 'proposed',
    summary: 'Machine-level spatial output; exact B-rep generation is deliberately outside this v0 UI slice.',
    domain: 'mechanical',
    spatial: { position: [0, 0, 0], size: [10.6, 0.55, 6.8] },
    facts: [{ label: 'Geometry state', value: 'PROPOSED ENVELOPE' }],
    unresolved: ['port apertures', 'fastener stack', 'lid articulation'],
    children: [],
  },
];

export const deck001Interfaces: WorkbenchInterface[] = [
  { id: 'if-display', name: 'Compute → display', from: 'cmp-mainboard', to: 'cmp-display', kind: 'video', authority: 'unknown', unresolved: ['protocol', 'pinout', 'supply', 'backlight'] },
  { id: 'if-power', name: 'Power → compute', from: 'cmp-pd', to: 'cmp-mainboard', kind: 'power', authority: 'blocked', unresolved: ['voltage profile', 'peak current', 'connector rating'] },
  { id: 'if-input', name: 'Keyboard → compute', from: 'cmp-keyboard', to: 'cmp-mainboard', kind: 'USB HID', authority: 'partial', unresolved: ['final integration path'] },
  { id: 'if-storage', name: 'Compute → NVMe', from: 'cmp-mainboard', to: 'cmp-nvme', kind: 'PCIe/NVMe', authority: 'verified', unresolved: [] },
  { id: 'if-usb', name: 'Compute → USB breakout', from: 'cmp-mainboard', to: 'cmp-hub', kind: 'USB', authority: 'partial', unresolved: ['downstream power budget'] },
];

export const deck001Evidence: WorkbenchEvidence[] = [
  { id: 'ev-board-observed', title: 'Board identity inspection', entityId: 'cmp-mainboard', state: 'partial', method: 'operator inspection', note: 'Candidate donor is observed, but exact revision and DC input contract are not yet closed.' },
  { id: 'ev-nvme-native', title: 'Native storage path', entityId: 'cmp-nvme', state: 'verified', method: 'documented interface', note: 'Known-good NVMe uses the donor board native M.2 path.' },
  { id: 'ev-display-needed', title: 'Display identity required', entityId: 'cmp-display', state: 'unknown', method: 'datasheet / bounded bench', note: 'Do not infer a raw panel pinout from similar models.' },
  { id: 'ev-power-needed', title: 'Power envelope required', entityId: 'cmp-pd', state: 'blocked', method: 'instrumented bench + analysis', note: 'Battery/PD energization is withheld until source/load contracts close.' },
  { id: 'ev-thermal-needed', title: 'Sustained thermal run', entityId: 'ss-thermal', state: 'blocked', method: 'instrumented workload test', note: 'Sustained-operation claim requires compute and battery-adjacent temperature evidence.' },
];

export const deck001Constraints: WorkbenchConstraint[] = [
  { id: 'con-power', title: 'No unverified battery power-on', entityId: 'ss-power', severity: 'blocking', state: 'open', note: 'Voltage, polarity, protection, peak current and connector limits must close first.' },
  { id: 'con-display', title: 'No inferred donor display pinout', entityId: 'cmp-display', severity: 'blocking', state: 'open', note: 'Exact panel/controller evidence is required before connection.' },
  { id: 'con-clearance', title: 'Measured enclosure clearances required', entityId: 'cmp-enclosure', severity: 'blocking', state: 'open', note: 'Component envelopes, port keep-outs and operating-state clearances remain provisional.' },
  { id: 'con-native-highspeed', title: 'Prefer native high-speed paths', entityId: 'cmp-mainboard', severity: 'warning', state: 'satisfied', note: 'The candidate architecture avoids novel eDP/PCIe/USB3 PCB routing.' },
];

export const deck001Verifications: WorkbenchVerification[] = [
  { id: 'ver-display', title: 'Identify and characterize donor display', entityId: 'cmp-display', state: 'planned', method: 'inspection + datasheet / bounded bench' },
  { id: 'ver-power', title: 'Verify whole-system power envelope', entityId: 'ss-power', state: 'blocked', method: 'analysis + instrumented bench' },
  { id: 'ver-input', title: 'Enumerate and test input path', entityId: 'cmp-keyboard', state: 'planned', method: 'USB enumeration + key functional test' },
  { id: 'ver-thermal', title: 'Sustained workload thermal soak', entityId: 'ss-thermal', state: 'blocked', method: 'instrumented workload test' },
  { id: 'ver-storage', title: 'NVMe enumeration and workload test', entityId: 'cmp-nvme', state: 'passed', method: 'functional test' },
];

export const deck001History: WorkbenchHistoryEvent[] = [
  { id: 'hist-1', at: 'R0', entityId: 'deck-001', title: 'Architecture created', note: 'System decomposed into compute, display, input, power, storage, I/O, thermal and enclosure domains.' },
  { id: 'hist-2', at: 'R0', entityId: 'cmp-battery', title: 'Ambiguous donor battery rejected', note: 'Reuse value did not outrank missing condition/protection evidence.' },
  { id: 'hist-3', at: 'R0', entityId: 'cmp-display', title: 'Display reuse held', note: 'Raw panel path stays unresolved; validated portable-monitor controller path is preferred.' },
  { id: 'hist-4', at: 'R0', entityId: 'cmp-mainboard', title: 'Native high-speed policy selected', note: 'Retain manufacturer-validated display, storage and USB paths wherever possible.' },
];

export const deck001EntityMap = new Map(deck001Entities.map((entity) => [entity.id, entity]));

export function authorityLabel(state: AuthorityState) {
  return state.replace('_', ' ').toUpperCase();
}
