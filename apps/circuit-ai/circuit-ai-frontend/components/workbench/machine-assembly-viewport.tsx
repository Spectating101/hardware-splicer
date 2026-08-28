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
import { useWorkbenchStore } from '@/lib/workbench-store';

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

function entityColor(entity: WorkbenchEntity, lens: string) {
  if (lens === 'provenance') return SOURCE_COLORS[entity.source];
  if (lens === 'constraints' && (entity.authority === 'blocked' || entity.unresolved.length > 2)) return '#ef4444';
  if (lens === 'interfaces') return entity.kind === 'component' ? '#94a3b8' : '#334155';
  return AUTHORITY_COLORS[entity.authority];
}

function explodedPosition(entity: WorkbenchEntity, exploded: boolean): [number, number, number] {
  if (!entity.spatial) return [0, 0, 0];
  if (!exploded || entity.id === 'cmp-enclosure') return entity.spatial.position;
  const [x, y, z] = entity.spatial.position;
  const magnitude = Math.max(Math.hypot(x, z), 1);
  const spread = 1.35;
  return [x + (x / magnitude) * spread, y + 0.45, z + (z / magnitude) * spread];
}

function MachinePart({ entity }: { entity: WorkbenchEntity }) {
  const selectedEntityId = useWorkbenchStore((state) => state.selectedEntityId);
  const isolatedEntityId = useWorkbenchStore((state) => state.isolatedEntityId);
  const activeLens = useWorkbenchStore((state) => state.activeLens);
  const exploded = useWorkbenchStore((state) => state.exploded);
  const setSelectedEntityId = useWorkbenchStore((state) => state.setSelectedEntityId);

  if (!entity.spatial) return null;

  const selected = selectedEntityId === entity.id;
  const hiddenByIsolation = Boolean(isolatedEntityId && isolatedEntityId !== entity.id);
  const [width, height, depth] = entity.spatial.size;
  const position = explodedPosition(entity, exploded);
  const opacity = hiddenByIsolation ? 0.08 : entity.authority === 'unknown' || entity.authority === 'proposed' ? 0.56 : 0.9;
  const color = entityColor(entity, activeLens);

  return (
    <group position={position}>
      <mesh
        onClick={(event) => {
          event.stopPropagation();
          setSelectedEntityId(entity.id);
        }}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial
          color={color}
          transparent
          opacity={opacity}
          roughness={0.46}
          metalness={entity.source === 'generated' ? 0.28 : 0.12}
          emissive={selected ? '#dbeafe' : '#000000'}
          emissiveIntensity={selected ? 0.32 : 0}
          wireframe={entity.authority === 'unknown'}
        />
      </mesh>
      {selected ? (
        <Html center position={[0, Math.max(height / 2 + 0.4, 0.55), 0]} distanceFactor={9}>
          <div className="pointer-events-none whitespace-nowrap rounded-md border border-cyan-300/30 bg-slate-950/90 px-2 py-1 text-[10px] font-semibold text-cyan-100 shadow-xl">
            {entity.name} · {entity.authority.toUpperCase()}
          </div>
        </Html>
      ) : null}
    </group>
  );
}

function InterfaceLines() {
  const activeLens = useWorkbenchStore((state) => state.activeLens);
  const exploded = useWorkbenchStore((state) => state.exploded);
  const selectedEntityId = useWorkbenchStore((state) => state.selectedEntityId);
  const setSelectedEntityId = useWorkbenchStore((state) => state.setSelectedEntityId);

  if (activeLens !== 'interfaces' && activeLens !== 'constraints') return null;

  return (
    <>
      {deck001Interfaces.map((link) => {
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
            lineWidth={highlighted ? 3 : 1.2}
            transparent
            opacity={highlighted ? 1 : 0.72}
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

export function MachineAssemblyViewport() {
  const activeLens = useWorkbenchStore((state) => state.activeLens);
  const setSelectedEntityId = useWorkbenchStore((state) => state.setSelectedEntityId);
  const parts = useMemo(() => deck001Entities.filter((entity) => entity.kind === 'component' && entity.spatial), []);

  return (
    <div className="relative h-full min-h-[420px] overflow-hidden bg-[#050912]">
      <Canvas
        camera={{ position: [11.5, 9.2, 12.5], fov: 42, near: 0.1, far: 200 }}
        shadows
        onPointerMissed={() => setSelectedEntityId('deck-001')}
      >
        <color attach="background" args={['#050912']} />
        <ambientLight intensity={1.25} />
        <directionalLight position={[7, 12, 8]} intensity={2.4} castShadow />
        <directionalLight position={[-8, 5, -6]} intensity={0.8} />
        <group position={[0, 0.25, 0]}>
          {parts.map((entity) => (
            <MachinePart key={entity.id} entity={entity} />
          ))}
          <InterfaceLines />
        </group>
        <Grid
          args={[30, 30]}
          cellSize={0.5}
          cellThickness={0.5}
          sectionSize={5}
          sectionThickness={1}
          fadeDistance={30}
          fadeStrength={1.5}
          position={[0, -0.08, 0]}
        />
        <CameraControls makeDefault minDistance={5} maxDistance={36} />
      </Canvas>

      <div className="pointer-events-none absolute left-4 top-4 rounded-lg border border-white/10 bg-slate-950/78 px-3 py-2 text-[11px] text-slate-300 backdrop-blur">
        <div className="font-semibold uppercase tracking-[0.16em] text-slate-100">{activeLens} lens</div>
        <div className="mt-1 text-slate-400">Click geometry to synchronize the full workbench.</div>
      </div>

      <div className="pointer-events-none absolute bottom-4 right-4 flex flex-wrap justify-end gap-2 text-[10px] font-medium text-slate-300">
        {Object.entries(AUTHORITY_COLORS).map(([state, color]) => (
          <span key={state} className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-slate-950/75 px-2 py-1 backdrop-blur">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
            {state}
          </span>
        ))}
      </div>
    </div>
  );
}
