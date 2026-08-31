'use client';

import { Canvas } from '@react-three/fiber';
import { CameraControls, Grid, Html, Line } from '@react-three/drei';
import { Crosshair, Eye, EyeOff } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';
import {
  deck001Entities,
  deck001EntityMap,
  deck001Interfaces,
  type AuthorityState,
  type ResourceSource,
  type WorkbenchEntity,
} from '@/lib/workbench-demo';
import {
  buildCandidateMachineProjection,
  type CandidateMachineProjection,
  type MachinePartProjection,
} from '@/lib/workbench-machine-projection';
import {
  useMachineWorkbenchStore,
  type WorkbenchCameraPreset,
  type WorkbenchLens,
} from '@/lib/machine-workbench-store';
import { DeclaredInterfaceAccessOverlays } from '@/components/workbench/declared-interface-access-overlay';

const AUTHORITY_COLORS: Record<AuthorityState, string> = {
  verified: '#22c55e',
  partial: '#38bdf8',
  unknown: '#f59e0b',
  blocked: '#ef4444',
  proposed: '#a78bfa',
};

const SOURCE_COLORS: Record<ResourceSource, string> = {
  output: '#64748b',
  donor: '#22d3ee',
  new: '#a78bfa',
  generated: '#f59e0b',
  external: '#94a3b8',
};

const PROJECTION_COLORS = {
  retained: '#22d3ee',
  substituted: '#a78bfa',
  held: '#f59e0b',
  gap: '#ef4444',
  implicit: '#64748b',
  suppressed: '#334155',
};

const PHYSICAL_COLORS: Record<string, string> = {
  'cmp-mainboard': '#14532d',
  'cmp-display': '#243244',
  'cmp-keyboard': '#263344',
  'cmp-battery': '#5b21b6',
  'cmp-pd': '#9f1239',
  'cmp-nvme': '#15803d',
  'cmp-hub': '#0f766e',
  'cmp-cooling': '#475569',
  'cmp-enclosure': '#334155',
};

const CAMERA_PRESETS: Array<{ id: WorkbenchCameraPreset; label: string; aria: string }> = [
  { id: 'iso', label: 'ISO', aria: 'Isometric view' },
  { id: 'top', label: 'TOP', aria: 'Top view' },
  { id: 'front', label: 'FRONT', aria: 'Front view' },
  { id: 'right', label: 'SIDE', aria: 'Right side view' },
];

function semanticColor(entity: WorkbenchEntity, lens: WorkbenchLens) {
  if (lens === 'provenance') return SOURCE_COLORS[entity.source];
  if (lens === 'constraints') {
    if (entity.authority === 'blocked') return '#ef4444';
    if (entity.unresolved.length > 2) return '#f59e0b';
    return '#475569';
  }
  if (lens === 'interfaces') return '#64748b';
  return AUTHORITY_COLORS[entity.authority];
}

function scenePosition(entity: WorkbenchEntity): [number, number, number] {
  if (!entity.spatial) return [0, 0, 0];
  if (entity.id === 'cmp-display') return [0, 3.35, -3.05];
  if (entity.id === 'cmp-keyboard') return [0.55, 0.72, 2.25];
  return entity.spatial.position;
}

function projectedPosition(entity: WorkbenchEntity, projection?: MachinePartProjection): [number, number, number] {
  const [x, y, z] = scenePosition(entity);
  const offset = projection?.positionOffset ?? [0, 0, 0];
  return [x + offset[0], y + offset[1], z + offset[2]];
}

function explodedPosition(
  entity: WorkbenchEntity,
  exploded: boolean,
  projection?: MachinePartProjection,
): [number, number, number] {
  const base = projectedPosition(entity, projection);
  if (!entity.spatial || !exploded || entity.id === 'cmp-enclosure') return base;
  const [x, y, z] = base;
  const magnitude = Math.max(Math.hypot(x, z), 1);
  const spread = 1.15;
  return [x + (x / magnitude) * spread, y + 0.38, z + (z / magnitude) * spread];
}

