export type PreflightMode = 'greenfield' | 'modify' | 'repair' | 'evolve';
export type AuthorityCeiling = 'declared' | 'observed' | 'measured';

export type PartRow = { id: string; partId: string; name: string; type: string; quantity: number };
export type SourceRow = { id: string; sourceId: string; sourceType: string; uri: string; revision: string; authority: AuthorityCeiling; claim: string };
export type ArtifactRow = { id: string; artifactId: string; kind: string; revision: string; contentHash: string };
export type AttachmentRow = { id: string; sourceId: string; fileName: string; artifactKind: string; sizeBytes: number; lastModified: number; content?: string };

export type PreflightState = {
  projectName: string; goal: string; mode: PreflightMode; candidateRevision: string; baselineRevision: string;
  robotGenre: string; runtimeMinutes: string; maximumWidthMm: string; payloadMassKg: string; maximumSpeedMps: string;
  batteryVoltageV: string; batteryCapacityAh: string; batteryUsableFraction: string; continuousPowerW: string;
  supplyCurrentLimitA: string; peakCurrentA: string; emergencyStopRequired: boolean; currentLimitedFirstMotion: boolean;
  autoInventory: boolean; parts: PartRow[]; sources: SourceRow[]; artifacts: ArtifactRow[]; attachments: AttachmentRow[]; advancedJson: string;
};

export type PlanSummary = {
  projectId: string; status: string; phase: string; sources: number; conflicts: number; components: number; interfaces: number;
  blockers: number; advisories: number; closureStatus: string; closureBlockers: number; executionChecks: number; guideSteps: number;
  nextActionTitle: string; nextActionInstruction: string; authority: Record<string, boolean>;
};

let sequence = 0;
function id(prefix: string) { sequence += 1; return `${prefix}-${sequence}`; }
export function blankPart(): PartRow { return { id: id('part'), partId: '', name: '', type: '', quantity: 1 }; }
export function blankSource(): SourceRow { return { id: id('source'), sourceId: '', sourceType: 'repository', uri: '', revision: '', authority: 'declared', claim: '' }; }
export function blankArtifact(): ArtifactRow { return { id: id('artifact'), artifactId: '', kind: 'other', revision: '', contentHash: '' }; }

const advancedStarter = { electrical_pins: [], firmware_pin_map: [], connectors: [], harnesses: [], fasteners: [], assembly_steps: [], cad_models: [], mounts: [] };

export function emptyPreflight(): PreflightState {
  return {
    projectName: '', goal: '', mode: 'greenfield', candidateRevision: 'candidate-r1', baselineRevision: '', robotGenre: 'rover',
    runtimeMinutes: '', maximumWidthMm: '', payloadMassKg: '', maximumSpeedMps: '', batteryVoltageV: '', batteryCapacityAh: '',
    batteryUsableFraction: '0.8', continuousPowerW: '', supplyCurrentLimitA: '', peakCurrentA: '', emergencyStopRequired: true,
    currentLimitedFirstMotion: true, autoInventory: true, parts: [blankPart()], sources: [blankSource()], artifacts: [blankArtifact()],
    attachments: [], advancedJson: JSON.stringify(advancedStarter, null, 2),
  };
}

