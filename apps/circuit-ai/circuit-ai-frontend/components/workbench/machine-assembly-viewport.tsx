'use client';

import { Canvas } from '@react-three/fiber';
import { CameraControls, Grid, Html, Line } from '@react-three/drei';
import { useMemo } from 'react';
import {
  deck001Entities,
  deck001EntityMap,
  deck001Interfaces,
  type AuthorityState,
  type ResourceSource,
  type WorkbenchEntity,
} from '@/lib/workbench-demo';
import { useMachineWorkbenchStore, type WorkbenchLens } from '@/lib/machine-workbench-store';

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

function explodedPosition(entity: WorkbenchEntity, exploded: boolean): [number, number, number] {
  const base = scenePosition(entity);
  if (!entity.spatial || !exploded || entity.id === 'cmp-enclosure') return base;
  const [x, y, z] = base;
  const magnitude = Math.max(Math.hypot(x, z), 1);
  const spread = 1.15;
  return [x + (x / magnitude) * spread, y + 0.38, z + (z / magnitude) * spread];
}

function StatusShell({ entity, width, height, depth, selected }: { entity: WorkbenchEntity; width: number; height: number; depth: number; selected: boolean }) {
  const activeLens = useMachineWorkbenchStore((state) => state.activeLens);
  const color = semanticColor(entity, activeLens);
  const relevant = activeLens !== 'interfaces' || selected;
  const opacity = selected ? 0.95 : relevant ? 0.38 : 0.12;

  return (
    <mesh scale={[1.025, 1.08, 1.025]}>
      <boxGeometry args={[width, height, depth]} />
      <meshBasicMaterial color={color} transparent opacity={opacity} wireframe depthWrite={false} />
    </mesh>
  );
}

function MainboardBody({ width, height, depth }: { width: number; height: number; depth: number }) {
  return (
    <>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color={PHYSICAL_COLORS['cmp-mainboard']} roughness={0.6} metalness={0.08} />
      </mesh>
      <mesh position={[0.35, height / 2 + 0.13, -0.25]} castShadow>
        <boxGeometry args={[1.1, 0.22, 1.05]} />
        <meshStandardMaterial color="#111827" roughness={0.32} metalness={0.45} />
      </mesh>
      <mesh position={[-1.15, height / 2 + 0.09, 0.7]} castShadow>
        <boxGeometry args={[1.45, 0.14, 0.34]} />
        <meshStandardMaterial color="#1f2937" roughness={0.42} metalness={0.25} />
      </mesh>
      <mesh position={[1.15, height / 2 + 0.08, 0.8]} castShadow>
        <boxGeometry args={[0.9, 0.12, 0.38]} />
        <meshStandardMaterial color="#334155" roughness={0.45} metalness={0.18} />
      </mesh>
    </>
  );
}

function DisplayBody({ width, height, depth }: { width: number; height: number; depth: number }) {
  return (
    <>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color={PHYSICAL_COLORS['cmp-display']} roughness={0.36} metalness={0.28} />
      </mesh>
      <mesh position={[0, 0, depth / 2 + 0.045]}>
        <boxGeometry args={[width - 0.55, height - 0.52, 0.06]} />
        <meshStandardMaterial color="#071827" emissive="#0e7490" emissiveIntensity={0.2} roughness={0.2} metalness={0.05} />
      </mesh>
      <mesh position={[0, -height / 2 - 0.12, 0.08]} castShadow>
        <boxGeometry args={[2.1, 0.18, 0.42]} />
        <meshStandardMaterial color="#334155" roughness={0.42} metalness={0.3} />
      </mesh>
    </>
  );
}

function KeyboardBody({ width, height, depth }: { width: number; height: number; depth: number }) {
  const keys = Array.from({ length: 40 }, (_, index) => ({ row: Math.floor(index / 10), col: index % 10 }));
  return (
    <>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color={PHYSICAL_COLORS['cmp-keyboard']} roughness={0.58} metalness={0.14} />
      </mesh>
      {keys.map(({ row, col }) => (
        <mesh key={`${row}-${col}`} position={[-3.3 + col * 0.72, height / 2 + 0.075, -0.78 + row * 0.52]} castShadow>
          <boxGeometry args={[0.56, 0.09, 0.39]} />
          <meshStandardMaterial color="#0f172a" roughness={0.52} metalness={0.18} />
        </mesh>
      ))}
      <mesh position={[2.9, height / 2 + 0.06, 0.78]}>
        <boxGeometry args={[1.15, 0.06, 0.62]} />
        <meshStandardMaterial color="#172033" roughness={0.45} metalness={0.15} />
      </mesh>
    </>
  );
}