function candidateProjectionFromStore() {
  const state = useMachineWorkbenchStore.getState();
  return buildCandidateMachineProjection(
    state.activeCandidateId,
    state.plannerSource,
    state.plannerProjections[state.activeCandidateId],
  );
}

function spatialPartsForSelection(selectedEntityId: string, projection?: CandidateMachineProjection) {
  const selected = deck001EntityMap.get(selectedEntityId);
  const allParts = deck001Entities.filter((entity) => {
    if (entity.kind !== 'component' || !entity.spatial) return false;
    return projection ? projection.parts[entity.id]?.visible !== false : true;
  });
  if (!selected || selected.kind === 'machine') return allParts;
  if (selected.spatial) return [selected];
  const childParts = selected.children
    .map((id) => deck001EntityMap.get(id))
    .filter((entity): entity is WorkbenchEntity => Boolean(entity?.spatial))
    .filter((entity) => projection ? projection.parts[entity.id]?.visible !== false : true);
  return childParts.length ? childParts : allParts;
}

function selectionScope(selectedEntityId: string) {
  const selected = deck001EntityMap.get(selectedEntityId);
  if (!selected || selected.kind === 'machine') return new Set<string>();
  if (selected.spatial) return new Set([selected.id]);
  return new Set(selected.children);
}

