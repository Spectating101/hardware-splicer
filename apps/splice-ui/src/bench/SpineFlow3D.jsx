import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

// Animated 3D view of the board pipeline. Layout and colours follow the 2026-11-28 design Neon (Gemini) drafted;
// every label is the engine's text as given. A step without an outcome is drawn as not recorded, never as not run.
// Constants, palette, and fixed key-based U-cell layout
const KEY_ORDER = [
  "design", "pin_coverage", "schematic", "readback", "erc", "placement",
  "freerouting", "krt", "copper",
  "finish", "drc", "track_current", "decoupling", "fab",
];
const ROUTERS = ["freerouting", "krt", "copper"];
const OUTCOME_LABEL = { clean: "clean", failed: "failed", recorded: "recorded", not_run: "not run", unknown: "not recorded" };
const C = {
  bg: 0x0f1114, padUnk: 0x181b1f, pad: 0x20242a, line: 0x2a2f36, grid: 0x1c2026,
  sel: 0xe4e7eb, hover: 0xaab2bc, pylon: 0x98a1ac, clean: 0x3ebd86,
  failed: 0xf0645c, rec: 0xc3cad3, notrun: 0x8a939e, unk: 0xe0a43e,
};
const DEG = Math.PI / 180;
const TARGET = new THREE.Vector3(0.4, 0, 0.2);
const EYE0 = new THREE.Vector3(0, 15.5, 10.5);
const V0 = EYE0.clone().sub(TARGET);
const DIST0 = V0.length();
const YAW0 = Math.atan2(V0.x, V0.z);
const PITCH0 = Math.atan2(V0.y, Math.hypot(V0.x, V0.z));
const ARC_CX = 5.5;
const LAYOUT = {
  design: { x: -5.5, z: -2.6, ry: 0, labelOff: [0, 0.28, -0.78] },
  pin_coverage: { x: -3.3, z: -2.6, ry: 0, labelOff: [0, 0.28, -0.78] },
  schematic: { x: -1.1, z: -2.6, ry: 0, labelOff: [0, 0.28, -0.78] },
  readback: { x: 1.1, z: -2.6, ry: 0, labelOff: [0, 0.28, -0.78] },
  erc: { x: 3.3, z: -2.6, ry: 0, labelOff: [0, 0.28, -0.78] },
  placement: { x: 5.5, z: -2.6, ry: 0, labelOff: [0, 0.28, -0.78] },
  freerouting: { x: ARC_CX + 2.6, z: 0, ry: -Math.PI / 2, r: 2.6, ang: 0, labelOff: [-0.85, 0.28, 0] },
  krt: { x: ARC_CX + 3.8 * Math.cos(-0.35), z: 3.8 * Math.sin(-0.35), ry: -Math.PI / 2 - 0.35, r: 3.8, ang: -0.35, labelOff: [0.9, 0.28, -0.3] },
  copper: { x: ARC_CX + 5.0 * Math.cos(0.32), z: 5.0 * Math.sin(0.32), ry: -Math.PI / 2 + 0.32, r: 5.0, ang: 0.32, labelOff: [0.95, 0.28, 0.3] },
  finish: { x: 5.5, z: 2.6, ry: Math.PI, labelOff: [0, 0.28, 0.82] },
  drc: { x: 2.75, z: 2.6, ry: Math.PI, labelOff: [0, 0.28, 0.82] },
  track_current: { x: 0, z: 2.6, ry: Math.PI, labelOff: [0, 0.28, 0.82] },
  decoupling: { x: -2.75, z: 2.6, ry: Math.PI, labelOff: [0, 0.28, 0.82] },
  fab: { x: -5.5, z: 2.6, ry: Math.PI, labelOff: [0, 0.28, 0.82] },
};