function BatteryBody({ width, height, depth }: { width: number; height: number; depth: number }) {
  return (
    <>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color={PHYSICAL_COLORS['cmp-battery']} roughness={0.48} metalness={0.12} />
      </mesh>
      {[-0.9, 0, 0.9].map((x) => (
        <mesh key={x} position={[x, height / 2 + 0.025, 0]}>
          <boxGeometry args={[0.04, 0.035, depth - 0.22]} />
          <meshBasicMaterial color="#c4b5fd" transparent opacity={0.48} />
        </mesh>
      ))}
    </>
  );
}

function CoolingBody() {
  return (
    <>
      <mesh castShadow>
        <cylinderGeometry args={[0.72, 0.72, 0.22, 32]} />
        <meshStandardMaterial color={PHYSICAL_COLORS['cmp-cooling']} roughness={0.42} metalness={0.32} />
      </mesh>
      <mesh position={[0, 0.13, 0]}>
        <cylinderGeometry args={[0.22, 0.22, 0.08, 24]} />
        <meshStandardMaterial color="#111827" roughness={0.32} metalness={0.38} />
      </mesh>
    </>
  );
}

function EnclosureBody({ width, depth }: { width: number; depth: number }) {
  return (
    <>
      <mesh position={[0, -0.18, 0]} receiveShadow>
        <boxGeometry args={[width, 0.26, depth]} />
        <meshStandardMaterial color={PHYSICAL_COLORS['cmp-enclosure']} transparent opacity={0.42} roughness={0.5} metalness={0.3} />
      </mesh>
      <mesh position={[0, 0.03, -depth / 2 + 0.12]}>
        <boxGeometry args={[width, 0.38, 0.16]} />
        <meshStandardMaterial color="#475569" transparent opacity={0.58} roughness={0.44} metalness={0.34} />
      </mesh>
      <mesh position={[-width / 2 + 0.12, 0.03, 0]}>
        <boxGeometry args={[0.16, 0.34, depth]} />
        <meshStandardMaterial color="#475569" transparent opacity={0.5} roughness={0.44} metalness={0.34} />
      </mesh>
      <mesh position={[width / 2 - 0.12, 0.03, 0]}>
        <boxGeometry args={[0.16, 0.34, depth]} />
        <meshStandardMaterial color="#475569" transparent opacity={0.5} roughness={0.44} metalness={0.34} />
      </mesh>
    </>
  );
}

function GenericBody({ entity, width, height, depth }: { entity: WorkbenchEntity; width: number; height: number; depth: number }) {
  return (
    <mesh castShadow receiveShadow>
      <boxGeometry args={[width, height, depth]} />
      <meshStandardMaterial color={PHYSICAL_COLORS[entity.id] ?? '#475569'} roughness={0.5} metalness={entity.source === 'generated' ? 0.28 : 0.14} />
    </mesh>
  );
}

function PhysicalBody({ entity, width, height, depth }: { entity: WorkbenchEntity; width: number; height: number; depth: number }) {
  if (entity.id === 'cmp-mainboard') return <MainboardBody width={width} height={height} depth={depth} />;
  if (entity.id === 'cmp-display') return <DisplayBody width={width} height={height} depth={depth} />;
  if (entity.id === 'cmp-keyboard') return <KeyboardBody width={width} height={height} depth={depth} />;
  if (entity.id === 'cmp-battery') return <BatteryBody width={width} height={height} depth={depth} />;
  if (entity.id === 'cmp-cooling') return <CoolingBody />;
  if (entity.id === 'cmp-enclosure') return <EnclosureBody width={width} depth={depth} />;
  return <GenericBody entity={entity} width={width} height={height} depth={depth} />;
}