function CameraDirector({ controlsRef }: { controlsRef: React.RefObject<CameraControls | null> }) {
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const cameraPreset = useMachineWorkbenchStore((state) => state.cameraPreset);
  const frameRequest = useMachineWorkbenchStore((state) => state.frameRequest);
  const exploded = useMachineWorkbenchStore((state) => state.exploded);
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const plannerSource = useMachineWorkbenchStore((state) => state.plannerSource);
  const plannerProjection = useMachineWorkbenchStore((state) => state.plannerProjections[state.activeCandidateId]);
  const initialized = useRef(false);
  const candidateProjection = phase === 'construct'
    ? buildCandidateMachineProjection(activeCandidateId, plannerSource, plannerProjection)
    : undefined;
  const targets = spatialPartsForSelection(selectedEntityId, candidateProjection);

  useEffect(() => {
    const controls = controlsRef.current;
    if (!controls || targets.length === 0) return;

    let minX = Infinity;
    let minY = Infinity;
    let minZ = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    let maxZ = -Infinity;

    for (const entity of targets) {
      if (!entity.spatial) continue;
      const partProjection = candidateProjection?.parts[entity.id];
      const [x, y, z] = explodedPosition(entity, exploded, partProjection);
      const scale = partProjection?.sizeScale ?? [1, 1, 1];
      const [width, height, depth] = entity.spatial.size.map((value, index) => value * scale[index]) as [number, number, number];
      minX = Math.min(minX, x - width / 2);
      maxX = Math.max(maxX, x + width / 2);
      minY = Math.min(minY, y - height / 2);
      maxY = Math.max(maxY, y + height / 2);
      minZ = Math.min(minZ, z - depth / 2);
      maxZ = Math.max(maxZ, z + depth / 2);
    }

    if (![minX, minY, minZ, maxX, maxY, maxZ].every(Number.isFinite)) return;

    const center: [number, number, number] = [
      (minX + maxX) / 2,
      (minY + maxY) / 2,
      (minZ + maxZ) / 2,
    ];
    const extent = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 1);
    const distance = Math.max(6.5, extent * 1.75);
    const directions: Record<WorkbenchCameraPreset, [number, number, number]> = {
      iso: [0.82, 0.62, 1],
      top: [0.001, 1, 0.001],
      front: [0, 0.18, 1],
      right: [1, 0.18, 0],
    };
    const [dx, dy, dz] = directions[cameraPreset];
    const length = Math.hypot(dx, dy, dz) || 1;
    const position: [number, number, number] = [
      center[0] + (dx / length) * distance,
      center[1] + (dy / length) * distance,
      center[2] + (dz / length) * distance,
    ];

    controls.setLookAt(position[0], position[1], position[2], center[0], center[1], center[2], initialized.current);
    initialized.current = true;
    // Explicit frame/camera requests only; candidate changes request a frame from the tray.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraPreset, frameRequest, exploded, activeCandidateId, plannerSource, controlsRef]);

  return null;
}

function StatusShell({
  entity,
  projection,
  width,
  height,
  depth,
  selected,
}: {
  entity: WorkbenchEntity;
  projection?: MachinePartProjection;
  width: number;
  height: number;
  depth: number;
  selected: boolean;
}) {
  const activeLens = useMachineWorkbenchStore((state) => state.activeLens);
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const selectedEntity = deck001EntityMap.get(selectedEntityId);
  const focusedSelection = Boolean(selectedEntity && selectedEntity.kind !== 'machine');
  const color = phase === 'construct' && projection
    ? PROJECTION_COLORS[projection.disposition]
    : semanticColor(entity, activeLens);
  const relevant = activeLens !== 'interfaces' || selected;
  const alertProjection = phase === 'construct' && projection && ['held', 'gap'].includes(projection.disposition);
  const opacity = selected ? 0.96 : alertProjection && focusedSelection ? 0.16 : relevant ? 0.4 : 0.13;

  return (
    <mesh scale={[1.025, 1.08, 1.025]}>
      <boxGeometry args={[width, height, depth]} />
      <meshBasicMaterial color={color} transparent opacity={opacity} wireframe depthWrite={false} />
    </mesh>
  );
}

function MainboardBody({ width, height, depth, documented, opacity }: { width: number; height: number; depth: number; documented: boolean; opacity: number }) {
  return (
    <>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color={documented ? '#1e3a5f' : PHYSICAL_COLORS['cmp-mainboard']} roughness={0.58} metalness={0.12} transparent opacity={opacity} />
      </mesh>
      <mesh position={[documented ? 0 : 0.35, height / 2 + 0.13, -0.25]} castShadow>
        <boxGeometry args={[documented ? 0.86 : 1.1, 0.22, documented ? 0.86 : 1.05]} />
        <meshStandardMaterial color="#111827" roughness={0.32} metalness={0.45} transparent opacity={opacity} />
      </mesh>
      {documented ? (
        <>
          <mesh position={[-width / 2 + 0.16, height / 2 + 0.08, 0]}><boxGeometry args={[0.14, 0.12, depth - 0.28]} /><meshStandardMaterial color="#64748b" metalness={0.55} roughness={0.3} /></mesh>
          <mesh position={[width / 2 - 0.16, height / 2 + 0.08, 0]}><boxGeometry args={[0.14, 0.12, depth - 0.28]} /><meshStandardMaterial color="#64748b" metalness={0.55} roughness={0.3} /></mesh>
        </>
      ) : (
        <>
          <mesh position={[-1.15, height / 2 + 0.09, 0.7]} castShadow><boxGeometry args={[1.45, 0.14, 0.34]} /><meshStandardMaterial color="#1f2937" roughness={0.42} metalness={0.25} /></mesh>
          <mesh position={[1.15, height / 2 + 0.08, 0.8]} castShadow><boxGeometry args={[0.9, 0.12, 0.38]} /><meshStandardMaterial color="#334155" roughness={0.45} metalness={0.18} /></mesh>
        </>
      )}
    </>
  );
}

function DisplayBody({ width, height, depth, variant, opacity }: { width: number; height: number; depth: number; variant: MachinePartProjection['variant']; opacity: number }) {
  const raw = variant === 'raw-display';
  const documented = variant === 'documented-display';
  return (
    <>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color={raw ? '#334155' : PHYSICAL_COLORS['cmp-display']} roughness={raw ? 0.46 : 0.36} metalness={raw ? 0.08 : 0.28} transparent opacity={opacity} />
      </mesh>
      <mesh position={[0, 0, depth / 2 + 0.045]}>
        <boxGeometry args={[Math.max(width - 0.55, 0.4), Math.max(height - 0.52, 0.4), 0.06]} />
        <meshStandardMaterial color="#071827" emissive={raw ? '#7c2d12' : '#0e7490'} emissiveIntensity={raw ? 0.08 : 0.2} roughness={0.2} transparent opacity={opacity} />
      </mesh>
      {!raw ? <mesh position={[0, -height / 2 - 0.12, 0.08]} castShadow><boxGeometry args={[2.1, 0.18, 0.42]} /><meshStandardMaterial color="#334155" roughness={0.42} metalness={0.3} /></mesh> : null}
      {documented ? <mesh position={[0, 0, -depth / 2 - 0.12]}><boxGeometry args={[2.6, 1.25, 0.22]} /><meshStandardMaterial color="#312e81" roughness={0.4} metalness={0.16} /></mesh> : null}
    </>
  );
}

function KeyboardBody({ width, height, depth, opacity }: { width: number; height: number; depth: number; opacity: number }) {
  const keys = Array.from({ length: 40 }, (_, index) => ({ row: Math.floor(index / 10), col: index % 10 }));
  return (
    <>
      <mesh castShadow receiveShadow><boxGeometry args={[width, height, depth]} /><meshStandardMaterial color={PHYSICAL_COLORS['cmp-keyboard']} roughness={0.58} metalness={0.14} transparent opacity={opacity} /></mesh>
      {keys.map(({ row, col }) => (
        <mesh key={`${row}-${col}`} position={[-3.3 + col * 0.72, height / 2 + 0.075, -0.78 + row * 0.52]} castShadow>
          <boxGeometry args={[0.56, 0.09, 0.39]} /><meshStandardMaterial color="#0f172a" roughness={0.52} metalness={0.18} transparent opacity={opacity} />
        </mesh>
      ))}
      <mesh position={[2.9, height / 2 + 0.06, 0.78]}><boxGeometry args={[1.15, 0.06, 0.62]} /><meshStandardMaterial color="#172033" roughness={0.45} metalness={0.15} transparent opacity={opacity} /></mesh>
    </>
  );
}

function BatteryBody({ width, height, depth, opacity }: { width: number; height: number; depth: number; opacity: number }) {
  return (
    <>
      <mesh castShadow receiveShadow><boxGeometry args={[width, height, depth]} /><meshStandardMaterial color={PHYSICAL_COLORS['cmp-battery']} roughness={0.48} metalness={0.12} transparent opacity={opacity} /></mesh>
      {[-0.9, 0, 0.9].map((x) => <mesh key={x} position={[x, height / 2 + 0.025, 0]}><boxGeometry args={[0.04, 0.035, depth - 0.22]} /><meshBasicMaterial color="#c4b5fd" transparent opacity={0.48 * opacity} /></mesh>)}
    </>
  );
}

function CoolingBody({ opacity }: { opacity: number }) {
  return (
    <>
      <mesh castShadow><cylinderGeometry args={[0.72, 0.72, 0.22, 32]} /><meshStandardMaterial color={PHYSICAL_COLORS['cmp-cooling']} roughness={0.42} metalness={0.32} transparent opacity={opacity} /></mesh>
      <mesh position={[0, 0.13, 0]}><cylinderGeometry args={[0.22, 0.22, 0.08, 24]} /><meshStandardMaterial color="#111827" roughness={0.32} metalness={0.38} transparent opacity={opacity} /></mesh>
    </>
  );
}

function EnclosureBody({ width, depth, opacity }: { width: number; depth: number; opacity: number }) {
  const xray = useMachineWorkbenchStore((state) => state.xray);
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const shellOpacity = Math.min(opacity, xray ? 0.08 : 0.42);
  return (
    <>
      <mesh position={[0, -0.18, 0]} receiveShadow><boxGeometry args={[width, 0.26, depth]} /><meshStandardMaterial color={PHYSICAL_COLORS['cmp-enclosure']} transparent opacity={shellOpacity} roughness={0.5} metalness={0.3} depthWrite={!xray} /></mesh>
      <mesh position={[0, 0.03, -depth / 2 + 0.12]}><boxGeometry args={[width, 0.38, 0.16]} /><meshStandardMaterial color="#475569" transparent opacity={Math.min(opacity, xray ? 0.12 : 0.58)} roughness={0.44} metalness={0.34} depthWrite={!xray} /></mesh>
      <mesh position={[-width / 2 + 0.12, 0.03, 0]}><boxGeometry args={[0.16, 0.34, depth]} /><meshStandardMaterial color="#475569" transparent opacity={Math.min(opacity, xray ? 0.1 : 0.5)} roughness={0.44} metalness={0.34} depthWrite={!xray} /></mesh>
      <mesh position={[width / 2 - 0.12, 0.03, 0]}><boxGeometry args={[0.16, 0.34, depth]} /><meshStandardMaterial color="#475569" transparent opacity={Math.min(opacity, xray ? 0.1 : 0.5)} roughness={0.44} metalness={0.34} depthWrite={!xray} /></mesh>
      {phase === 'construct' && activeCandidateId === 'low-risk' ? (
        <>
          <mesh position={[0, 0.14, -depth / 2 + 0.55]}><boxGeometry args={[width - 0.65, 0.12, 0.12]} /><meshStandardMaterial color="#64748b" metalness={0.65} roughness={0.28} /></mesh>
          <mesh position={[0, 0.14, depth / 2 - 0.55]}><boxGeometry args={[width - 0.65, 0.12, 0.12]} /><meshStandardMaterial color="#64748b" metalness={0.65} roughness={0.28} /></mesh>
        </>
      ) : null}
    </>
  );
}

function GapBody({ width, height, depth }: { width: number; height: number; depth: number }) {
  return (
    <mesh>
      <boxGeometry args={[width, Math.max(height, 0.34), depth]} />
      <meshBasicMaterial color="#ef4444" transparent opacity={0.18} wireframe />
    </mesh>
  );
}

function GenericBody({ entity, width, height, depth, opacity }: { entity: WorkbenchEntity; width: number; height: number; depth: number; opacity: number }) {
  return <mesh castShadow receiveShadow><boxGeometry args={[width, height, depth]} /><meshStandardMaterial color={PHYSICAL_COLORS[entity.id] ?? '#475569'} roughness={0.5} metalness={entity.source === 'generated' ? 0.28 : 0.14} transparent opacity={opacity} /></mesh>;
}

function PhysicalBody({ entity, projection, width, height, depth }: { entity: WorkbenchEntity; projection?: MachinePartProjection; width: number; height: number; depth: number }) {
  const opacity = projection?.opacity ?? 1;
  if (projection?.disposition === 'gap') return <GapBody width={width} height={height} depth={depth} />;
  if (entity.id === 'cmp-mainboard') return <MainboardBody width={width} height={height} depth={depth} documented={projection?.variant === 'documented-mainboard'} opacity={opacity} />;
  if (entity.id === 'cmp-display') return <DisplayBody width={width} height={height} depth={depth} variant={projection?.variant ?? 'controlled-display'} opacity={opacity} />;
  if (entity.id === 'cmp-keyboard') return <KeyboardBody width={width} height={height} depth={depth} opacity={opacity} />;
  if (entity.id === 'cmp-battery') return projection?.variant === 'gap' ? <GapBody width={width} height={height} depth={depth} /> : <BatteryBody width={width} height={height} depth={depth} opacity={opacity} />;
  if (entity.id === 'cmp-cooling') return <CoolingBody opacity={opacity} />;
  if (entity.id === 'cmp-enclosure') return <EnclosureBody width={width} depth={depth} opacity={opacity} />;
  return <GenericBody entity={entity} width={width} height={height} depth={depth} opacity={opacity} />;
}

function MachinePart({ entity, candidateProjection }: { entity: WorkbenchEntity; candidateProjection?: CandidateMachineProjection }) {
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const isolatedEntityId = useMachineWorkbenchStore((state) => state.isolatedEntityId);
  const exploded = useMachineWorkbenchStore((state) => state.exploded);
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);

  if (!entity.spatial) return null;
  const projection = phase === 'construct' ? candidateProjection?.parts[entity.id] : undefined;
  if (projection?.visible === false) return null;

  const selectedEntity = deck001EntityMap.get(selectedEntityId);
  const directlySelected = selectedEntityId === entity.id;
  const inSelectedSubsystem = selectedEntity?.kind === 'subsystem' && selectedEntity.children.includes(entity.id);
  const emphasized = directlySelected || inSelectedSubsystem;
  const hiddenByIsolation = Boolean(isolatedEntityId && isolatedEntityId !== entity.id);
  const scale = projection?.sizeScale ?? [1, 1, 1];
  const [width, height, depth] = entity.spatial.size.map((value, index) => value * scale[index]) as [number, number, number];
  const position = explodedPosition(entity, exploded, projection);
  const focusedSelection = Boolean(selectedEntity && selectedEntity.kind !== 'machine');
  const alwaysLabel = phase === 'construct' && projection && ['held', 'gap'].includes(projection.disposition) && !focusedSelection;

  return (
    <group
      position={position}
      visible={!hiddenByIsolation}
      onClick={(event) => { event.stopPropagation(); setSelectedEntityId(entity.id); }}
      onDoubleClick={(event) => { event.stopPropagation(); setSelectedEntityId(entity.id); requestFrameSelection(); }}
    >
      <PhysicalBody entity={entity} projection={projection} width={width} height={height} depth={depth} />
      {entity.id !== 'cmp-enclosure' ? <StatusShell entity={entity} projection={projection} width={width} height={height} depth={depth} selected={emphasized} /> : null}
      {directlySelected || alwaysLabel ? (
        <Html center position={[0, Math.max(height / 2 + 0.46, 0.62), 0]} distanceFactor={9}>
          <div data-testid="machine-part-status-label" data-projection-disposition={projection?.disposition ?? 'none'} className={`pointer-events-none whitespace-nowrap rounded-md border bg-slate-950/92 px-2.5 py-1.5 text-[10px] font-semibold shadow-2xl ${alwaysLabel ? 'border-amber-300/30 text-amber-100' : 'border-cyan-300/30 text-cyan-50'}`}>
            {phase === 'construct' && projection ? projection.resourceName : entity.name}
            <span className="ml-1 text-slate-500">·</span>
            <span className={`ml-1 uppercase ${alwaysLabel ? 'text-amber-300' : 'text-cyan-300'}`}>{phase === 'construct' && projection ? projection.label : entity.authority}</span>
          </div>
        </Html>
      ) : null}
    </group>
  );
}