// WebGL capability check and geometry helpers
export function canUseWebGL() {
  if (typeof document === "undefined") return false;
  if (typeof navigator !== "undefined" && /jsdom/i.test(navigator.userAgent || "")) return false;
  try {
    const c = document.createElement("canvas");
    const gl = c.getContext("webgl2") || c.getContext("webgl") || c.getContext("experimental-webgl");
    if (!gl) return false;
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function sidingPoints(key, y = 0.06) {
  const { r } = LAYOUT[key];
  const pts = [new THREE.Vector3(5.5, y, -2.6)];
  if (key === "freerouting") {
    for (let i = 1; i <= 7; i++) {
      const a = -Math.PI / 2 + (Math.PI * i) / 8;
      pts.push(new THREE.Vector3(ARC_CX + r * Math.cos(a), y, r * Math.sin(a)));
    }
  } else {
    const angs = key === "krt" ? [-0.68, -0.35, 0, 0.35, 0.68] : [-0.58, -0.25, 0, 0.32, 0.58];
    pts.push(new THREE.Vector3(6.45, y, -2.6));
    for (const a of angs) pts.push(new THREE.Vector3(ARC_CX + r * Math.cos(a), y, r * Math.sin(a)));
    pts.push(new THREE.Vector3(6.45, y, 2.6));
  }
  pts.push(new THREE.Vector3(5.5, y, 2.6));
  return pts;
}

function makeHatchTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const ctx = c.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#181b1f";
    ctx.fillRect(0, 0, 64, 64);
    ctx.strokeStyle = "rgba(224, 164, 62, 0.35)";
    ctx.lineWidth = 4;
    for (let i = -64; i < 128; i += 12) {
      ctx.beginPath();
      ctx.moveTo(i, 0);
      ctx.lineTo(i + 64, 64);
      ctx.stroke();
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2, 2);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeBracketGeo(hx, hz, arm, y) {
  const v = [];
  for (const sx of [-1, 1]) {
    for (const sz of [-1, 1]) {
      v.push(sx * hx, y, sz * hz, sx * (hx - arm), y, sz * hz);
      v.push(sx * hx, y, sz * hz, sx * hx, y, sz * (hz - arm));
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
  return g;
}

function makeChevronGeo() {
  const s = new THREE.Shape();
  s.moveTo(0, 0.14);
  s.lineTo(0.14, -0.06);
  s.lineTo(0.08, -0.1);
  s.lineTo(0, 0.02);
  s.lineTo(-0.08, -0.1);
  s.lineTo(-0.14, -0.06);
  s.closePath();
  const g = new THREE.ShapeGeometry(s);
  g.rotateX(Math.PI / 2);
  return g;
}

// Component state, media query, and ordered steps
export default function SpineFlow3D({ steps = [], selectedKey, onSelect, renders, renderUrl }) {
  const rootRef = useRef(null);
  const canvasHostRef = useRef(null);
  const labelRefs = useRef({});
  const sceneRef = useRef(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const [webglFailed, setWebglFailed] = useState(() => !canUseWebGL());
  const [hoveredKey, setHoveredKey] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false
  );

  const stepMap = {};
  for (const s of steps) if (s?.key) stepMap[s.key] = s;
  const orderedSteps = KEY_ORDER.map((k) => stepMap[k]).filter(Boolean);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = (e) => setReduced(e.matches);
    setReduced(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  // Build Three.js scene once per steps change
  useEffect(() => {
    if (webglFailed) return;
    const host = canvasHostRef.current;
    if (!host) return;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    } catch {
      setWebglFailed(true);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(C.bg, 1);
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const cam = new THREE.OrthographicCamera(-9, 9, 5.25, -5.25, 0.1, 100);
    const camState = { yaw: YAW0, pitch: PITCH0, zoom: 1, w: 1, h: 1 };
    scene.add(new THREE.HemisphereLight(0xe4e7eb, 0x0f1114, 0.95));
    const l1 = new THREE.DirectionalLight(0xffffff, 0.8);
    l1.position.set(8, 16, 10);
    scene.add(l1);
    const l2 = new THREE.DirectionalLight(0x98a1ac, 0.35);
    l2.position.set(-10, 8, -8);
    scene.add(l2);

    // Floor grid (1-unit pitch at y = -0.05)
    const gv = [];
    for (let x = -16; x <= 20; x++) gv.push(x, -0.05, -12, x, -0.05, 12);
    for (let z = -12; z <= 12; z++) gv.push(-16, -0.05, z, 20, -0.05, z);
    const gridGeo = new THREE.BufferGeometry();
    gridGeo.setAttribute("position", new THREE.Float32BufferAttribute(gv, 3));
    scene.add(new THREE.LineSegments(gridGeo, new THREE.LineBasicMaterial({ color: C.grid })));

    // Centre board slab (static, top face texturable)
    const boardSideMat = new THREE.MeshStandardMaterial({ color: C.pad, roughness: 0.78, metalness: 0.15 });
    const boardTopMat = new THREE.MeshStandardMaterial({ color: C.pad, roughness: 0.78, metalness: 0.15 });
    const boardGeo = new THREE.BoxGeometry(3.5, 0.08, 2.8);
    const board = new THREE.Mesh(boardGeo, [boardSideMat, boardSideMat, boardTopMat, boardSideMat, boardSideMat, boardSideMat]);
    board.position.set(-0.3, 0.04, 0);
    scene.add(board);
    const boardEdge = new THREE.LineSegments(new THREE.EdgesGeometry(boardGeo), new THREE.LineBasicMaterial({ color: C.line }));
    boardEdge.position.copy(board.position);
    scene.add(boardEdge);

    // Shared station geometries and materials
    const padGeo = new THREE.BoxGeometry(1.4, 0.24, 1.1);
    const padEdgesGeo = new THREE.EdgesGeometry(padGeo);
    const beaconGeo = new THREE.BoxGeometry(0.1, 0.07, 0.92);
    const beaconEdgesGeo = new THREE.EdgesGeometry(beaconGeo);
    const hitGeo = new THREE.BoxGeometry(1.58, 0.55, 1.28);
    const hitMat = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false, colorWrite: false });
    const padStdMat = new THREE.MeshStandardMaterial({ color: C.pad, roughness: 0.78, metalness: 0.15 });
    const padUnkSideMat = new THREE.MeshStandardMaterial({ color: C.padUnk, roughness: 0.82, metalness: 0.1 });
    const hatchTex = makeHatchTexture();
    const padUnkTopMat = new THREE.MeshStandardMaterial({ map: hatchTex, roughness: 0.82, metalness: 0.1 });
    const pylonGeo = new THREE.BoxGeometry(0.12, 0.92, 0.12);
    const beamGeo = new THREE.BoxGeometry(0.16, 0.12, 1.48);
    const pylonMat = new THREE.MeshStandardMaterial({ color: C.pylon, roughness: 0.6, metalness: 0.25 });
    const beamMat = new THREE.MeshStandardMaterial({ color: C.line, roughness: 0.7, metalness: 0.2 });

    // Build stations by key
    const hitBoxes = [];
    const anchors = {};
    const stationMeta = {};
    for (const key of KEY_ORDER) {
      const step = stepMap[key];
      const pos = LAYOUT[key];
      if (!step || !pos) continue;
      const outcome = step.run?.outcome || "unknown";
      const g = new THREE.Group();
      g.position.set(pos.x, 0, pos.z);
      g.rotation.y = pos.ry;

      if (outcome === "not_run") {
        const em = new THREE.LineBasicMaterial({ color: C.notrun, transparent: true, opacity: 0.45 });
        const pe = new THREE.LineSegments(padEdgesGeo, em);
        pe.position.y = 0.12;
        g.add(pe);
        const be = new THREE.LineSegments(beaconEdgesGeo, em);
        be.position.set(0.62, 0.255, 0);
        g.add(be);
      } else if (outcome === "unknown") {
        const pm = new THREE.Mesh(padGeo, [padUnkSideMat, padUnkSideMat, padUnkTopMat, padUnkSideMat, padUnkSideMat, padUnkSideMat]);
        pm.position.y = 0.12;
        g.add(pm);
        const pe = new THREE.LineSegments(padEdgesGeo, new THREE.LineDashedMaterial({ color: C.unk, dashSize: 0.14, gapSize: 0.1 }));
        pe.position.y = 0.12;
        pe.computeLineDistances();
        g.add(pe);
        const be = new THREE.LineSegments(beaconEdgesGeo, new THREE.LineDashedMaterial({ color: C.unk, dashSize: 0.08, gapSize: 0.06 }));
        be.position.set(0.62, 0.255, 0);
        be.computeLineDistances();
        g.add(be);
      } else {
        const pm = new THREE.Mesh(padGeo, padStdMat);
        pm.position.y = 0.12;
        g.add(pm);
        const ec = outcome === "failed" ? C.failed : C.line;
        const pe = new THREE.LineSegments(padEdgesGeo, new THREE.LineBasicMaterial({ color: ec }));
        pe.position.y = 0.12;
        g.add(pe);
        const bc = outcome === "clean" ? C.clean : outcome === "failed" ? C.failed : C.rec;
        const bi = outcome === "recorded" ? 0.25 : 0.8;
        const bm = new THREE.Mesh(beaconGeo, new THREE.MeshStandardMaterial({ color: bc, emissive: bc, emissiveIntensity: bi, roughness: 0.4 }));
        bm.position.set(0.62, 0.255, 0);
        g.add(bm);
      }

      if (step.gate) {
        const p1 = new THREE.Mesh(pylonGeo, pylonMat);
        p1.position.set(0, 0.46, -0.66);
        const p2 = new THREE.Mesh(pylonGeo, pylonMat);
        p2.position.set(0, 0.46, 0.66);
        const bm = new THREE.Mesh(beamGeo, beamMat);
        bm.position.set(0, 0.94, 0);
        g.add(p1, p2, bm);
      }

      const hit = new THREE.Mesh(hitGeo, hitMat);
      hit.position.y = 0.24;
      hit.userData.key = key;
      g.add(hit);
      hitBoxes.push(hit);
      scene.add(g);
      anchors[key] = new THREE.Vector3(pos.x + pos.labelOff[0], pos.labelOff[1], pos.z + pos.labelOff[2]);
      stationMeta[key] = { pos, step, outcome };
    }

    // Hover rim and selection bracket
    const hoverRim = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(1.48, 0.04, 1.18)),
      new THREE.LineBasicMaterial({ color: C.hover })
    );
    hoverRim.visible = false;
    scene.add(hoverRim);
    const selectBracket = new THREE.LineSegments(makeBracketGeo(0.84, 0.68, 0.28, 0.28), new THREE.LineBasicMaterial({ color: C.sel }));
    selectBracket.visible = false;
    scene.add(selectBracket);

    // Switchyard dashed sidings and active CatmullRomCurve3 rail
    const activeRouter = [...ROUTERS].reverse().find((k) => stationMeta[k] && stationMeta[k].outcome !== "not_run") || null;
    for (const rk of ROUTERS) {
      if (rk === activeRouter) continue;
      const curve = new THREE.CatmullRomCurve3(sidingPoints(rk, 0.05), false, "catmullrom", 0.25);
      const lGeo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(36));
      const line = new THREE.Line(lGeo, new THREE.LineDashedMaterial({ color: C.line, transparent: true, opacity: 0.4, dashSize: 0.22, gapSize: 0.16 }));
      line.computeLineDistances();
      scene.add(line);
    }

    const activeSeq = KEY_ORDER.filter((k) => stationMeta[k] && stationMeta[k].outcome !== "not_run" && (!ROUTERS.includes(k) || k === activeRouter));
    const railPts = [];
    for (let i = 0; i < activeSeq.length; i++) {
      const k = activeSeq[i];
      if (k === activeRouter) {
        const sp = sidingPoints(k, 0.06);
        const hasPrev = i > 0 && activeSeq[i - 1] === "placement";
        const hasNext = i < activeSeq.length - 1 && activeSeq[i + 1] === "finish";
        const mid = sp.slice(hasPrev ? 1 : 0, hasNext ? sp.length - 1 : sp.length);
        railPts.push(...mid);
      } else {
        railPts.push(new THREE.Vector3(LAYOUT[k].x, 0.06, LAYOUT[k].z));
      }
    }

    let activeCurve = null;
    let activeStations = [];
    let failU = null;
    let carrier = null;
    let carrierMat = null;
    let pulseMesh = null;
    let pulseMat = null;
    const chevronsGroup = new THREE.Group();
    scene.add(chevronsGroup);

    if (railPts.length >= 2) {
      activeCurve = new THREE.CatmullRomCurve3(railPts, false, "catmullrom", 0.25);
      const samples = Array.from({ length: 241 }, (_, i) => activeCurve.getPointAt(i / 240));
      let minIdx = 0;
      activeStations = activeSeq.map((k) => {
        const p = LAYOUT[k];
        let best = minIdx;
        let bestD = Infinity;
        for (let i = minIdx; i < samples.length; i++) {
          const d = (samples[i].x - p.x) ** 2 + (samples[i].z - p.z) ** 2;
          if (d < bestD) { bestD = d; best = i; }
        }
        minIdx = best;
        return { key: k, u: best / 240, step: stationMeta[k].step, outcome: stationMeta[k].outcome };
      });
      const failedSt = activeStations.find((s) => s.outcome === "failed");
      failU = failedSt ? failedSt.u : null;

      const railMat = new THREE.MeshStandardMaterial({ color: C.line, roughness: 0.72, metalness: 0.2 });
      const dimRailMat = new THREE.MeshStandardMaterial({ color: C.line, roughness: 0.72, metalness: 0.2, transparent: true, opacity: 0.25 });
      if (failU !== null && failU > 0.005 && failU < 0.995) {
        const prePts = Array.from({ length: 48 }, (_, i) => activeCurve.getPointAt((failU * i) / 47));
        const postPts = Array.from({ length: 48 }, (_, i) => activeCurve.getPointAt(failU + ((1 - failU) * i) / 47));
        scene.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(prePts), 64, 0.045, 8, false), railMat));
        scene.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(postPts), 64, 0.045, 8, false), dimRailMat));
      } else if (failU === 0) {
        scene.add(new THREE.Mesh(new THREE.TubeGeometry(activeCurve, 96, 0.045, 8, false), dimRailMat));
      } else {
        scene.add(new THREE.Mesh(new THREE.TubeGeometry(activeCurve, 96, 0.045, 8, false), railMat));
      }

      // Carrier capsule, failure pulse ring, and reduced-motion chevrons
      const capGeo = new THREE.CapsuleGeometry(0.1, 0.22, 6, 12);
      capGeo.rotateX(Math.PI / 2);
      carrierMat = new THREE.MeshStandardMaterial({ color: C.clean, emissive: C.clean, emissiveIntensity: 0.75, roughness: 0.35 });
      carrier = new THREE.Mesh(capGeo, carrierMat);
      scene.add(carrier);

      pulseMat = new THREE.MeshBasicMaterial({ color: C.failed, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false });
      pulseMesh = new THREE.Mesh(new THREE.RingGeometry(0.22, 0.34, 28), pulseMat);
      pulseMesh.rotation.x = -Math.PI / 2;
      pulseMesh.visible = false;
      scene.add(pulseMesh);

      const chevGeo = makeChevronGeo();
      const maxU = failU !== null ? failU : 0.97;
      const segColor = (u) => {
        const unk = activeStations.find((s) => s.outcome === "unknown" && Math.abs(s.u - u) < 0.045);
        if (unk) return C.unk;
        const near = activeStations.reduce((a, b) => (Math.abs(b.u - u) < Math.abs(a.u - u) ? b : a), activeStations[0]);
        return near?.outcome === "recorded" ? C.rec : C.clean;
      };
      const count = Math.max(2, Math.floor(maxU * 18));
      for (let i = 1; i <= count; i++) {
        const u = (maxU * i) / (count + 1);
        const pt = activeCurve.getPointAt(u);
        const nxt = activeCurve.getPointAt(Math.min(1, u + 0.01));
        const cm = new THREE.Mesh(chevGeo, new THREE.MeshBasicMaterial({ color: segColor(u), side: THREE.DoubleSide }));
        cm.position.set(pt.x, 0.28, pt.z);
        cm.lookAt(nxt.x, 0.28, nxt.z);
        chevronsGroup.add(cm);
      }
    }

    // Camera framing, label projection, and carrier stepping
    const tmpV = new THREE.Vector3();
    const applyCamera = () => {
      const { yaw, pitch, zoom, w, h } = camState;
      const cosP = Math.cos(pitch);
      cam.position.set(TARGET.x + DIST0 * cosP * Math.sin(yaw), TARGET.y + DIST0 * Math.sin(pitch), TARGET.z + DIST0 * cosP * Math.cos(yaw));
      cam.lookAt(TARGET);
      const aspect = w / Math.max(h, 1);
      const baseW = 20.2;
      const baseH = 9.2;
      const fitH = aspect >= baseW / baseH ? baseH : baseW / aspect;
      const fitW = fitH * aspect;
      const cx = 2.5;
      cam.left = cx - fitW / 2;
      cam.right = cx + fitW / 2;
      cam.top = fitH / 2;
      cam.bottom = -fitH / 2;
      cam.zoom = zoom;
      cam.updateProjectionMatrix();
    };

    const projectLabels = () => {
      const { w, h } = camState;
      for (const key in anchors) {
        const el = labelRefs.current[key];
        if (!el) continue;
        tmpV.copy(anchors[key]).project(cam);
        const px = (tmpV.x * 0.5 + 0.5) * w;
        const py = (-tmpV.y * 0.5 + 0.5) * h;
        el.style.transform = `translate3d(${px.toFixed(1)}px,${py.toFixed(1)}px,0) translate(-50%,-50%)`;
      }
    };

    const anim = { u: 0, gateHold: 0, failHold: 0, pulseT: 1, passedGates: new Set(), raf: 0, lastT: 0, paused: false, reduced: false };
    const stepCarrier = (dt) => {
      if (!activeCurve || !carrier || !carrierMat) return;
      if (anim.failHold > 0) {
        anim.failHold -= dt;
        if (pulseMesh && pulseMat) {
          anim.pulseT += dt / 0.65;
          pulseMesh.visible = anim.pulseT < 1;
          if (pulseMesh.visible) {
            const sc = 1 + anim.pulseT * 2.4;
            pulseMesh.scale.set(sc, sc, 1);
            pulseMat.opacity = Math.max(0, 0.85 * (1 - anim.pulseT));
          }
        }
        if (anim.failHold <= 0) {
          anim.u = 0;
          anim.passedGates.clear();
          if (pulseMesh) pulseMesh.visible = false;
        }
        return;
      }

      let rate = 1 / 7;
      const inUnk = activeStations.some((s) => s.outcome === "unknown" && Math.abs(s.u - anim.u) < 0.045);
      if (inUnk) rate *= 0.38;
      if (anim.gateHold > 0) {
        anim.gateHold -= dt;
        rate *= 0.1;
      } else {
        const hitGate = activeStations.find((s) => s.step.gate && Math.abs(s.u - anim.u) < 0.018 && !anim.passedGates.has(s.key));
        if (hitGate) {
          anim.passedGates.add(hitGate.key);
          anim.gateHold = 0.18;
        }
      }

      anim.u += dt * rate;
      if (failU !== null && anim.u >= failU) {
        anim.u = failU;
        anim.failHold = 1.4;
        anim.pulseT = 0;
        const fp = activeCurve.getPointAt(failU);
        carrier.position.set(fp.x, 0.28, fp.z);
        carrierMat.color.setHex(C.failed);
        carrierMat.emissive.setHex(C.failed);
        carrierMat.emissiveIntensity = 0.9;
        if (pulseMesh && pulseMat) {
          pulseMesh.position.set(fp.x, 0.29, fp.z);
          pulseMesh.scale.set(1, 1, 1);
          pulseMat.opacity = 0.85;
          pulseMesh.visible = true;
        }
        return;
      }
      if (anim.u >= 1) {
        anim.u -= 1;
        anim.passedGates.clear();
      }
      const pt = activeCurve.getPointAt(anim.u);
      const nxt = activeCurve.getPointAt(Math.min(1, anim.u + 0.008));
      carrier.position.set(pt.x, 0.28, pt.z);
      carrier.lookAt(nxt.x, 0.28, nxt.z);
      const near = activeStations.reduce((a, b) => (Math.abs(b.u - anim.u) < Math.abs(a.u - anim.u) ? b : a), activeStations[0]);
      const col = inUnk ? C.unk : near?.outcome === "recorded" ? C.rec : C.clean;
      carrierMat.color.setHex(col);
      carrierMat.emissive.setHex(col);
      carrierMat.emissiveIntensity = col === C.rec ? 0.25 : 0.75;
    };

    const renderOnce = () => {
      renderer.render(scene, cam);
      projectLabels();
    };

    const tick = (now) => {
      anim.raf = 0;
      if (anim.paused || anim.reduced) return;
      const dt = anim.lastT ? Math.min(0.05, (now - anim.lastT) / 1000) : 0;
      anim.lastT = now;
      stepCarrier(dt);
      renderOnce();
      anim.raf = requestAnimationFrame(tick);
    };

    const syncLoop = () => {
      if (carrier) carrier.visible = !anim.reduced;
      if (pulseMesh && anim.reduced) pulseMesh.visible = false;
      chevronsGroup.visible = anim.reduced;
      if (anim.raf) { cancelAnimationFrame(anim.raf); anim.raf = 0; }
      anim.lastT = 0;
      if (!anim.reduced && !anim.paused) {
        anim.raf = requestAnimationFrame(tick);
      } else {
        if (activeCurve && carrier) stepCarrier(0);
        renderOnce();
      }
    };

    // ResizeObserver and pointer/wheel interactions
    const resize = () => {
      const rect = host.getBoundingClientRect();
      camState.w = Math.max(1, Math.floor(rect.width));
      camState.h = Math.max(1, Math.floor(rect.height));
      renderer.setSize(camState.w, camState.h, false);
      applyCamera();
      renderOnce();
    };
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    ro?.observe(host);

    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    const pick = (e) => {
      const rect = renderer.domElement.getBoundingClientRect();
      ndc.x = ((e.clientX - rect.left) / Math.max(rect.width, 1)) * 2 - 1;
      ndc.y = -((e.clientY - rect.top) / Math.max(rect.height, 1)) * 2 + 1;
      ray.setFromCamera(ndc, cam);
      const hit = ray.intersectObjects(hitBoxes, false)[0];
      return hit ? hit.object.userData.key : null;
    };

    let drag = null;
    const onDown = (e) => {
      if (e.button !== 0) return;
      drag = { id: e.pointerId, x: e.clientX, y: e.clientY, yaw: camState.yaw, pitch: camState.pitch, moved: false };
      renderer.domElement.setPointerCapture?.(e.pointerId);
    };
    const onMove = (e) => {
      if (drag && drag.id === e.pointerId) {
        const dx = e.clientX - drag.x;
        const dy = e.clientY - drag.y;
        if (!drag.moved && Math.hypot(dx, dy) > 4) {
          drag.moved = true;
          setDragging(true);
        }
        if (drag.moved) {
          camState.yaw = clamp(drag.yaw - dx * 0.004, -16 * DEG, 16 * DEG);
          camState.pitch = clamp(drag.pitch + dy * 0.004, 35 * DEG, 62 * DEG);
          applyCamera();
          renderOnce();
        }
        return;
      }
      const k = pick(e);
      setHoveredKey((prev) => (prev === k ? prev : k));
    };
    const onUp = (e) => {
      if (!drag || drag.id !== e.pointerId) return;
      const wasDrag = drag.moved;
      drag = null;
      setDragging(false);
      renderer.domElement.releasePointerCapture?.(e.pointerId);
      if (!wasDrag) {
        const k = pick(e);
        if (k) onSelectRef.current?.(k);
      }
    };
    const onLeave = () => { if (!drag) setHoveredKey(null); };
    const onWheel = (e) => {
      e.preventDefault();
      camState.zoom = clamp(camState.zoom * Math.exp(-e.deltaY * 0.0012), 0.85, 1.75);
      applyCamera();
      renderOnce();
    };

    const dom = renderer.domElement;
    dom.addEventListener("pointerdown", onDown);
    dom.addEventListener("pointermove", onMove);
    dom.addEventListener("pointerup", onUp);
    dom.addEventListener("pointercancel", onUp);
    dom.addEventListener("pointerleave", onLeave);
    dom.addEventListener("wheel", onWheel, { passive: false });

    sceneRef.current = {
      scene, camState, stationMeta, hoverRim, selectBracket, boardTopMat, anim,
      applyCamera, renderOnce, syncLoop,
      resetView: () => { camState.yaw = YAW0; camState.pitch = PITCH0; camState.zoom = 1; applyCamera(); renderOnce(); },
    };
    resize();

    return () => {
      if (anim.raf) cancelAnimationFrame(anim.raf);
      ro?.disconnect();
      dom.removeEventListener("pointerdown", onDown);
      dom.removeEventListener("pointermove", onMove);
      dom.removeEventListener("pointerup", onUp);
      dom.removeEventListener("pointercancel", onUp);
      dom.removeEventListener("pointerleave", onLeave);
      dom.removeEventListener("wheel", onWheel);
      const geos = new Set();
      const mats = new Set();
      const texs = new Set([hatchTex]);
      scene.traverse((o) => {
        if (o.geometry) geos.add(o.geometry);
        const ml = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
        for (const m of ml) { mats.add(m); if (m.map) texs.add(m.map); }
      });
      geos.forEach((g) => g.dispose());
      texs.forEach((t) => t.dispose());
      mats.forEach((m) => m.dispose());
      renderer.dispose();
      dom.remove();
      sceneRef.current = null;
    };
  }, [steps, webglFailed]);

  // Separate effects for board texture, selection, hover, and playback mode
  useEffect(() => {
    const st = sceneRef.current;
    if (!st) return;
    let alive = true;
    const mat = st.boardTopMat;
    if (Array.isArray(renders) && renders.includes("top") && typeof renderUrl === "function") {
      new THREE.TextureLoader().load(
        renderUrl("top"),
        (tex) => {
          if (!alive) { tex.dispose(); return; }
          tex.colorSpace = THREE.SRGBColorSpace;
          mat.map?.dispose();
          mat.map = tex;
          mat.color.setHex(0xffffff);
          mat.needsUpdate = true;
          st.renderOnce();
        },
        undefined,
        () => {}
      );
    } else if (mat.map) {
      mat.map.dispose();
      mat.map = null;
      mat.color.setHex(C.pad);
      mat.needsUpdate = true;
      st.renderOnce();
    }
    return () => { alive = false; };
  }, [renders, renderUrl, steps]);

  useEffect(() => {
    const st = sceneRef.current;
    if (!st) return;
    const meta = selectedKey ? st.stationMeta[selectedKey] : null;
    st.selectBracket.visible = Boolean(meta);
    if (meta) {
      st.selectBracket.position.set(meta.pos.x, 0, meta.pos.z);
      st.selectBracket.rotation.y = meta.pos.ry;
    }
    st.renderOnce();
  }, [selectedKey, steps]);

  useEffect(() => {
    const st = sceneRef.current;
    if (!st) return;
    const meta = hoveredKey ? st.stationMeta[hoveredKey] : null;
    st.hoverRim.visible = Boolean(meta);
    if (meta) {
      st.hoverRim.position.set(meta.pos.x, 0.27, meta.pos.z);
      st.hoverRim.rotation.y = meta.pos.ry;
    }
    st.renderOnce();
  }, [hoveredKey, steps]);

  useEffect(() => {
    const st = sceneRef.current;
    if (!st) return;
    st.anim.paused = paused;
    st.anim.reduced = reduced;
    st.syncLoop();
  }, [paused, reduced, steps]);

  if (webglFailed) return null;

  // Keyboard navigation and DOM overlay render
  const onKeyDown = (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    if (!orderedSteps.length) return;
    e.preventDefault();
    const dir = e.key === "ArrowRight" ? 1 : -1;
    const idx = orderedSteps.findIndex((s) => s.key === selectedKey);
    const next = idx < 0 ? (dir > 0 ? 0 : orderedSteps.length - 1) : (idx + dir + orderedSteps.length) % orderedSteps.length;
    onSelectRef.current?.(orderedSteps[next].key);
  };

  return (
    <div ref={rootRef} className="wb-flow-root" role="group" aria-label="Board pipeline, 3D" tabIndex={0} onKeyDown={onKeyDown}>
      <div ref={canvasHostRef} className={`wb-flow-canvas${dragging ? " is-drag" : hoveredKey ? " is-hover" : ""}`} />
      <div className="wb-flow-labels" aria-hidden="true">
        {orderedSteps.map((step) => {
          const outcome = step.run?.outcome || "unknown";
          const line = step.run?.line ?? "";
          const showLine = Boolean(line) && (selectedKey === step.key || hoveredKey === step.key || outcome === "failed" || outcome === "unknown");
          const cls = `wb-flow-label is-${outcome}${selectedKey === step.key ? " is-selected" : ""}${hoveredKey === step.key ? " is-hover" : ""}`;
          return (
            <div key={step.key} ref={(el) => { if (el) labelRefs.current[step.key] = el; else delete labelRefs.current[step.key]; }} className={cls}>
              <div className="wb-flow-head">
                <span className="wb-flow-num">{String(step.n).padStart(2, "0")}</span>
                <span className="wb-flow-title">{step.title}</span>
              </div>
              {showLine && <div className="wb-flow-line">{line}</div>}
            </div>
          );
        })}
      </div>
      <div className="wb-flow-hud">
        <button type="button" className="wb-flow-btn" aria-pressed={paused || reduced} disabled={reduced} onClick={() => setPaused((p) => !p)}>
          {paused ? "Resume" : "Pause"}
        </button>
        <button type="button" className="wb-flow-btn" onClick={() => sceneRef.current?.resetView()}>
          Reset view
        </button>
      </div>
      <ol className="wb-flow-sr">
        {orderedSteps.map((step) => {
          const outcome = step.run?.outcome || "unknown";
          const line = step.run?.line ?? "";
          const aria = `${step.n} ${step.title}${step.gate ? ", gate" : ""}: ${OUTCOME_LABEL[outcome] || outcome}, ${line}`;
          return (
            <li key={step.key}>
              <button type="button" aria-label={aria} aria-pressed={selectedKey === step.key} onClick={() => onSelectRef.current?.(step.key)}>
                {aria}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