function MachinePart({ entity }: { entity: WorkbenchEntity }) {
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const isolatedEntityId = useMachineWorkbenchStore((state) => state.isolatedEntityId);
  const exploded = useMachineWorkbenchStore((state) => state.exploded);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);

  if (!entity.spatial) return null;

  const selected = selectedEntityId === entity.id;
  const hiddenByIsolation = Boolean(isolatedEntityId && isolatedEntityId !== entity.id);
  const [width, height, depth] = entity.spatial.size;
  const position = explodedPosition(entity, exploded);

  return (
    <group
      position={position}
      visible={!hiddenByIsolation}
      onClick={(event) => {
        event.stopPropagation();
        setSelectedEntityId(entity.id);
      }}
    >
      <PhysicalBody entity={entity} width={width} height={height} depth={depth} />
      {entity.id !== 'cmp-enclosure' ? <StatusShell entity={entity} width={width} height={height} depth={depth} selected={selected} /> : null}
      {selected ? (
        <Html center position={[0, Math.max(height / 2 + 0.46, 0.62), 0]} distanceFactor={9}>
          <div className="pointer-events-none whitespace-nowrap rounded-md border border-cyan-300/30 bg-slate-950/92 px-2.5 py-1.5 text-[10px] font-semibold text-cyan-50 shadow-2xl">
            {entity.name} <span className="ml-1 text-slate-500">·</span> <span className="ml-1 text-cyan-300">{entity.authority.toUpperCase()}</span>
          </div>
        </Html>
      ) : null}
    </group>
  );
}

function InterfaceLines() {
  const activeLens = useMachineWorkbenchStore((state) => state.activeLens);
  const exploded = useMachineWorkbenchStore((state) => state.exploded);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);

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
        const fromPosition = explodedPosition(from, exploded);
        const toPosition = explodedPosition(to, exploded);
        const highlighted = selectedEntityId === from.id || selectedEntityId === to.id;
        return (
          <Line
            key={link.id}
            points={[fromPosition, toPosition]}
            color={AUTHORITY_COLORS[link.authority]}
            lineWidth={highlighted ? 2.4 : 0.9}
            transparent
            opacity={highlighted ? 0.95 : 0.38}
            onClick={(event) => {
              event.stopPropagation();
              setSelectedEntityId(link.authority === 'blocked' ? link.to : link.from);
            }}
          />
        );
      })}
    </>
  );
}

function legendForLens(lens: WorkbenchLens) {
  if (lens === 'provenance') {
    return Object.entries(SOURCE_COLORS).map(([label, color]) => ({ label, color }));
  }
  if (lens === 'constraints') {
    return [
      { label: 'blocking', color: '#ef4444' },
      { label: 'unresolved', color: '#f59e0b' },
      { label: 'clear', color: '#475569' },
    ];
  }
  return Object.entries(AUTHORITY_COLORS).map(([label, color]) => ({ label, color }));
}

export function MachineAssemblyViewport() {
  const activeLens = useMachineWorkbenchStore((state) => state.activeLens);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const parts = useMemo(() => deck001Entities.filter((entity) => entity.kind === 'component' && entity.spatial), []);
  const legend = legendForLens(activeLens);

  return (
    <div className="relative h-full min-h-[420px] overflow-hidden bg-[#050912]">
      <Canvas
        camera={{ position: [11.5, 8.4, 13.8], fov: 44, near: 0.1, far: 200 }}
        shadows
        onPointerMissed={() => setSelectedEntityId('deck-001')}
      >
        <color attach="background" args={['#050912']} />
        <ambientLight intensity={0.9} />
        <directionalLight position={[8, 13, 9]} intensity={2.1} castShadow />
        <directionalLight position={[-7, 5, -4]} intensity={0.65} />
        <group position={[0, -0.18, 0]}>
          {parts.map((entity) => (
            <MachinePart key={entity.id} entity={entity} />
          ))}
          <InterfaceLines />
        </group>
        <Grid
          args={[32, 32]}
          cellSize={0.5}
          cellThickness={0.35}
          cellColor="#16243a"
          sectionSize={5}
          sectionThickness={0.8}
          sectionColor="#25466b"
          fadeDistance={28}
          fadeStrength={1.8}
          position={[0, -0.42, 0]}
        />
        <CameraControls makeDefault minDistance={5} maxDistance={34} />
      </Canvas>

      <div className="pointer-events-none absolute left-4 top-4 rounded-lg border border-white/10 bg-slate-950/82 px-3 py-2.5 text-[11px] text-slate-300 shadow-xl backdrop-blur">
        <div className="font-semibold uppercase tracking-[0.16em] text-slate-100">{activeLens} lens</div>
        <div className="mt-1 text-slate-400">Spatial architecture fixture · click hardware to inspect.</div>
      </div>

      <div className="pointer-events-none absolute bottom-4 right-4 flex max-w-[75%] flex-wrap justify-end gap-2 text-[10px] font-medium text-slate-300">
        {legend.map(({ label, color }) => (
          <span key={label} className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-slate-950/78 px-2 py-1 backdrop-blur">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