function InterfaceLines({ candidateProjection }: { candidateProjection?: CandidateMachineProjection }) {
  const activeLens = useMachineWorkbenchStore((state) => state.activeLens);
  const exploded = useMachineWorkbenchStore((state) => state.exploded);
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const scopedIds = selectionScope(selectedEntityId);

  if (activeLens !== 'interfaces' && activeLens !== 'constraints') return null;
  const visibleLinks = activeLens === 'constraints'
    ? deck001Interfaces.filter((link) => link.authority === 'blocked' || link.authority === 'unknown')
    : deck001Interfaces;

  return (
    <>
      {visibleLinks.map((link) => {
        const from = deck001EntityMap.get(link.from);
        const to = deck001EntityMap.get(link.to);
        if (!from?.spatial || !to?.spatial) return null;
        const fromProjection = phase === 'construct' ? candidateProjection?.parts[from.id] : undefined;
        const toProjection = phase === 'construct' ? candidateProjection?.parts[to.id] : undefined;
        if (fromProjection?.visible === false || toProjection?.visible === false) return null;
        const fromPosition = explodedPosition(from, exploded, fromProjection);
        const toPosition = explodedPosition(to, exploded, toProjection);
        const highlighted = scopedIds.has(from.id) || scopedIds.has(to.id);
        const hasGap = fromProjection?.disposition === 'gap' || toProjection?.disposition === 'gap';
        const lineColor = hasGap ? PROJECTION_COLORS.gap : AUTHORITY_COLORS[link.authority];
        const midpoint: [number, number, number] = [(fromPosition[0] + toPosition[0]) / 2, (fromPosition[1] + toPosition[1]) / 2 + 0.24, (fromPosition[2] + toPosition[2]) / 2];
        return (
          <group key={link.id}>
            <Line points={[fromPosition, toPosition]} color={lineColor} lineWidth={highlighted ? 2.5 : 0.8} transparent opacity={highlighted ? 0.98 : 0.22} onClick={(event) => { event.stopPropagation(); setSelectedEntityId(link.authority === 'blocked' ? link.to : link.from); }} />
            {highlighted ? (
              <>
                <mesh position={fromPosition}><sphereGeometry args={[0.095, 16, 16]} /><meshBasicMaterial color={lineColor} /></mesh>
                <mesh position={toPosition}><sphereGeometry args={[0.095, 16, 16]} /><meshBasicMaterial color={lineColor} /></mesh>
                <Html center position={midpoint} distanceFactor={10}><div className="pointer-events-none whitespace-nowrap rounded border border-white/10 bg-slate-950/88 px-2 py-1 text-[9px] font-medium text-slate-200 shadow-xl">{link.kind} <span className="ml-1 uppercase text-slate-500">{hasGap ? 'resource gap' : link.authority}</span></div></Html>
              </>
            ) : null}
          </group>
        );
      })}
    </>
  );
}

