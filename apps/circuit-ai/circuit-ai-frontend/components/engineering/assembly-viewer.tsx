'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Box, ChevronLeft, ChevronRight, LoaderCircle, Pause, Play, RotateCcw } from 'lucide-react';
import type * as ThreeNS from 'three';
import type { OrbitControls as OrbitControlsType } from 'three/examples/jsm/controls/OrbitControls.js';

export type AssemblyPart = {
  id: string;
  ref: string;
  do_not_populate: boolean;
  value: string;
  footprint: string;
  kind: string;
  side: 'front' | 'back';
  corners: number[][];
  height_mm: number;
  height_basis: string;
  outline_basis: string;
  pin1: { x: number; y: number } | null;
  pads: { number: string; x: number; y: number; net: string | null }[];
  mounting?: string | null;
  identity?: { mpn: string | null; manufacturer: string | null };
  salvage?: { verdict: string; label: string; effort: string; tool: string; reasons: string[]; hazards: string[]; basis: string };
};
export type AssemblyCheck = { kind: string; check: string; from: string; to: string; net: string; expect: string };
export type AssemblyStep = {
  step_id: string;
  order: number;
  title: string;
  instruction: string;
  kind: string;
  side: 'front' | 'back';
  turn_board_over: boolean;
  refs: string[];
  part_ids: string[];
  checks: AssemblyCheck[];
  verdict?: string;
  verdict_label?: string;
  effort?: string;
};
export type AssemblyPlan = {
  mode?: string;
  limits?: string[];
  summary?: { counts: Record<string, number>; keep: { ref: string; what: string; manufacturer: string | null }[] };
  authority: string;
  not_fitted: string[];
  board: { thickness_mm: number; size_mm: number[]; outline: { kind: string; bbox: { x0: number; y0: number; x1: number; y1: number } } };
  parts: AssemblyPart[];
  steps: AssemblyStep[];
  warnings: string[];
};

type Fetched = { ok?: boolean; available?: boolean; reason?: string; error?: string; plan?: AssemblyPlan };
type Stats = { placed: number; flying: number; removed: number };
type SceneApi = { goTo: (index: number, animate: boolean) => void; dispose: () => void };

const FLY_MS = 950;
const STAGGER_MS = 110;
const MAX_STAGGER_MS = 700;
const MAX_LABELS = 8;
const VERDICT_COLORS: Record<string, string> = { keep: '#3fb950', test_first: '#f5c542', identify: '#4c8dff', optional: '#a0a7b4', skip: '#454a54' };
const VERDICT_LABELS: Record<string, string> = { keep: 'Worth taking', test_first: 'Take it, test first', identify: 'Read the marking', optional: 'Cheap to buy new', skip: 'Leave it' };
const VERDICT_CHIP: Record<string, string> = {
  keep: 'bg-emerald-500/20 text-emerald-200',
  test_first: 'bg-amber-400/20 text-amber-200',
  identify: 'bg-sky-500/20 text-sky-200',
  optional: 'bg-stone-500/25 text-stone-200',
  skip: 'bg-stone-700/40 text-stone-300',
};

function checkText(check: { check: string; from: string; to: string }): string {
  switch (check.check) {
    case 'isolation': return `meter between ${check.from} and ${check.to}`;
    case 'continuity': return `beep ${check.from} to ${check.to}`;
    case 'test': return `test ${check.from} with ${check.to}`;
    case 'read_marking': return `read ${check.to} on ${check.from}`;
    case 'inspect': return `inspect the ${check.to} of ${check.from}`;
    default: return `check ${check.from} against ${check.to}`;
  }
}
const COLORS: Record<string, string> = {
  passive: '#d8c79a',
  ic: '#2f3441',
  connector: '#41464f',
  testpoint: '#d6b24a',
  mounting_hole: '#9aa3ad',
  other: '#7b8aa0',
};

/**
 * The build sequence as a 3D animation: each group of parts descends onto its real position on the board, in the order the
 * plan gives. Parts are stand-in boxes sized from the footprint outline with a typical height; the viewer says so. It is a
 * view of retained bytes and carries no authority.
 */
