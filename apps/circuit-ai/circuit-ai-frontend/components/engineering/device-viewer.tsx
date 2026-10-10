'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, LoaderCircle, Pause, Play, RotateCcw } from 'lucide-react';
import type * as ThreeNS from 'three';
import type { OrbitControls as OrbitControlsType } from 'three/examples/jsm/controls/OrbitControls.js';

export type Point = { x: number; y: number; z: number };
type Housing = { x: number; z: number; y0: number; y1: number; size_mm: number };
type WireEnd = { module: string; pin_id: string; pin: string; label: string; point: Point; housing: Housing; exit: Point };
export type DeviceWire = {
  id: string;
  from: WireEnd;
  to: WireEnd;
  color: string;
  straight_mm: number;
  curve_mm: number;
  stock_length_mm: number | null;
  bezier: Point[];
};
type DevicePin = { id: string; name: string; roles: string[]; point: Point; label: string };
export type DeviceModule = {
  id: string;
  module: string;
  name: string;
  kind: string;
  pcb_mm: { x: number; y: number; z: number };
  above_board_mm: number;
  below_board_mm: number;
  turned: boolean;
  base_y: number;
  box: { x0: number; x1: number; z0: number; z1: number };
  overhang_mm: { antenna_end?: number };
  pins: DevicePin[];
  pin_order_varies: boolean;
  pin_order: string | null;
};
export type DeviceCheck = { kind: string; check: string; from: string; to: string; expect: string };
export type DeviceStep = {
  step_id: string;
  order: number;
  kind: string;
  title: string;
  instruction: string;
  checks: DeviceCheck[];
  wire?: string;
  parts?: string[];
  motion?: string;
  color?: string;
};
export type DeviceFinding = { severity: 'error' | 'warning' | 'info'; rule: string; message: string; basis: string; wire: string | null };
export type DevicePlan = {
  authority: string;
  name: string;
  modules: DeviceModule[];
  wires: DeviceWire[];
  case: {
    wall_mm: number;
    inner_mm: { x: number; y: number; z: number };
    outer_mm: { x: number; y: number; z: number };
    floor_top_y: number;
    lid_underside_y: number;
    usb_cutout: { wall: string; z: number; y: number; width_mm: number; height_mm: number; basis: string } | null;
    window: { x: number; z: number; width_mm: number; depth_mm: number; basis: string } | null;
    basis: string;
  };
  findings: DeviceFinding[];
  steps: DeviceStep[];
  shopping: { item: string; quantity: number; note: string | null }[];
  counts: { modules: number; wires: number; steps: number; errors: number; warnings: number };
};

type Stats = { moving: boolean; wires: number; lid: string; mcu: string; display: string; usb: string; lag: number };
type Label = { id: string; text: string; point: Point; part: 'mcu' | 'display' | 'lid' | 'case' | null; tone: 'part' | 'pin' };
type SceneApi = { goTo: (index: number, instant: boolean) => void };

const WIRE_COLORS: Record<string, string> = {
  red: '#e5484d', black: '#23252b', yellow: '#f5c542', green: '#3fb950', blue: '#4c8dff', white: '#e8eaed', orange: '#f08c3a',
};
const AWAY = { mcu: 30, display: 42, lid: 66 } as const;
const LID_HOVER = 18;
const EASE = 6.5;

const kindOf = (step: DeviceStep) => step.kind;

/** What each step asks of each part. The scene eases toward this, so jumping around the steps is always smooth. */
function targetsFor(plan: DevicePlan, index: number) {
  const done = plan.steps.slice(0, index + 1);
  const placed = done.some((s) => kindOf(s) === 'place' && s.parts?.some((id) => plan.modules.find((m) => m.id === id)?.kind === 'mcu_board'));
  const wired = done.filter((s) => kindOf(s) === 'wire' && s.wire).map((s) => s.wire as string);
  const displayFitted = done.some((s) => kindOf(s) === 'place' && s.parts?.some((id) => plan.modules.find((m) => m.id === id)?.kind === 'display'));
  const closed = done.some((s) => kindOf(s) === 'close');
  const powered = done.some((s) => kindOf(s) === 'power');
  const displayHome = placed && (wired.length > 0 || displayFitted || done.some((s) => kindOf(s) === 'check'));
  return {
    mcu: placed ? 0 : AWAY.mcu,
    display: displayHome ? 0 : AWAY.display,
    lid: closed ? 0 : displayFitted ? LID_HOVER : AWAY.lid,
    usb: powered ? 0 : -46,
    wires: new Set(wired),
  };
}

