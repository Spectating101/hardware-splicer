export const referenceComponentTypes = ['esp32_module', 'resistor_0603', 'capacitor_0603', 'power_trace', 'ground_return', 'fabrication_rule'];

export const referenceEducationalContent = [
  {
    title: 'ESP32 module placement and antenna keepout',
    difficulty: 'intermediate',
    component_type: 'esp32_module',
    estimated_time: '12 min',
  },
  {
    title: 'Resistor package power derating',
    difficulty: 'intermediate',
    component_type: 'resistor_0603',
    estimated_time: '8 min',
  },
  {
    title: 'Bulk decoupling near 3V3 rails',
    difficulty: 'beginner',
    component_type: 'capacitor_0603',
    estimated_time: '6 min',
  },
  {
    title: 'Trace width and voltage-drop review',
    difficulty: 'intermediate',
    component_type: 'power_trace',
    estimated_time: '10 min',
  },
  {
    title: 'Ground return continuity check',
    difficulty: 'beginner',
    component_type: 'ground_return',
    estimated_time: '7 min',
  },
  {
    title: 'Fabrication readiness and evidence packaging',
    difficulty: 'advanced',
    component_type: 'fabrication_rule',
    estimated_time: '14 min',
  },
];

export const referenceRepairGuides = [
  {
    component_type: 'resistor_0603',
    issue: 'R1 exceeds 0603 1/4W derating target under the demo load model.',
    difficulty: 'intermediate',
    success_rate: 0.82,
  },
  {
    component_type: 'power_trace',
    issue: 'VCC_MAIN needs a wider trace or alternate route before fabrication handoff.',
    difficulty: 'advanced',
    success_rate: 0.76,
  },
  {
    component_type: 'capacitor_0603',
    issue: 'C1 should remain near the ESP32 3V3 input during layout edits.',
    difficulty: 'beginner',
    success_rate: 0.9,
  },
  {
    component_type: 'fabrication_rule',
    issue: 'Generate an evidence bundle before treating the demo board as manufacturing ready.',
    difficulty: 'intermediate',
    success_rate: 0.88,
  },
];

export const referenceProjects = [
  {
    id: 'trace_width_remediation',
    name: 'Resolve VCC_MAIN voltage drop',
    difficulty: 'advanced',
    category: 'remediation',
    estimated_cost: 0,
    score: 0.94,
    rationale: 'Directly addresses the highest electrical warning in the reference board.',
    next_action: 'Open CAD and widen the +3V3 route before fabrication review.',
  },
  {
    id: 'resistor_power_upgrade',
    name: 'Upgrade R1 power rating',
    difficulty: 'intermediate',
    category: 'repair',
    estimated_cost: 1,
    score: 0.87,
    rationale: 'Reduces the thermal risk exposed by the validation issue on R1.',
    next_action: 'Select R1 in CAD and swap to a footprint/value that satisfies the load model.',
  },
  {
    id: 'evidence_package',
    name: 'Prepare validation evidence bundle',
    difficulty: 'beginner',
    category: 'review',
    estimated_cost: 0,
    score: 0.83,
    rationale: 'Turns the reference-board analysis into material a reviewer can inspect.',
    next_action: 'Capture issues, geometry counts, and next-step decisions for professor review.',
  },
  {
    id: 'fabrication_handoff',
    name: 'Stage fabrication handoff',
    difficulty: 'intermediate',
    category: 'fabrication',
    estimated_cost: 5,
    score: 0.78,
    rationale: 'Useful only after the validation warnings have an explicit disposition.',
    next_action: 'Move into CAD fabrication mode once the issue list is resolved or accepted.',
  },
];