export function roverDemo(): PreflightState {
  return {
    ...emptyPreflight(),
    projectName: 'reference-rich-indoor-inspection-rover',
    goal: 'Prepare a repairable differential-drive indoor inspection rover that fits through 700 mm doors, carries a 500 g sensor payload, runs for at least 90 minutes, maps with 2D lidar, and supports ROS 2 navigation.',
    candidateRevision: 'demo-r1', runtimeMinutes: '90', maximumWidthMm: '500', payloadMassKg: '0.5', maximumSpeedMps: '0.4',
    batteryVoltageV: '12', batteryCapacityAh: '8', continuousPowerW: '45', supplyCurrentLimitA: '20', peakCurrentA: '12',
    parts: [
      ['pi5', 'Raspberry Pi 5', 'computer', 1], ['mcu', 'ESP32-S3 controller', 'microcontroller', 1],
      ['wheel-motor', '12 V geared motor with encoder', 'dc_motor', 2], ['motor-driver', 'Dual-channel motor driver', 'motor_driver', 1],
      ['lidar', '2D lidar', 'lidar', 1], ['imu', 'BNO085 IMU', 'imu', 1],
      ['battery', '12 V 8 Ah protected battery', 'power_source', 1], ['chassis', 'Chassis assembly', 'mechanical_structure', 1],
    ].map(([partId, name, type, quantity]) => ({ id: id('part'), partId: String(partId), name: String(name), type: String(type), quantity: Number(quantity) })),
    sources: [
      ['linorobot2-repo', 'repository', 'https://github.com/linorobot/linorobot2', 'pin-before-release', 'declared', 'Reference ROS 2 rover architecture.'],
      ['linorobot2-hardware', 'repository', 'https://github.com/linorobot/linorobot2_hardware', 'pin-before-release', 'declared', 'Reference firmware and motor-control architecture.'],
      ['turtlebot3-manual', 'manual', 'https://emanual.robotis.com/docs/en/platform/turtlebot3/overview/', 'retrieval-demo', 'declared', 'Comparative assembly and bring-up reference.'],
      ['assembly-video', 'video', 'https://www.youtube.com/results?search_query=linorobot2+assembly', 'unresolved-video-selection', 'observed', 'Discovery source only; select an exact video and timestamp.'],
    ].map(([sourceId, sourceType, uri, revision, authority, claim]) => ({ id: id('source'), sourceId, sourceType, uri, revision, authority: authority as AuthorityCeiling, claim })),
    artifacts: [
      { id: id('artifact'), artifactId: 'chassis-step', kind: 'step', revision: 'demo-r1', contentHash: 'sha256:replace-with-real-step-hash' },
      { id: id('artifact'), artifactId: 'firmware-build', kind: 'firmware', revision: 'demo-r1', contentHash: 'sha256:replace-with-real-firmware-hash' },
    ],
    advancedJson: JSON.stringify({ ...advancedStarter,
      electrical_pins: [{ component_id: 'mcu', pin: 'gpio12', net: 'left_motor_pwm' }, { component_id: 'mcu', pin: 'gpio13', net: 'right_motor_pwm' }],
      firmware_pin_map: [{ component_id: 'mcu', physical_pin: 'gpio12', net: 'left_motor_pwm' }, { component_id: 'mcu', physical_pin: 'gpio13', net: 'right_motor_pwm' }],
    }, null, 2),
  };
}

function numeric(value: string) { const parsed = Number(value); return value.trim() && Number.isFinite(parsed) ? parsed : undefined; }
function object(value: unknown): Record<string, unknown> { return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
function rows(value: unknown): Record<string, unknown>[] { return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) as Record<string, unknown>[] : []; }

export function validatePreflight(state: PreflightState) {
  const errors: string[] = [];
  if (!state.projectName.trim()) errors.push('Project name is required.');
  if (!state.goal.trim()) errors.push('Describe the required machine outcome.');
  if (!state.candidateRevision.trim()) errors.push('Candidate revision is required.');
  if (!state.parts.some((row) => row.name.trim() && row.type.trim())) errors.push('Add at least one component.');
  if (state.sources.some((row) => row.uri.trim() && !row.sourceId.trim())) errors.push('Every source URL needs a source ID.');
  const modelCount = state.attachments.filter((row) => ['urdf', 'sdf', 'mjcf'].includes(row.artifactKind)).length;
  if (modelCount > 1) errors.push('Select one structured robot model; multiple models are never mixed automatically.');
  try { const advanced = JSON.parse(state.advancedJson || '{}'); if (!advanced || typeof advanced !== 'object' || Array.isArray(advanced)) errors.push('Advanced package JSON must be an object.'); }
  catch { errors.push('Advanced package JSON is invalid.'); }
  return errors;
}