function legendForLens(lens: WorkbenchLens, construct: boolean) {
  if (construct) return Object.entries(PROJECTION_COLORS).filter(([label]) => label !== 'suppressed').map(([label, color]) => ({ label, color }));
  if (lens === 'provenance') return Object.entries(SOURCE_COLORS).map(([label, color]) => ({ label, color }));
  if (lens === 'constraints') return [{ label: 'blocking', color: '#ef4444' }, { label: 'unresolved', color: '#f59e0b' }, { label: 'clear', color: '#475569' }];
  return Object.entries(AUTHORITY_COLORS).map(([label, color]) => ({ label, color }));
}

export function MachineAssemblyViewport() {
  const activeLens = useMachineWorkbenchStore((state) => state.activeLens);
  const xray = useMachineWorkbenchStore((state) => state.xray);
  const cameraPreset = useMachineWorkbenchStore((state) => state.cameraPreset);
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const plannerSource = useMachineWorkbenchStore((state) => state.plannerSource);
  const plannerProjection = useMachineWorkbenchStore((state) => state.plannerProjections[state.activeCandidateId]);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const setCameraPreset = useMachineWorkbenchStore((state) => state.setCameraPreset);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const toggleXray = useMachineWorkbenchStore((state) => state.toggleXray);
  const parts = useMemo(() => deck001Entities.filter((entity) => entity.kind === 'component' && entity.spatial), []);
  const candidateProjection = useMemo(
    () => phase === 'construct' ? buildCandidateMachineProjection(activeCandidateId, plannerSource, plannerProjection) : undefined,
    [phase, activeCandidateId, plannerSource, plannerProjection],
  );
  const legend = legendForLens(activeLens, phase === 'construct');
  const controlsRef = useRef<CameraControls | null>(null);

  return (
    <div className="relative h-full min-h-[420px] overflow-hidden bg-[#050912]">
      <Canvas camera={{ position: [11.5, 8.4, 13.8], fov: 44, near: 0.1, far: 200 }} shadows onPointerMissed={() => setSelectedEntityId('deck-001')}>
        <color attach="background" args={['#050912']} />
        <ambientLight intensity={0.9} />
        <directionalLight position={[8, 13, 9]} intensity={2.1} castShadow />
        <directionalLight position={[-7, 5, -4]} intensity={0.65} />
        <group position={[0, -0.18, 0]}>
          {parts.map((entity) => <MachinePart key={entity.id} entity={entity} candidateProjection={candidateProjection} />)}
          <InterfaceLines candidateProjection={candidateProjection} />
          <DeclaredInterfaceAccessOverlays />
        </group>
        <Grid args={[32, 32]} cellSize={0.5} cellThickness={0.35} cellColor="#16243a" sectionSize={5} sectionThickness={0.8} sectionColor="#25466b" fadeDistance={28} fadeStrength={1.8} position={[0, -0.42, 0]} />
        <CameraControls ref={controlsRef} makeDefault minDistance={3.5} maxDistance={38} smoothTime={0.22} draggingSmoothTime={0.1} />
        <CameraDirector controlsRef={controlsRef} />
      </Canvas>

      <div className="pointer-events-none absolute left-4 top-4 rounded-lg border border-white/10 bg-slate-950/82 px-3 py-2.5 text-[11px] text-slate-300 shadow-xl backdrop-blur">
        <div className="flex items-center gap-2 font-semibold uppercase tracking-[0.16em] text-slate-100">
          {phase === 'construct' ? 'candidate spatial projection' : `${activeLens} lens`}
          {xray ? <span className="rounded border border-cyan-300/20 bg-cyan-300/10 px-1.5 py-0.5 text-[8px] tracking-[0.12em] text-cyan-200">XRAY</span> : null}
        </div>
        {phase === 'construct' && candidateProjection ? (
          <div className="mt-1 flex flex-wrap gap-x-2 text-[9px] text-slate-400" data-testid="candidate-spatial-projection">
            <span>{activeCandidateId}</span><span>·</span><span>{plannerSource}</span><span>·</span><span>{candidateProjection.substitutedCount} substitute</span><span>·</span><span>{candidateProjection.heldCount} held</span><span>·</span><span>{candidateProjection.gapCount} gaps</span>
          </div>
        ) : <div className="mt-1 text-slate-400">Click to inspect · double-click to frame · orbit directly in 3D.</div>}
        {phase === 'construct' ? <div className="mt-1 text-[9px] text-amber-100/55">Spatial shapes are working projections, not measured geometry or build authority.</div> : null}
      </div>

      <div className="pointer-events-auto absolute right-4 top-4 flex items-center gap-1 rounded-lg border border-white/10 bg-slate-950/82 p-1 shadow-xl backdrop-blur">
        <button type="button" onClick={requestFrameSelection} aria-label="Frame selection in 3D" title="Frame selected hardware" className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-300 transition hover:bg-white/8 hover:text-white"><Crosshair className="h-3.5 w-3.5" /> Frame</button>
        <button type="button" onClick={toggleXray} aria-label="X-ray shell" aria-pressed={xray} title="Ghost the enclosure shell" className={`inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-[9px] font-semibold uppercase tracking-[0.1em] transition ${xray ? 'bg-cyan-300/10 text-cyan-100 ring-1 ring-cyan-300/20' : 'text-slate-400 hover:bg-white/8 hover:text-white'}`}>{xray ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />} X-ray</button>
        <span className="mx-0.5 h-5 w-px bg-white/10" />
        {CAMERA_PRESETS.map((preset) => <button key={preset.id} type="button" onClick={() => setCameraPreset(preset.id)} aria-label={preset.aria} aria-pressed={cameraPreset === preset.id} className={`h-8 rounded-md px-2 text-[9px] font-semibold tracking-[0.08em] transition ${cameraPreset === preset.id ? 'bg-white/10 text-white' : 'text-slate-500 hover:bg-white/6 hover:text-slate-200'}`}>{preset.label}</button>)}
      </div>

      <div className="pointer-events-none absolute bottom-4 right-4 flex max-w-[75%] flex-wrap justify-end gap-2 text-[10px] font-medium text-slate-300">
        {legend.map(({ label, color }) => <span key={label} className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-slate-950/78 px-2 py-1 backdrop-blur"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />{label}</span>)}
      </div>
    </div>
  );
}
