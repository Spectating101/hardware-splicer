'use client';

export type EngineeringVisualView =
  | 'system'
  | 'kicad'
  | 'proposal'
  | 'mechanical'
  | 'gerber'
  | 'assembly';

export type EngineeringVisualAdapter = {
  id: string;
  view: EngineeringVisualView;
  label: string;
  project: string;
  license: string;
  status: 'active' | 'adapter-ready' | 'planned';
  readOnly: boolean;
  externalNetworkRequired: boolean;
  ownsProjectTruth: false;
  authorityEffect: 'none';
  purpose: string;
  requiredArtifactTypes: string[];
  limitations: string[];
};

export const engineeringVisualAdapters: EngineeringVisualAdapter[] = [
  {
    id: 'react-flow-system-v1',
    view: 'system',
    label: 'System',
    project: 'React Flow',
    license: 'MIT',
    status: 'active',
    readOnly: true,
    externalNetworkRequired: false,
    ownsProjectTruth: false,
    authorityEffect: 'none',
    purpose: 'Canonical cross-domain topology, evidence, blocker, proposal, and authority overlays.',
    requiredArtifactTypes: ['hardware_splicer.system_graph.v1'],
    limitations: [
      'Not an ECAD engine.',
      'Does not validate electrical or manufacturing rules.',
    ],
  },
  {
    id: 'kicanvas-native-v1',
    view: 'kicad',
    label: 'KiCad',
    project: 'KiCanvas',
    license: 'MIT',
    status: 'adapter-ready',
    readOnly: true,
    externalNetworkRequired: false,
    ownsProjectTruth: false,
    authorityEffect: 'none',
    purpose: 'Faithful read-only display of native KiCad schematic and PCB artifacts.',
    requiredArtifactTypes: ['kicad_schematic', 'kicad_pcb', 'kicad_project'],
    limitations: [
      'KiCanvas embedding remains alpha.',
      'Editing and visual comparison are explicit non-goals upstream.',
      'Bundle must be pinned and self-hosted before production enablement.',
    ],
  },
  {
    id: 'tscircuit-proposal-v1',
    view: 'proposal',
    label: 'Proposal',
    project: 'tscircuit / Circuit JSON',
    license: 'MIT',
    status: 'adapter-ready',
    readOnly: false,
    externalNetworkRequired: false,
    ownsProjectTruth: false,
    authorityEffect: 'none',
    purpose: 'Interactive schematic, PCB, and visual-diff sandbox for proposed successor designs.',
    requiredArtifactTypes: ['circuit_json'],
    limitations: [
      'Circuit JSON is a proposal representation, not the sole project source of truth.',
      'Conversion to KiCad requires an accepted deterministic action and native KiCad validation.',
    ],
  },
  {
    id: 'react-three-mechanical-v1',
    view: 'mechanical',
    label: '3D',
    project: 'React Three Fiber / Three.js',
    license: 'MIT',
    status: 'active',
    readOnly: true,
    externalNetworkRequired: false,
    ownsProjectTruth: false,
    authorityEffect: 'none',
    purpose: 'Mechanical context, cross-view selection, collision and clearance overlays.',
    requiredArtifactTypes: ['gltf', 'glb', 'stl', 'obj', 'step_mesh'],
    limitations: [
      'STEP and OpenCascade import must remain behind a reviewed conversion boundary.',
      'Rendered geometry is not dimensional verification by itself.',
    ],
  },
  {
    id: 'tracespace-gerber-v1',
    view: 'gerber',
    label: 'Gerber',
    project: 'tracespace',
    license: 'MIT',
    status: 'planned',
    readOnly: true,
    externalNetworkRequired: false,
    ownsProjectTruth: false,
    authorityEffect: 'none',
    purpose: 'Render exported Gerber and drill artifacts as manufacturing evidence.',
    requiredArtifactTypes: ['gerber', 'excellon'],
    limitations: [
      'Manufacturing output must first be produced by a deterministic accepted export action.',
      'A visual stack does not replace fabrication-rule verification.',
    ],
  },
  {
    id: 'interactive-html-bom-v1',
    view: 'assembly',
    label: 'Assembly',
    project: 'InteractiveHtmlBom',
    license: 'MIT',
    status: 'planned',
    readOnly: true,
    externalNetworkRequired: false,
    ownsProjectTruth: false,
    authorityEffect: 'none',
    purpose: 'Assembly, BOM, board-location, and troubleshooting artifact view.',
    requiredArtifactTypes: ['interactive_html_bom'],
    limitations: [
      'Generated HTML remains an artifact, not canonical state.',
      'Embedding must be sandboxed and script policy reviewed.',
    ],
  },
];

export function visualAdapter(view: EngineeringVisualView) {
  return engineeringVisualAdapters.find((adapter) => adapter.view === view);
}