function labelsFor(plan: DevicePlan, index: number): Label[] {
  const step = plan.steps[index];
  if (!step) return [];
  const mcu = plan.modules.find((m) => m.kind === 'mcu_board');
  const display = plan.modules.find((m) => m.kind === 'display');
  const labels: Label[] = [];
  const short = (name: string) => name.split(/ \(|, /)[0];
  const centre = (m: DeviceModule, up: number): Point => ({ x: (m.box.x0 + m.box.x1) / 2, y: m.base_y + up, z: (m.box.z0 + m.box.z1) / 2 });
  if (step.kind === 'gather' || step.kind === 'measure') {
    if (mcu) labels.push({ id: 'mcu', text: short(mcu.name), point: centre(mcu, mcu.pcb_mm.z + mcu.above_board_mm + 4), part: 'mcu', tone: 'part' });
    if (display) labels.push({ id: 'display', text: short(display.name), point: centre(display, display.pcb_mm.z + display.above_board_mm + 4), part: 'display', tone: 'part' });
    labels.push({ id: 'lid', text: 'Case lid', point: { x: 0, y: plan.case.lid_underside_y + plan.case.wall_mm + 4, z: 0 }, part: 'lid', tone: 'part' });
    labels.push({ id: 'case', text: 'Case base', point: { x: 0, y: 0, z: plan.case.outer_mm.z / 2 + 4 }, part: 'case', tone: 'part' });
  }
  if (step.kind === 'place' && step.motion === 'drop' && mcu && step.parts?.includes(mcu.id)) {
    const usb = plan.case.usb_cutout;
    if (usb) labels.push({ id: 'usb', text: 'USB end', point: { x: -plan.case.outer_mm.x / 2 - 2, y: usb.y + 5, z: usb.z }, part: null, tone: 'part' });
    labels.push({ id: 'antenna', text: 'Antenna end: keep clear', point: { x: mcu.box.x1 + (mcu.overhang_mm.antenna_end ?? 0), y: mcu.base_y + mcu.pcb_mm.z + 6, z: (mcu.box.z0 + mcu.box.z1) / 2 }, part: 'mcu', tone: 'part' });
  }
  if (step.kind === 'wire' && step.wire) {
    const wire = plan.wires.find((w) => w.id === step.wire);
    if (wire) {
      for (const end of [wire.from, wire.to]) {
        const owner = plan.modules.find((m) => m.id === end.module);
        const text = owner?.kind === 'mcu_board' ? `${end.pin} · ${end.pin_id}` : end.pin;
        labels.push({ id: `${wire.id}-${end.module}`, text: `${end.module}: ${text}`, point: { x: end.exit.x, y: end.exit.y + (owner?.kind === 'mcu_board' ? 4 : -4), z: end.exit.z }, part: owner?.kind === 'display' ? 'display' : 'mcu', tone: 'pin' });
      }
    }
  }
  if (step.kind === 'check' || step.kind === 'power') {
    if (mcu) {
      for (const pin of mcu.pins) if (pin.name === '3V3' || (pin.roles.includes('ground') && plan.wires.some((w) => w.to.pin_id === pin.id))) labels.push({ id: pin.id, text: `${pin.name} · ${pin.id}`, point: { x: pin.point.x, y: pin.point.y + 4, z: pin.point.z }, part: 'mcu', tone: 'pin' });
    }
  }
  return labels;
}

/**
 * A whole device going together: parts hover apart, the board drops into the case, each wire grows from pin to pin, the display
 * and lid come down, and USB plugs in. Every part is a stand-in shape sized from the plan; the case is a proposal that has not
 * been printed. It is a view of a plan and carries no authority.
 */
export function DeviceViewer({ plan }: { plan: DevicePlan }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SceneApi | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState('');
  const [stats, setStats] = useState<Stats>({ moving: false, wires: 0, lid: 'open', mcu: 'away', display: 'away', usb: 'out', lag: 0 });
  const last = plan.steps.length - 1;

  useEffect(() => {
    setStep(0);
    setPlaying(false);
    setReady(false);
    setFailed('');
  }, [plan]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const labelHost = labelsRef.current;
    let disposed = false;
    let frame = 0;
    let observer: ResizeObserver | null = null;
    let controls: OrbitControlsType | null = null;
    let renderer: ThreeNS.WebGLRenderer | null = null;
    let scene: ThreeNS.Scene | null = null;
    const labelNodes = new Map<string, HTMLDivElement>();
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
        if (disposed) return;
        const reduced = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const world = new THREE.Scene();
        scene = world;
        world.background = new THREE.Color('#0b0d12');
        const camera = new THREE.PerspectiveCamera(36, 1, 0.5, 5000);
        const gl = new THREE.WebGLRenderer({ antialias: true });
        renderer = gl;
        gl.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        host.appendChild(gl.domElement);
        gl.domElement.style.display = 'block';
        world.add(new THREE.HemisphereLight('#ffffff', '#1c2230', 1.6));
        const key = new THREE.DirectionalLight('#ffffff', 2.4);
        key.position.set(80, 160, 110);
        world.add(key);

        const mat = (color: string, extra: Partial<ThreeNS.MeshStandardMaterialParameters> = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.1, ...extra });
        const glass = (color: string, opacity: number) => new THREE.MeshStandardMaterial({ color, roughness: 0.3, metalness: 0.0, transparent: true, opacity, depthWrite: false });
        /** A box between bounds, as a mesh at the right place. */
        const slab = (parent: ThreeNS.Object3D, x0: number, x1: number, y0: number, y1: number, z0: number, z1: number, material: ThreeNS.Material, edges = false) => {
          const mesh = new THREE.Mesh(new THREE.BoxGeometry(Math.max(x1 - x0, 0.01), Math.max(y1 - y0, 0.01), Math.max(z1 - z0, 0.01)), material);
          mesh.position.set((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
          parent.add(mesh);
          if (edges) {
            const lines = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), new THREE.LineBasicMaterial({ color: '#7f95ad', transparent: true, opacity: 0.55 }));
            lines.position.copy(mesh.position);
            parent.add(lines);
          }
          return mesh;
        };

        const c = plan.case;
        const ox = c.outer_mm.x / 2;
        const oz = c.outer_mm.z / 2;
        const wall = c.wall_mm;
        const top = c.lid_underside_y;

        // --- the case: base and lid, drawn see-through so the inside can be watched ---
        const base = new THREE.Group();
        const lid = new THREE.Group();
        const baseMaterial = glass('#a9bdd3', 0.2);
        slab(base, -ox, ox, 0, wall, -oz, oz, baseMaterial, true);
        slab(base, -ox, ox, wall, top, oz - wall, oz, baseMaterial, true);
        slab(base, -ox, ox, wall, top, -oz, -oz + wall, baseMaterial, true);
        slab(base, ox - wall, ox, wall, top, -oz + wall, oz - wall, baseMaterial, true);
        const cut = c.usb_cutout;
        if (cut) {
          const x1 = -ox + wall;
          const half = cut.width_mm / 2;
          const low = cut.y - cut.height_mm / 2;
          const high = cut.y + cut.height_mm / 2;
          slab(base, -ox, x1, wall, top, -oz + wall, cut.z - half, baseMaterial, true);
          slab(base, -ox, x1, wall, top, cut.z + half, oz - wall, baseMaterial, true);
          slab(base, -ox, x1, wall, low, cut.z - half, cut.z + half, baseMaterial, true);
          slab(base, -ox, x1, high, top, cut.z - half, cut.z + half, baseMaterial, true);
        } else {
          slab(base, -ox, -ox + wall, wall, top, -oz + wall, oz - wall, baseMaterial, true);
        }
        const lidMaterial = glass('#c3d3e6', 0.34);
        const win = c.window;
        if (win) {
          const wx0 = win.x - win.width_mm / 2;
          const wx1 = win.x + win.width_mm / 2;
          const wz0 = win.z - win.depth_mm / 2;
          const wz1 = win.z + win.depth_mm / 2;
          slab(lid, -ox, wx0, top, top + wall, -oz, oz, lidMaterial, true);
          slab(lid, wx1, ox, top, top + wall, -oz, oz, lidMaterial, true);
          slab(lid, wx0, wx1, top, top + wall, -oz, wz0, lidMaterial, true);
          slab(lid, wx0, wx1, top, top + wall, wz1, oz, lidMaterial, true);
        } else {
          slab(lid, -ox, ox, top, top + wall, -oz, oz, lidMaterial, true);
        }
        world.add(base, lid);

        // --- the modules ---
        const mcuGroup = new THREE.Group();
        const displayGroup = new THREE.Group();
        world.add(mcuGroup, displayGroup);
        const mcu = plan.modules.find((m) => m.kind === 'mcu_board');
        const display = plan.modules.find((m) => m.kind === 'display');
        if (mcu) {
          const { x0, x1, z0, z1 } = mcu.box;
          const y0 = mcu.base_y;
          const y1 = y0 + mcu.pcb_mm.z;
          slab(mcuGroup, x0, x1, y0, y1, z0, z1, mat('#101a2c'));
          const antenna = mcu.overhang_mm.antenna_end ?? 0;
          const zc = (z0 + z1) / 2;
          // The module: a metal can over most of it and a bare antenna strip that sticks out past the board.
          slab(mcuGroup, x1 - 19.5, x1 - 1.0, y1, y1 + mcu.above_board_mm, zc - 9, zc + 9, mat('#c9ced6', { metalness: 0.8, roughness: 0.35 }));
          slab(mcuGroup, x1 - 1.0, x1 + antenna, y1, y1 + 0.8, zc - 9, zc + 9, mat('#0f3b2e'));
          const gold = mat('#d6b24a', { metalness: 0.8, roughness: 0.35 });
          const plastic = mat('#16181d');
          const rows = new Map<number, { x0: number; x1: number; z: number }>();
          for (const pin of mcu.pins) {
            const row = rows.get(pin.point.z) ?? { x0: pin.point.x, x1: pin.point.x, z: pin.point.z };
            row.x0 = Math.min(row.x0, pin.point.x);
            row.x1 = Math.max(row.x1, pin.point.x);
            rows.set(pin.point.z, row);
            slab(mcuGroup, pin.point.x - 0.32, pin.point.x + 0.32, y0 - mcu.below_board_mm, pin.point.y, pin.point.z - 0.32, pin.point.z + 0.32, gold);
          }
          rows.forEach((row) => slab(mcuGroup, row.x0 - 1.27, row.x1 + 1.27, y0 - 2.5, y0, row.z - 1.27, row.z + 1.27, plastic));
          const usb = c.usb_cutout;
          if (usb) slab(mcuGroup, x0 - 0.9, x0 + 5.5, y1, y1 + 2.6, usb.z - 4.25, usb.z + 4.25, mat('#b8bec7', { metalness: 0.85, roughness: 0.3 }));
        }
        if (display) {
          const { x0, x1, z0, z1 } = display.box;
          const y0 = display.base_y;
          const y1 = y0 + display.pcb_mm.z;
          slab(displayGroup, x0, x1, y0, y1, z0, z1, mat('#143d6b'));
          const win2 = c.window;
          if (win2) {
            slab(displayGroup, win2.x - (win2.width_mm - 3) / 2 - 2, win2.x + (win2.width_mm - 3) / 2 + 2, y1, y1 + display.above_board_mm, win2.z - (win2.depth_mm - 3) / 2 - 1.5, win2.z + (win2.depth_mm - 3) / 2 + 1.5, mat('#070a10'));
            slab(displayGroup, win2.x - (win2.width_mm - 3) / 2, win2.x + (win2.width_mm - 3) / 2, y1 + display.above_board_mm, y1 + display.above_board_mm + 0.05, win2.z - (win2.depth_mm - 3) / 2, win2.z + (win2.depth_mm - 3) / 2, mat('#02040a', { roughness: 0.15 }));
          }
          const goldDisplay = mat('#d6b24a', { metalness: 0.8, roughness: 0.35 });
          for (const pin of display.pins) slab(displayGroup, pin.point.x - 0.32, pin.point.x + 0.32, y0 - 6, y0, pin.point.z - 0.32, pin.point.z + 0.32, goldDisplay);
        }

        // --- wires: a tube that grows from end to end, with a female housing on each pin. The housings ride with their module and
        // the tube is rebuilt from where the two modules are now, so a wire stays attached at both ends while a part moves. ---
        type Part = 'mcu' | 'display';
        type WireEntry = {
          id: string; mesh: ThreeNS.Mesh; total: number; housings: ThreeNS.Mesh[]; progress: number; target: number; rings: ThreeNS.Mesh[];
          ends: [Part, Part]; builtKey: string; path: Point[]; exits: { up: boolean; height: number }[];
        };
        const wires = new Map<string, WireEntry>();
        const housingMaterial = mat('#15161a');
        const partOf = (moduleId: string): Part => (plan.modules.find((m) => m.id === moduleId)?.kind === 'display' ? 'display' : 'mcu');
        const groupOf = (part: Part) => (part === 'display' ? displayGroup : mcuGroup);
        for (const wire of plan.wires) {
          const ends: [Part, Part] = [partOf(wire.from.module), partOf(wire.to.module)];
          const mesh = new THREE.Mesh(new THREE.BufferGeometry(), mat(WIRE_COLORS[wire.color] ?? '#e8eaed', { roughness: 0.45 }));
          mesh.visible = false;
          world.add(mesh);
          const housings = [wire.from, wire.to].map((end, i) => {
            const h = slab(groupOf(ends[i]), end.housing.x - 1.27, end.housing.x + 1.27, end.housing.y0, end.housing.y1, end.housing.z - 1.27, end.housing.z + 1.27, housingMaterial);
            h.visible = false;
            return h;
          });
          const rings = [wire.from, wire.to].map((end, i) => {
            const ring = new THREE.Mesh(new THREE.SphereGeometry(1.5, 16, 12), new THREE.MeshBasicMaterial({ color: '#ffcf5a', transparent: true, opacity: 0.85 }));
            ring.position.set(end.point.x, end.point.y, end.point.z);
            ring.visible = false;
            groupOf(ends[i]).add(ring);
            return ring;
          });
          const exits = [wire.from, wire.to].map((end) => ({ up: end.exit.y > end.point.y, height: end.housing.y1 - end.housing.y0 }));
          wires.set(wire.id, { id: wire.id, mesh, total: 0, housings, progress: 0, target: 0, rings, ends, builtKey: '', path: wire.bezier, exits });
        }

        // --- the USB cable ---
        const cable = new THREE.Group();
        world.add(cable);
        if (cut && mcu) {
          const reach = -ox + wall;   // the wall's inner face
          slab(cable, reach - 16, reach + 4, cut.y - 3, cut.y + 3, cut.z - 6, cut.z + 6, mat('#1c1f26'));
          const lead = new THREE.Mesh(new THREE.CylinderGeometry(1.8, 1.8, 60, 16), mat('#262a33'));
          lead.rotation.z = Math.PI / 2;
          lead.position.set(reach - 16 - 30, cut.y, cut.z);
          cable.add(lead);
        }

        // --- camera ---
        // Frame the whole stack, including the parts hovering above the case at the start.
        const span = Math.max(c.outer_mm.x, c.outer_mm.z, 40);
        const stackHeight = c.outer_mm.y + AWAY.lid + 8;
        const distance = Math.max(stackHeight * 1.2, span * 1.7);
        const orbit = new OrbitControls(camera, gl.domElement);
        controls = orbit;
        orbit.enableDamping = true;
        const centreY = stackHeight * 0.48;
        orbit.target.set(0, centreY, 0);
        camera.position.set(distance * 0.55, centreY + distance * 0.42, distance * 0.82);
        camera.near = span / 100;
        camera.far = span * 40;
        camera.updateProjectionMatrix();
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

        // --- poses: each part eases toward what the current step asks of it ---
        const pose = { mcu: AWAY.mcu as number, display: AWAY.display as number, lid: AWAY.lid as number, usb: -46 };
        let want = targetsFor(plan, 0);
        let current = 0;
        // The camera follows the height of whatever is on screen, until the person takes hold of it themselves.
        let userMoved = false;
        orbit.addEventListener('start', () => { userMoved = true; });
        const caseTop = c.outer_mm.y;
        const lidDepth = wall;
        let lastSignature = '';
        let labels: Label[] = [];
        const partOffset = (part: Label['part']) => (part === 'mcu' ? pose.mcu : part === 'display' ? pose.display : part === 'lid' ? pose.lid : 0);

        const syncLabels = () => {
          labels = labelsFor(plan, current);
          const ids = new Set(labels.map((l) => l.id));
          labelNodes.forEach((node, id) => { if (!ids.has(id)) { node.remove(); labelNodes.delete(id); } });
          if (!labelHost) return;
          for (const label of labels) {
            let node = labelNodes.get(label.id);
            if (!node) {
              node = document.createElement('div');
              node.setAttribute('data-testid', 'device-label');
              labelHost.appendChild(node);
              labelNodes.set(label.id, node);
            }
            node.textContent = label.text;
            node.className = `pointer-events-none absolute left-0 top-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-semibold shadow ${label.tone === 'pin' ? 'bg-amber-300 text-stone-950' : 'bg-stone-100/90 text-stone-900'}`;
          }
        };

        const goTo = (index: number, instant: boolean) => {
          current = Math.min(Math.max(index, 0), plan.steps.length - 1);
          want = targetsFor(plan, current);
          userMoved = false;
          const active = plan.steps[current];
          wires.forEach((entry) => {
            entry.target = want.wires.has(entry.id) ? 1 : 0;
            const isCurrent = active.kind === 'wire' && active.wire === entry.id;
            entry.rings.forEach((ring) => { ring.visible = isCurrent; });
          });
          if (instant || reduced) {
            pose.mcu = want.mcu; pose.display = want.display; pose.lid = want.lid; pose.usb = want.usb;
            wires.forEach((entry) => { entry.progress = entry.target; });
          }
          syncLabels();
        };

        const project = new THREE.Vector3();
        let previous = performance.now();
        const tick = () => {
          const now = performance.now();
          const dt = Math.min((now - previous) / 1000, 0.1);
          previous = now;
          const k = 1 - Math.exp(-EASE * dt);
          let moving = false;
          const ease = (value: number, target: number) => {
            const next = value + (target - value) * k;
            if (Math.abs(target - next) < 0.05) return target;
            moving = true;
            return next;
          };
          pose.mcu = ease(pose.mcu, want.mcu);
          pose.display = ease(pose.display, want.display);
          pose.lid = ease(pose.lid, want.lid);
          pose.usb = ease(pose.usb, want.usb);
          mcuGroup.position.y = pose.mcu;
          displayGroup.position.y = pose.display;
          lid.position.y = pose.lid;
          cable.position.x = pose.usb;
          cable.visible = pose.usb > -45.9;
          let finished = 0;
          let lag = 0;
          mcuGroup.updateMatrixWorld(true);
          displayGroup.updateMatrixWorld(true);
          const pulse = 1 + Math.sin(now / 160) * 0.18;
          const offsetOf = (part: Part) => (part === 'mcu' ? pose.mcu : pose.display);
          wires.forEach((entry) => {
            const next = entry.progress + (entry.target - entry.progress) * k * 0.8;
            entry.progress = Math.abs(entry.target - next) < 0.004 ? entry.target : next;
            if (entry.progress !== entry.target) moving = true;
            if (entry.progress >= 0.999) finished += 1;
            const shown = entry.progress > 0.002;
            entry.mesh.visible = shown;
            entry.housings.forEach((h) => { h.visible = shown; });
            if (shown) {
              // Rebuild the tube only when one of its two modules has moved since it was last drawn.
              const key = `${offsetOf(entry.ends[0]).toFixed(2)}|${offsetOf(entry.ends[1]).toFixed(2)}`;
              if (key !== entry.builtKey) {
                const shift = [offsetOf(entry.ends[0]), offsetOf(entry.ends[0]), offsetOf(entry.ends[1]), offsetOf(entry.ends[1])];
                const p = entry.path.map((point, i) => new THREE.Vector3(point.x, point.y + shift[i], point.z));
                const geometry = new THREE.TubeGeometry(new THREE.CubicBezierCurve3(p[0], p[1], p[2], p[3]), 48, 0.9, 8, false);
                entry.mesh.geometry.dispose();
                entry.mesh.geometry = geometry;
                entry.total = geometry.index ? geometry.index.count : 0;
                entry.builtKey = key;
              }
              entry.mesh.geometry.setDrawRange(0, Math.floor((entry.total * entry.progress) / 6) * 6);
              // How far is each end of the wire from where its connector housing really is right now? It is 0 when it follows.
              const position = entry.mesh.geometry.getAttribute('position');
              const ring = 9;
              const ringCentre = (first: number) => {
                const centre = new THREE.Vector3();
                for (let i = first; i < first + ring; i += 1) centre.add(new THREE.Vector3(position.getX(i), position.getY(i), position.getZ(i)));
                return centre.multiplyScalar(1 / ring);
              };
              [ringCentre(0), ringCentre(48 * ring)].forEach((end, i) => {
                const housing = entry.housings[i].getWorldPosition(new THREE.Vector3());
                housing.y += (entry.exits[i].up ? 1 : -1) * (entry.exits[i].height / 2);
                lag = Math.max(lag, end.distanceTo(housing));
              });
            }
            entry.rings.forEach((ring) => ring.scale.setScalar(pulse));
          });
          const lagRounded = Math.round(lag * 10) / 10;
          const signature = `${moving}|${finished}|${want.lid}|${want.mcu}|${want.display}|${want.usb}|${lagRounded}`;
          if (signature !== lastSignature) {
            lastSignature = signature;
            setStats({
              moving, wires: finished,
              lid: want.lid === 0 ? 'closed' : want.lid === LID_HOVER ? 'hover' : 'open',
              mcu: want.mcu === 0 ? 'home' : 'away', display: want.display === 0 ? 'home' : 'away', usb: want.usb === 0 ? 'in' : 'out', lag: lagRounded,
            });
          }
          if (labelHost && labelNodes.size) {
            const rect = host.getBoundingClientRect();
            for (const label of labels) {
              const node = labelNodes.get(label.id);
              if (!node) continue;
              project.set(label.point.x, label.point.y + partOffset(label.part), label.point.z).project(camera);
              const shown = project.z < 1;
              node.style.display = shown ? 'block' : 'none';
              node.style.transform = `translate(${((project.x + 1) / 2) * rect.width + 6}px, ${((1 - project.y) / 2) * rect.height - 8}px)`;
            }
          }
          if (!userMoved) {
            const top = Math.max(caseTop, c.lid_underside_y + lidDepth + pose.lid, (display ? display.base_y + display.pcb_mm.z + display.above_board_mm + pose.display : 0), (mcu ? mcu.base_y + mcu.pcb_mm.z + mcu.above_board_mm + pose.mcu : 0));
            const lift = (top * 0.42 - orbit.target.y) * k * 0.6;
            if (Math.abs(lift) > 0.002) { orbit.target.y += lift; camera.position.y += lift; }
          }
          orbit.update();
          gl.render(world, camera);
          frame = window.requestAnimationFrame(tick);
        };
        tick();

        sceneRef.current = { goTo };
        if (disposed) {
          cleanup();
          return;
        }
        setReady(true);
      } catch (caught) {
        cleanup();
        if (!disposed) setFailed(caught instanceof Error ? caught.message : 'The 3D view could not start.');
      }
    })();

    return () => {
      disposed = true;
      cleanup();
    };
  }, [plan]);

  const first = useRef(true);
  useEffect(() => {
    if (!ready) { first.current = true; return; }
    sceneRef.current?.goTo(step, first.current);
    first.current = false;
  }, [step, ready]);

  useEffect(() => {
    if (!playing || !ready || stats.moving) return;
    if (step >= last) { setPlaying(false); return; }
    const timer = window.setTimeout(() => setStep((value) => Math.min(value + 1, last)), 1100);
    return () => window.clearTimeout(timer);
  }, [playing, ready, stats.moving, step, last]);

  const go = useCallback((next: number) => setStep(Math.min(Math.max(next, 0), last)), [last]);
  const active = plan.steps[step];
  const swatch = active?.color ? WIRE_COLORS[active.color] : null;
  const problems = useMemo(() => plan.findings.filter((f) => f.severity === 'error').length, [plan]);

  return (
    <div
      className="relative flex h-full min-h-[520px] w-full flex-col bg-[#0b0d12] outline-none"
      data-testid="device-viewer"
      data-ready={ready ? '1' : '0'}
      data-step={step}
      data-step-count={plan.steps.length}
      data-moving={stats.moving ? '1' : '0'}
      data-wires={stats.wires}
      data-lid={stats.lid}
      data-mcu={stats.mcu}
      data-display={stats.display}
      data-display-vcc-pad={JSON.stringify(plan.modules.find((module) => module.kind === 'display')?.pins.find((pin) => pin.name === 'VCC')?.point)}
      data-usb={stats.usb}
      data-wire-lag={stats.lag}
      data-playing={playing ? '1' : '0'}
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.target instanceof HTMLInputElement) return;
        if (event.key === 'ArrowRight') { event.preventDefault(); go(step + 1); }
        else if (event.key === 'ArrowLeft') { event.preventDefault(); go(step - 1); }
        else if (event.key === ' ') { event.preventDefault(); setPlaying((value) => !value); }
      }}
    >
      <div className="relative min-h-[340px] flex-1">
        <div ref={hostRef} className="absolute inset-0" role="img" aria-label={`Animated assembly of ${plan.name}. Drag to orbit, scroll to zoom.`} />
        <div ref={labelsRef} className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true" />
        {!ready && !failed ? <div className="absolute inset-0 flex items-center justify-center text-stone-400"><LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" /></div> : null}
        {failed ? <div className="absolute inset-0 flex items-center justify-center p-8 text-center text-xs text-stone-400" role="alert">The 3D view failed: {failed}</div> : null}
        {ready ? (
          <div className="pointer-events-none absolute left-3 top-3 max-w-[18rem] rounded bg-stone-950/75 px-2 py-1 text-[10px] leading-4 text-stone-300" title={plan.case.basis}>
            Stand-in shapes · the case is a proposal, not yet printed
          </div>
        ) : null}
        {ready && problems > 0 ? (
          <div className="pointer-events-none absolute right-3 top-3 rounded bg-red-950/85 px-2 py-1 text-[11px] font-medium text-red-200" data-testid="device-problems">
            {problems} wiring {problems === 1 ? 'problem' : 'problems'}: see the list
          </div>
        ) : null}
      </div>

      {active ? (
        <div className="shrink-0 border-t border-stone-800 bg-stone-950 px-4 py-3 text-stone-100" data-testid="device-panel">
          <div className="flex items-baseline justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[11px] text-stone-400" data-testid="device-counter">Step {step + 1} of {plan.steps.length}</div>
              <div className="flex items-center gap-2 truncate text-sm font-semibold" data-testid="device-title">
                {swatch ? <span className="inline-block h-2.5 w-5 shrink-0 rounded-sm border border-stone-600" style={{ background: swatch }} aria-label={`${active.color} wire`} /> : null}
                <span className="truncate">{active.title}</span>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <button type="button" onClick={() => { setPlaying(false); setStep(0); }} aria-label="Start again" title="Start again" className="inline-flex h-8 w-8 items-center justify-center rounded-md text-stone-300 hover:bg-stone-800">
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => { setPlaying(false); go(step - 1); }} disabled={step === 0} aria-label="Previous step" data-testid="device-prev" className="inline-flex h-8 w-8 items-center justify-center rounded-md text-stone-200 hover:bg-stone-800 disabled:opacity-30">
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => { if (!playing && step >= last) setStep(0); setPlaying((value) => !value); }} aria-label={playing ? 'Pause' : 'Play the build'} aria-pressed={playing} data-testid="device-play" className="inline-flex h-8 items-center gap-1.5 rounded-md bg-amber-300 px-3 text-xs font-semibold text-stone-950 hover:bg-amber-200">
                {playing ? <Pause className="h-3.5 w-3.5" aria-hidden="true" /> : <Play className="h-3.5 w-3.5" aria-hidden="true" />}
                {playing ? 'Pause' : 'Play'}
              </button>
              <button type="button" onClick={() => { setPlaying(false); go(step + 1); }} disabled={step >= last} aria-label="Next step" data-testid="device-next" className="inline-flex h-8 w-8 items-center justify-center rounded-md text-stone-200 hover:bg-stone-800 disabled:opacity-30">
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>
          <p className="mt-1.5 text-xs leading-5 text-stone-300" data-testid="device-instruction">{active.instruction}</p>
          {active.checks.length ? (
            <ul className="mt-2 space-y-0.5 text-[11px] leading-4 text-stone-400" data-testid="device-checks">
              {active.checks.map((check, index) => (
                <li key={`${check.check}-${check.from}-${index}`}>
                  <span className="text-stone-500">Try:</span> {check.check === 'measure' ? `measure ${check.from}` : check.check === 'voltage' ? `meter ${check.from} to ${check.to}` : check.check === 'i2c_scan' ? 'run an I2C scan' : check.check === 'isolation' ? `meter between ${check.from} and ${check.to}` : `beep ${check.from} to ${check.to}`} — {check.expect}
                </li>
              ))}
            </ul>
          ) : null}
          <input type="range" min={0} max={last} value={step} onChange={(event) => { setPlaying(false); go(Number(event.target.value)); }} aria-label="Build step" data-testid="device-slider" className="mt-2.5 h-1 w-full cursor-pointer accent-amber-300" />
          <p className="mt-1.5 text-[10px] leading-4 text-stone-500">{plan.authority}</p>
        </div>
      ) : null}
    </div>
  );
}