export function compilePreflightRequest(state: PreflightState) {
  const errors = validatePreflight(state); if (errors.length) throw new Error(errors.join(' '));
  const advanced = JSON.parse(state.advancedJson || '{}') as Record<string, unknown>;
  const parts = state.parts.filter((row) => row.name.trim() && row.type.trim()).map((row) => ({
    part_id: row.partId.trim() || row.name.toLowerCase().replace(/[^a-z0-9]+/g, '-'), name: row.name.trim(), type: row.type.trim(), quantity: Math.max(1, Math.round(row.quantity || 1)),
  }));
  const inventory = parts.map((row) => ({ part_id: row.part_id, quantity: row.quantity }));
  const model = state.attachments.find((row) => ['urdf', 'sdf', 'mjcf'].includes(row.artifactKind));
  const intake: Record<string, unknown> = {
    ...advanced, project_name: state.projectName.trim(), goal: state.goal.trim(), mode: state.mode, candidate_revision: state.candidateRevision.trim(),
    ...(state.baselineRevision.trim() ? { baseline_revision: state.baselineRevision.trim() } : {}),
    ...(model ? { selected_robot_model_source_id: model.sourceId } : {}), available_parts: parts,
    constraints: { ...object(advanced.constraints), robot_genre: state.robotGenre, runtime_min: numeric(state.runtimeMinutes), maximum_width_mm: numeric(state.maximumWidthMm),
      payload_mass_kg: numeric(state.payloadMassKg), maximum_speed_mps: numeric(state.maximumSpeedMps), battery_voltage_v: numeric(state.batteryVoltageV),
      battery_capacity_ah: numeric(state.batteryCapacityAh), battery_usable_fraction: numeric(state.batteryUsableFraction), continuous_power_w: numeric(state.continuousPowerW),
      supply_current_limit_a: numeric(state.supplyCurrentLimitA), peak_current_a: numeric(state.peakCurrentA), emergency_stop_required: state.emergencyStopRequired,
      first_motion_current_limited: state.currentLimitedFirstMotion },
    ...(state.autoInventory ? { bom: rows(advanced.bom).length ? advanced.bom : inventory, physical_instances: rows(advanced.physical_instances).length ? advanced.physical_instances : inventory } : {}),
    fabrication_artifacts: state.artifacts.filter((row) => row.artifactId.trim()).map((row) => ({ artifact_id: row.artifactId.trim(), artifact_kind: row.kind,
      revision: row.revision.trim() || state.candidateRevision.trim(), content_hash: row.contentHash.trim() || undefined })),
  };
  const sources = state.sources.filter((row) => row.sourceId.trim() || row.uri.trim()).map((row) => ({ source_id: row.sourceId.trim(), source_type: row.sourceType,
    uri: row.uri.trim() || undefined, revision: row.revision.trim() || undefined, authority_ceiling: row.authority, claims: row.claim.trim() ? [row.claim.trim()] : [] }));
  const attachments = state.attachments.map((row) => ({ source_id: row.sourceId, artifact_kind: row.artifactKind,
    source_type: ['urdf', 'sdf', 'mjcf'].includes(row.artifactKind) ? row.artifactKind : 'project_snapshot', uri: `local-upload:${row.fileName}`,
    revision: `mtime-${row.lastModified}`, ...(row.content ? { content: row.content } : {}), claims: row.content ? [] : [`Attached ${row.fileName} (${row.sizeBytes} bytes); registered without binary parsing.`],
    metadata: { file_name: row.fileName, size_bytes: row.sizeBytes, local_upload: true } }));
  return { intake, engineering_sources: [...sources, ...attachments], declared_conflicts: [], skip_vision: true };
}

export function summarizePlan(plan: Record<string, unknown>): PlanSummary {
  const project = object(plan.machine_project), graph = object(plan.engineering_source_graph), status = object(plan.engineering_status), readiness = object(plan.engineering_readiness);
  const closure = object(plan.manufacturing_closure), execution = object(plan.engineering_execution_plan), guide = object(plan.operator_guide), nextAction = rows(status.next_actions)[0] || {};
  return { projectId: String(project.project_id || status.project_id || 'engineering-project'), status: String(status.overall_status || readiness.status || 'candidate'),
    phase: String(status.current_phase || 'requirements'), sources: rows(graph.sources).length, conflicts: rows(graph.conflicts).length, components: rows(project.components).length,
    interfaces: rows(project.interfaces).length, blockers: rows(status.blockers).length, advisories: rows(status.advisories).length, closureStatus: String(closure.status || 'unresolved'),
    closureBlockers: rows(closure.checks).filter((row) => row.blocking === true && row.status !== 'pass').length, executionChecks: rows(execution.checks).length,
    guideSteps: rows(guide.steps).length, nextActionTitle: String(nextAction.title || 'Inspect the generated plan'),
    nextActionInstruction: String(nextAction.instruction || 'Resolve the highest-ranked engineering blocker.'), authority: {
      fabrication: readiness.fabrication_authorized === true, flash: readiness.flash_authorized === true, power: readiness.power_on_authorized === true,
      motion: readiness.motion_authorized === true, release: readiness.release_authorized === true },
  };
}