export function AssemblyViewer({
  projectId = '',
  revision = 0,
  mode: initialMode = 'build',
  plan: givenPlan,
}: {
  projectId?: string;
  revision?: number;
  mode?: 'build' | 'salvage';
  /** A plan handed in (a board described by a person) instead of one fetched for a project revision. It has no board model and one mode. */
  plan?: AssemblyPlan;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SceneApi | null>(null);
  const [plan, setPlan] = useState<AssemblyPlan | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'unavailable' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const [stats, setStats] = useState<Stats>({ placed: 0, flying: 0, removed: 0 });
  const [mode, setMode] = useState<'build' | 'salvage'>(givenPlan ? (givenPlan.mode === 'salvage' ? 'salvage' : 'build') : initialMode);
  const salvageMode = mode === 'salvage';
  const what = salvageMode ? 'take-apart plan' : 'build sequence';
  const base = `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/revisions/${revision}`;
  const url = `${base}/${salvageMode ? 'salvage-plan' : 'assembly-plan'}`;
  const boardUrl = `${base}/assembly-plan/board.glb`;

  useEffect(() => {
    let cancelled = false;
    setMessage('');
    setStep(0);
    setPlaying(false);
    setSceneReady(false);
    if (givenPlan) {
      setStats({ placed: 0, flying: 0, removed: 0 });
      setMode(givenPlan.mode === 'salvage' ? 'salvage' : 'build');
      setPlan(givenPlan);
      setState('ready');
      return () => { cancelled = true; };
    }
    setState('loading');
    setPlan(null);
    fetch(url, { cache: 'no-store' })
      .then((response) => response.json())
      .then((body: Fetched) => {
        if (cancelled) return;
        if (body.ok === false) throw new Error(body.error || `The ${what} could not be requested.`);
        if (!body.available || !body.plan) {
          setState('unavailable');
          setMessage(body.reason === 'no retained pcb' ? `This revision has no retained board file, so there is nothing to ${salvageMode ? 'take apart' : 'build'} from.` : body.reason || `No ${what} is available for this revision.`);
          return;
        }
        if (!body.plan.steps.length) {
          setState('unavailable');
          setMessage(salvageMode ? 'The board has nothing to take.' : 'The board has no parts to place.');
          return;
        }
        setPlan(body.plan);
        setState('ready');
      })
      .catch((caught) => {
        if (cancelled) return;
        setState('error');
        setMessage(caught instanceof Error ? caught.message : `The ${what} could not be requested.`);
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, givenPlan]);

  useEffect(() => {
    if (!plan || !hostRef.current) return;
    const host = hostRef.current;
    const labels = labelsRef.current;
    let disposed = false;
    // Everything allocated is tracked here the moment it exists, so cancelling at any point (mid-load, mid-parse, on an
    // error) releases the renderer and its GPU resources instead of waiting for a step that may never run.
    let frame = 0;
    let observer: ResizeObserver | null = null;
    let controls: OrbitControlsType | null = null;
    let renderer: ThreeNS.WebGLRenderer | null = null;
    let scene: ThreeNS.Scene | null = null;
    const labelNodes = new Map<string, HTMLDivElement>();
    const abort = new AbortController();
    const cleanup = () => {
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
      controls?.dispose();
      labelNodes.forEach((node) => node.remove());
      labelNodes.clear();
      scene?.traverse((object) => {
        const mesh = object as ThreeNS.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        const material = mesh.material as ThreeNS.Material | ThreeNS.Material[] | undefined;
        if (Array.isArray(material)) material.forEach((item) => item.dispose());
        else material?.dispose();
      });
      renderer?.dispose();
      // Release the GPU context now rather than whenever the garbage collector gets to it: tabs are switched often.
      renderer?.forceContextLoss();
      renderer?.domElement.remove();
      scene = null;
      renderer = null;
      sceneRef.current = null;
    };

    (async () => {
      try {
        const THREE = await import('three');
        const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
        const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
        if (disposed) return;
        const reduced = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        const world = new THREE.Scene();
        scene = world;
        world.background = new THREE.Color('#0b0d12');
        const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 5000);
        const gl = new THREE.WebGLRenderer({ antialias: true });
        renderer = gl;
        gl.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        host.appendChild(gl.domElement);
        gl.domElement.style.display = 'block';
        world.add(new THREE.HemisphereLight('#ffffff', '#1c2230', 1.5));
        const key = new THREE.DirectionalLight('#ffffff', 2.4);
        key.position.set(60, 120, 80);
        world.add(key);

        const { x0, y0, x1, y1 } = plan.board.outline.bbox;
        const cx = (x0 + x1) / 2;
        const cz = (y0 + y1) / 2;
        const width = x1 - x0;
        const depth = y1 - y0;
        const thickness = plan.board.thickness_mm;
        const span = Math.max(width, depth, 10);
        const explode = span * 0.32;

        const turnTable = new THREE.Group();
        world.add(turnTable);
        // The real bare board (outline, copper, pads, silkscreen) when KiCad can draw it; a plain slab of the right size when not.
        let realBoard = false;
        try {
          // A board a person described has no model from KiCad: a plain slab of the right size stands in.
          const response = givenPlan ? null : await fetch(boardUrl, { cache: 'no-store', signal: abort.signal });
          if (response?.ok) {
            const buffer = await response.arrayBuffer();
            if (disposed) return;
            const gltf = await new Promise<{ scene: ThreeNS.Group }>((resolve, reject) => {
              new GLTFLoader().parse(buffer, '', (result) => resolve(result as never), reject);
            });
            if (disposed) return;
            // KiCad writes metres, with the front face up and the board's y running along z.
            gltf.scene.scale.setScalar(1000);
            gltf.scene.updateMatrixWorld(true);
            const top = new THREE.Box3().setFromObject(gltf.scene).max.y;
            gltf.scene.position.set(-cx, -top, -cz);
            turnTable.add(gltf.scene);
            realBoard = true;
          }
        } catch {
          if (disposed) return;
          realBoard = false;
        }
        if (disposed) return;
        if (!realBoard) {
          const board = new THREE.Mesh(
            new THREE.BoxGeometry(width, thickness, depth),
            new THREE.MeshStandardMaterial({ color: '#17624a', roughness: 0.6, metalness: 0.05 }),
          );
          board.position.set(0, -thickness / 2, 0);
          turnTable.add(board);
          const outline = new THREE.LineSegments(new THREE.EdgesGeometry(board.geometry), new THREE.LineBasicMaterial({ color: '#6fb89f' }));
          outline.position.copy(board.position);
          turnTable.add(outline);
        }

        type Entry = {
          id: string;
          step: number;
          mesh: ThreeNS.Mesh;
          ghost: ThreeNS.LineSegments;
          fade: ThreeNS.Material[];
          rest: number;
          start: number;
          sign: number;
          state: 'hidden' | 'flying' | 'placed' | 'leaving';
          t0: number;
          delay: number;
        };
        const entries = new Map<string, Entry>();
        const stepOf = new Map<string, number>();
        plan.steps.forEach((s, index) => s.part_ids.forEach((id) => stepOf.set(id, index)));
        const refOf = new Map(plan.parts.map((part) => [part.id, part.ref]));

        for (const part of plan.parts) {
          const corners = part.corners;
          // A part the board leaves off (do-not-populate) is not drawn. In the build, a part in no step is not drawn; when taking
          // a board apart, the parts left on it are drawn and stay.
          if (corners.length !== 4 || part.do_not_populate || (!stepOf.has(part.id) && !salvageMode)) continue;
          const [c0, c1, , c3] = corners;
          const sizeX = Math.max(Math.hypot(c1[0] - c0[0], c1[1] - c0[1]), 0.2);
          const sizeZ = Math.max(Math.hypot(c3[0] - c0[0], c3[1] - c0[1]), 0.2);
          const angle = Math.atan2(c1[1] - c0[1], c1[0] - c0[0]);
          const centreX = corners.reduce((sum, c) => sum + c[0], 0) / 4 - cx;
          const centreZ = corners.reduce((sum, c) => sum + c[1], 0) / 4 - cz;
          const flat = part.kind === 'testpoint' || part.kind === 'mounting_hole';
          const hasPins = part.kind === 'connector' && part.pads.length > 0 && part.height_mm > 3;
          // A header is drawn as a low black body with its pins standing up where they will be connected.
          const height = flat ? 0.6 : hasPins ? Math.min(2.5, part.height_mm) : Math.max(part.height_mm, 0.3);
          const round = part.kind === 'mounting_hole' || part.kind === 'testpoint';
          const radius = (Math.min(sizeX, sizeZ) / 2) * (part.kind === 'mounting_hole' ? 0.6 : 1);
          const geometry = round ? new THREE.CylinderGeometry(radius, radius, height, 24) : new THREE.BoxGeometry(sizeX, height, sizeZ);
          const material = new THREE.MeshStandardMaterial({
            color: salvageMode ? (VERDICT_COLORS[part.salvage?.verdict ?? 'optional'] ?? COLORS.other) : (COLORS[part.kind] ?? COLORS.other),
            roughness: 0.55,
            metalness: part.kind === 'testpoint' ? 0.7 : 0.1,
            transparent: true,
            opacity: 1,
            emissive: '#000000',
          });
          const mesh = new THREE.Mesh(geometry, material);
          const sign = part.side === 'back' ? -1 : 1;
          const rest = sign * (part.side === 'back' ? thickness + height / 2 : height / 2);
          const start = rest + sign * explode;
          mesh.rotation.y = -angle;
          mesh.position.set(centreX, rest, centreZ);
          mesh.visible = false;
          turnTable.add(mesh);

          const ghost = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), new THREE.LineBasicMaterial({ color: salvageMode ? '#8b95a3' : '#ffcf5a', transparent: true, opacity: salvageMode ? 0.55 : 0.9 }));
          ghost.rotation.copy(mesh.rotation);
          ghost.position.set(centreX, rest, centreZ);
          ghost.visible = false;
          turnTable.add(ghost);

          // Things that ride along with the part must fade with it. Positions are given in the board's frame, so undo the part's own turn.
          const fade: ThreeNS.Material[] = [];
          const along = (x: number, y: number, z: number) => new THREE.Vector3(x - cx - centreX, y, z - cz - centreZ).applyAxisAngle(new THREE.Vector3(0, 1, 0), angle);
          if (hasPins) {
            const pinHeight = Math.max(part.height_mm - height, 0.5);
            const pinMaterial = new THREE.MeshStandardMaterial({ color: '#d6b24a', metalness: 0.8, roughness: 0.35, transparent: true, opacity: 1 });
            fade.push(pinMaterial);
            for (const pad of part.pads) {
              const pinMesh = new THREE.Mesh(new THREE.BoxGeometry(0.64, pinHeight, 0.64), pinMaterial);
              const at = along(pad.x, 0, pad.y);
              pinMesh.position.set(at.x, sign * (height / 2 + pinHeight / 2), at.z);
              pinMesh.rotation.y = angle;
              mesh.add(pinMesh);
            }
          }
          if (part.pin1 && !round) {
            const markerMaterial = new THREE.MeshBasicMaterial({ color: '#ffffff', transparent: true, opacity: 1 });
            fade.push(markerMaterial);
            const marker = new THREE.Mesh(new THREE.SphereGeometry(Math.max(Math.min(sizeX, sizeZ) * 0.09, 0.22), 12, 8), markerMaterial);
            const at = along(part.pin1.x, 0, part.pin1.y);
            marker.position.set(at.x, sign * (hasPins ? height / 2 + 0.02 : height / 2 + 0.02), at.z);
            mesh.add(marker);
          }
          entries.set(part.id, { id: part.id, step: stepOf.get(part.id) ?? -1, mesh, ghost, fade, rest, start, sign, state: 'hidden', t0: 0, delay: 0 });
        }

        const orbit = new OrbitControls(camera, gl.domElement);
        controls = orbit;
        orbit.enableDamping = true;
        camera.position.set(0, span * 0.8, span * 0.8);
        camera.near = span / 200;
        camera.far = span * 40;
        camera.updateProjectionMatrix();
        orbit.target.set(0, 0, 0);
        orbit.update();

        const resize = () => {
          const w = Math.max(host.clientWidth, 1);
          const h = Math.max(host.clientHeight, 1);
          gl.setSize(w, h, false);
          gl.domElement.style.width = '100%';
          gl.domElement.style.height = '100%';
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
        };
        observer = new ResizeObserver(resize);
        observer.observe(host);
        resize();

        let current = 0;
        let turnTarget = 0;
        let lastReport = '';

        const report = () => {
          let placed = 0;
          let flying = 0;
          let removed = 0;
          entries.forEach((entry) => {
            if (entry.state === 'placed') placed += 1;
            if (entry.state === 'flying' || entry.state === 'leaving') flying += 1;
            if (entry.state === 'hidden' && entry.step >= 0 && salvageMode) removed += 1;
          });
          const moving = Math.abs(turnTable.rotation.x - turnTarget) > 0.01 ? 1 : 0;
          const signature = `${placed}/${flying + moving}/${removed}`;
          if (signature !== lastReport) {
            lastReport = signature;
            setStats({ placed, flying: flying + moving, removed });
          }
        };

        const syncLabels = () => {
          if (!labels) return;
          const wanted = plan.steps[current]?.part_ids ?? [];
          const show = wanted.length > 0 && wanted.length <= MAX_LABELS ? wanted : [];
          labelNodes.forEach((node, id) => {
            if (!show.includes(id)) { node.remove(); labelNodes.delete(id); }
          });
          for (const id of show) {
            if (labelNodes.has(id)) continue;
            const node = document.createElement('div');
            node.textContent = refOf.get(id) ?? id;
            node.setAttribute('data-testid', 'assembly-label');
            node.className = 'pointer-events-none absolute left-0 top-0 rounded bg-amber-300 px-1.5 py-0.5 text-[10px] font-semibold text-stone-950 shadow';
            labels.appendChild(node);
            labelNodes.set(id, node);
          }
        };

        const goTo = (index: number, animate: boolean) => {
          current = Math.min(Math.max(index, 0), plan.steps.length - 1);
          const active = plan.steps[current];
          turnTarget = active.side === 'back' ? Math.PI : 0;
          if (!animate || reduced) turnTable.rotation.x = turnTarget;
          const now = performance.now();
          entries.forEach((entry) => {
            const material = entry.mesh.material as ThreeNS.MeshStandardMaterial;
            const setOpacity = (value: number) => { material.opacity = value; entry.fade.forEach((item) => { item.opacity = value; }); };
            const isCurrent = entry.step === current && active.kind !== 'verify';
            material.emissive.set(isCurrent ? '#ffb43a' : '#000000');
            material.emissiveIntensity = isCurrent ? 0.32 : 0;
            if (salvageMode) {
              // Taking apart: parts in later steps, and parts that stay, are on the board; this step's parts lift off; earlier ones are gone.
              if (entry.step < 0 || entry.step > current) {
                entry.state = 'placed'; entry.mesh.visible = true; entry.mesh.position.y = entry.rest; setOpacity(1); entry.ghost.visible = false;
              } else if (entry.step < current) {
                entry.state = 'hidden'; entry.mesh.visible = false; entry.ghost.visible = true;
              } else if (animate && !reduced) {
                entry.state = 'leaving';
                entry.t0 = now;
                entry.delay = Math.min(Math.max(active.part_ids.indexOf(entry.id), 0) * STAGGER_MS, MAX_STAGGER_MS);
                entry.mesh.visible = true; entry.mesh.position.y = entry.rest; setOpacity(1); entry.ghost.visible = true;
              } else {
                entry.state = 'hidden'; entry.mesh.visible = false; entry.ghost.visible = true;
              }
              return;
            }
            if (entry.step < current || (entry.step === current && active.kind === 'verify')) {
              entry.state = 'placed';
              entry.mesh.visible = true;
              entry.mesh.position.y = entry.rest;
              setOpacity(1);
              entry.ghost.visible = false;
            } else if (entry.step === current) {
              if (animate && !reduced) {
                const order = active.part_ids.indexOf(entry.id);
                entry.state = 'flying';
                entry.t0 = now;
                entry.delay = Math.min(Math.max(order, 0) * STAGGER_MS, MAX_STAGGER_MS);
                entry.mesh.visible = true;
                entry.mesh.position.y = entry.start;
                setOpacity(0);
                entry.ghost.visible = true;
              } else {
                entry.state = 'placed';
                entry.mesh.visible = true;
                entry.mesh.position.y = entry.rest;
                setOpacity(1);
                entry.ghost.visible = false;
              }
            } else {
              entry.state = 'hidden';
              entry.mesh.visible = false;
              entry.ghost.visible = false;
            }
          });
          syncLabels();
          report();
        };

        const project = new THREE.Vector3();
        const tick = () => {
          const now = performance.now();
          entries.forEach((entry) => {
            if (entry.state === 'leaving') {
              const t = Math.min(Math.max((now - entry.t0 - entry.delay) / FLY_MS, 0), 1);
              const eased = t * t * (3 - 2 * t);
              entry.mesh.position.y = entry.rest + (entry.start - entry.rest) * eased;
              const opacity = 1 - eased;
              (entry.mesh.material as ThreeNS.MeshStandardMaterial).opacity = opacity;
              entry.fade.forEach((item) => { item.opacity = opacity; });
              if (t >= 1) { entry.state = 'hidden'; entry.mesh.visible = false; }
              return;
            }
            if (entry.state !== 'flying') return;
            const raw = (now - entry.t0 - entry.delay) / FLY_MS;
            const t = Math.min(Math.max(raw, 0), 1);
            const eased = 1 - Math.pow(1 - t, 3);
            entry.mesh.position.y = entry.start + (entry.rest - entry.start) * eased;
            const opacity = Math.min(eased * 2.2, 1);
            (entry.mesh.material as ThreeNS.MeshStandardMaterial).opacity = opacity;
            entry.fade.forEach((item) => { item.opacity = opacity; });
            if (t >= 1) {
              entry.state = 'placed';
              entry.ghost.visible = false;
              (entry.mesh.material as ThreeNS.MeshStandardMaterial).opacity = 1;
              entry.fade.forEach((item) => { item.opacity = 1; });
            }
          });
          const delta = turnTarget - turnTable.rotation.x;
          if (Math.abs(delta) > 0.002) turnTable.rotation.x += delta * 0.12;
          else turnTable.rotation.x = turnTarget;
          report();
          if (labels && labelNodes.size) {
            const rect = host.getBoundingClientRect();
            labelNodes.forEach((node, id) => {
              const entry = entries.get(id);
              if (!entry) return;
              entry.mesh.getWorldPosition(project);
              project.y += entry.sign * 1.5;
              project.project(camera);
              const visible = project.z < 1 && entry.mesh.visible;
              node.style.display = visible ? 'block' : 'none';
              node.style.transform = `translate(${((project.x + 1) / 2) * rect.width + 6}px, ${((1 - project.y) / 2) * rect.height - 8}px)`;
            });
          }
          orbit.update();
          gl.render(world, camera);
          frame = window.requestAnimationFrame(tick);
        };
        tick();

        sceneRef.current = { goTo, dispose: cleanup };
        if (disposed) {
          cleanup();
          return;
        }
        setSceneReady(true);
      } catch (caught) {
        // Whatever was built before the failure is released, not left holding a WebGL context.
        cleanup();
        if (!disposed) {
          setState('error');
          setMessage(caught instanceof Error ? caught.message : 'The 3D view could not start.');
        }
      }
    })();

    return () => {
      disposed = true;
      abort.abort();
      cleanup();
    };
  }, [plan, url, boardUrl, salvageMode, givenPlan]);

  // Whatever step is chosen, the scene shows it: earlier steps in place, this one arriving, later ones not yet.
  const previous = useRef(-1);
  useEffect(() => {
    if (!sceneReady || !sceneRef.current) return;
    const animate = previous.current >= 0 && step === previous.current + 1;
    sceneRef.current.goTo(step, animate || previous.current === -1);
    previous.current = step;
  }, [step, sceneReady]);
  useEffect(() => {
    if (!sceneReady) previous.current = -1;
  }, [sceneReady]);

  const last = (plan?.steps.length ?? 1) - 1;
  useEffect(() => {
    if (!playing || !sceneReady) return;
    if (stats.flying > 0) return;
    if (step >= last) { setPlaying(false); return; }
    const timer = window.setTimeout(() => setStep((value) => Math.min(value + 1, last)), 1300);
    return () => window.clearTimeout(timer);
  }, [playing, sceneReady, stats.flying, step, last]);

  const go = useCallback((next: number) => setStep(Math.min(Math.max(next, 0), last)), [last]);
  const active = plan?.steps[step];
  const estimateNote = useMemo(() => {
    if (!plan) return '';
    const bases = plan.parts.map((part) => part.outline_basis);
    // A board a person described has no courtyards: its sizes are what they typed, or typical for the package.
    if (bases.some((value) => value.startsWith('typical size') || value === 'the size you typed')) return 'Sizes are typical for each package unless you typed them.';
    if (bases.some((value) => value.startsWith('no outline'))) return 'Some parts have no outline or pads in the file and are drawn as a small box.';
    return bases.some((value) => !value.startsWith('courtyard')) ? 'Some outlines come from pad positions because those footprints have no courtyard.' : '';
  }, [plan]);

  return (
    <div
      className="relative flex h-full min-h-[470px] w-full flex-col bg-[#0b0d12] outline-none"
      data-testid="assembly-viewer"
      data-state={state}
      data-mode={mode}
      data-removed={stats.removed}
      data-step={step}
      data-step-count={plan?.steps.length ?? 0}
      data-placed={stats.placed}
      data-flying={stats.flying}
      data-playing={playing ? '1' : '0'}
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.target instanceof HTMLInputElement) return;
        if (event.key === 'ArrowRight') { event.preventDefault(); go(step + 1); }
        else if (event.key === 'ArrowLeft') { event.preventDefault(); go(step - 1); }
        else if (event.key === ' ') { event.preventDefault(); setPlaying((value) => !value); }
      }}
    >
      <div className="relative min-h-[300px] flex-1">
        <div ref={hostRef} className="absolute inset-0" role="img" aria-label={givenPlan ? `Animated ${what}. Drag to orbit, scroll to zoom.` : `Animated ${what} for revision ${revision}. Drag to orbit, scroll to zoom.`} />
        <div ref={labelsRef} className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true" />
        {state === 'loading' || (state === 'ready' && !sceneReady) ? (
          <div className="absolute inset-0 flex items-center justify-center text-stone-400"><LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" /></div>
        ) : null}
        {state === 'unavailable' || state === 'error' ? (
          <div className="absolute inset-0 flex items-center justify-center p-8">
            <div className="max-w-sm text-center">
              <Box className="mx-auto h-9 w-9 text-stone-600" aria-hidden="true" />
              <div className="mt-3 text-sm font-medium text-stone-200">{state === 'error' ? `The ${what} failed` : `No ${what}`}</div>
              <div className="mt-1 text-xs leading-5 text-stone-400">{message}</div>
            </div>
          </div>
        ) : null}
        {state === 'ready' && sceneReady ? (
          <div
            className="pointer-events-none absolute left-3 top-3 max-w-[16rem] rounded bg-stone-950/75 px-2 py-1 text-[10px] leading-4 text-stone-300"
            title={givenPlan ? "Parts are boxes sized from what you typed, or typical for the package. Heights are typical, not measured. The order is a rule of thumb for taking parts off, not a procedure from the manufacturer." : salvageMode ? "Parts are boxes sized from each footprint's outline. Heights are typical for the package, not measured. The order is a rule of thumb for taking parts off, not a procedure from the manufacturer." : "Parts are boxes sized from each footprint's outline. Heights are typical for the package, not measured. The order is conventional, not the manufacturer's."}
          >
            Stand-in shapes · typical heights{estimateNote ? ` · ${estimateNote}` : ''}
          </div>
        ) : null}
        {!givenPlan && (
          // Always on screen, loading or not, so a slow or hung request can never leave the person unable to go back.
          <div className="absolute right-3 top-3 z-10 inline-flex overflow-hidden rounded-md border border-stone-700 bg-stone-950/80 text-[11px] font-medium" role="group" aria-label="What to watch">
            {(['build', 'salvage'] as const).map((value) => (
              <button
                key={value}
                type="button"
                data-testid={`assembly-mode-${value}`}
                aria-pressed={mode === value}
                onClick={() => {
                  if (mode === value) return;
                  // Drop the old plan and scene in the same update, so nothing is rebuilt from one mode's plan under the other's rules.
                  setPlaying(false);
                  setPlan(null);
                  setSceneReady(false);
                  setState('loading');
                  setStep(0);
                  setStats({ placed: 0, flying: 0, removed: 0 });
                  setMode(value);
                }}
                className={`px-2.5 py-1 ${mode === value ? 'bg-amber-300 text-stone-950' : 'text-stone-300 hover:bg-stone-800'}`}
              >
                {value === 'build' ? 'Put together' : 'Take apart'}
              </button>
            ))}
          </div>
        )}
      </div>

      {state === 'ready' && plan && active ? (
        <div className="shrink-0 border-t border-stone-800 bg-stone-950 px-4 py-3 text-stone-100" data-testid="assembly-panel">
          <div className="flex items-baseline justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[11px] text-stone-400" data-testid="assembly-counter">Step {step + 1} of {plan.steps.length}</div>
              <div className="flex items-center gap-2 text-sm font-semibold">
                {salvageMode && active.verdict ? (
                  <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${VERDICT_CHIP[active.verdict] ?? ''}`} data-testid="assembly-verdict" data-verdict={active.verdict}>
                    {active.verdict_label || VERDICT_LABELS[active.verdict] || active.verdict}
                  </span>
                ) : null}
                <span className="truncate" data-testid="assembly-title">{active.title}</span>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <button
                type="button"
                onClick={() => { setPlaying(false); setStep(0); }}
                aria-label="Start again"
                title="Start again"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-stone-300 hover:bg-stone-800"
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => { setPlaying(false); go(step - 1); }}
                disabled={step === 0}
                aria-label="Previous step"
                data-testid="assembly-prev"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-stone-200 hover:bg-stone-800 disabled:opacity-30"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => { if (!playing && step >= last) setStep(0); setPlaying((value) => !value); }}
                aria-label={playing ? 'Pause' : salvageMode ? 'Play the take-apart' : 'Play the build'}
                aria-pressed={playing}
                data-testid="assembly-play"
                className="inline-flex h-8 items-center gap-1.5 rounded-md bg-amber-300 px-3 text-xs font-semibold text-stone-950 hover:bg-amber-200"
              >
                {playing ? <Pause className="h-3.5 w-3.5" aria-hidden="true" /> : <Play className="h-3.5 w-3.5" aria-hidden="true" />}
                {playing ? 'Pause' : 'Play'}
              </button>
              <button
                type="button"
                onClick={() => { setPlaying(false); go(step + 1); }}
                disabled={step >= last}
                aria-label="Next step"
                data-testid="assembly-next"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-stone-200 hover:bg-stone-800 disabled:opacity-30"
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>
          <p className="mt-1.5 text-xs leading-5 text-stone-300" data-testid="assembly-instruction">
            {active.turn_board_over ? <strong className="text-amber-300">Turn the board over. </strong> : null}
            {active.instruction}
          </p>
          {plan.not_fitted.length ? (
            <p className="mt-1.5 text-[11px] leading-4 text-amber-200/90" data-testid="assembly-not-fitted">
              Not fitted on this board (the design marks {plan.not_fitted.length === 1 ? 'it' : 'them'} do-not-populate): {plan.not_fitted.join(', ')}
            </p>
          ) : null}
          {active.checks.length ? (
            <ul className="mt-2 space-y-0.5 text-[11px] leading-4 text-stone-400" data-testid="assembly-checks">
              {active.checks.map((check, index) => (
                <li key={`${check.from}-${check.to}-${index}`}>
                  <span className="text-stone-500">Try:</span> {checkText(check)} — {check.expect}
                </li>
              ))}
            </ul>
          ) : null}
          <input
            type="range"
            min={0}
            max={last}
            value={step}
            onChange={(event) => { setPlaying(false); go(Number(event.target.value)); }}
            aria-label={salvageMode ? 'Take-apart step' : 'Build step'}
            data-testid="assembly-slider"
            className="mt-2.5 h-1 w-full cursor-pointer accent-amber-300"
          />
          {salvageMode && plan.summary ? (
            <p className="mt-2 text-[11px] leading-4 text-stone-300" data-testid="salvage-summary">
              {(['keep', 'test_first', 'identify', 'optional', 'skip'] as const).map((v) => `${plan.summary?.counts[v] ?? 0} ${VERDICT_LABELS[v].toLowerCase()}`).join(' · ')}
            </p>
          ) : null}
          {salvageMode && plan.limits?.length ? (
            <ul className="mt-1 list-disc pl-4 text-[10px] leading-4 text-stone-400" data-testid="salvage-limits">
              {plan.limits.map((limit) => <li key={limit}>{limit}</li>)}
            </ul>
          ) : null}
          <p className="mt-1.5 text-[10px] leading-4 text-stone-500">{plan.authority}</p>
        </div>
      ) : null}
    </div>
  );
}
