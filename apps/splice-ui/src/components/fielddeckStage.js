import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { HorizontalBlurShader } from "three/examples/jsm/shaders/HorizontalBlurShader.js";
import { VerticalBlurShader } from "three/examples/jsm/shaders/VerticalBlurShader.js";
import { fielddeckSceneUrl } from "../api.js";
import { classifyPart, DEFAULT_EXPLODE, explodeGroupOffsets, FIELDDECK_NARROW, placeCallouts, rowForNode, TOUR } from "./fielddeckLogic.js";

const COLORS = {
  custom: 0xd8ccb6, vendor_step: 0x94a6b2, envelope: 0x94a6b2,
  unknown: 0x9097a0, proxy: 0xa6a098, changed: 0xe0a040, added: 0x2dd4bf,
  removed: 0xf17e70,
};
const CONTACT_LAYER = 1;
const UP = new THREE.Vector3(0, 0, 1);
const VIEW = new THREE.Vector3(8.2, -9.6, 9.1).normalize();
const clamp = (n) => Math.min(1, Math.max(0, n));
const outCubic = (t) => 1 - (1 - t) ** 3;
const inOutCubic = (t) => t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
const damped = (t) => (1 - (1 + 7 * t) * Math.exp(-7 * t)) / (1 - 8 * Math.exp(-7));

async function request(url, type, signal) {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`.trim());
  return response[type]();
}

export async function loadFielddeck(signal) {
  const loader = new GLTFLoader();
  const revisions = await Promise.all(["7", "5"].map(async (revision) => {
    const url = fielddeckSceneUrl(revision);
    const [sidecar, model] = await Promise.allSettled([
      request(url, "json", signal),
      request(`${url}/model`, "arrayBuffer", signal).then((bytes) => loader.parseAsync(bytes, url)),
    ]);
    return [revision, {
      sidecar: sidecar.value,
      gltf: model.value,
      error: sidecar.status === "rejected" ? `Fielddeck ${revision} parts unavailable (${sidecar.reason.message}).`
        : model.status === "rejected" ? `Fielddeck ${revision} model unavailable (${model.reason.message}).` : null,
    }];
  }));
  return Object.fromEntries(revisions);
}

export function disposeFielddeck(assets) {
  const resources = new Set();
  for (const { gltf } of Object.values(assets)) {
    for (const scene of gltf?.scenes ?? []) {
      scene.traverse((object) => {
        if (object.geometry) resources.add(object.geometry);
        for (const material of [object.material].flat().filter(Boolean)) {
          resources.add(material);
          for (const value of Object.values(material)) {
            if (value?.isTexture) resources.add(value);
          }
        }
      });
    }
  }
  resources.forEach((resource) => resource.dispose());
}

function solidMaterial(basis) {
  return new THREE.MeshStandardMaterial({
    color: COLORS[basis], metalness: 0, roughness: basis === "vendor_step" ? 0.78 : 0.84,
    polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
  });
}

function applyHatch(material, spacing, pixelRatio) {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.hatchStep = { value: spacing * pixelRatio };
    shader.fragmentShader = shader.fragmentShader.replace("#include <common>",
      "#include <common>\nuniform float hatchStep;");
    shader.fragmentShader = shader.fragmentShader.replace("#include <color_fragment>", `
      #include <color_fragment>
      float hatch = step(0.8, fract((gl_FragCoord.x + gl_FragCoord.y) / hatchStep));
      diffuseColor.rgb *= 1.0 - hatch * 0.24;
    `);
  };
}

function edgeMaterial(color, pattern, linewidth) {
  return new LineMaterial({
    color, linewidth, dashed: Boolean(pattern), dashSize: pattern?.[0] ?? 1, gapSize: pattern?.[1] ?? 1,
    transparent: true, depthWrite: false, toneMapped: false, alphaToCoverage: true,
  });
}

function stylePart(entry, compare, weight, ghost, accent) {
  const { basis, outline, row } = entry;
  const { solid, baseColor, mutedColor, fill, edge, surface, lines } = entry.style;
  const translucent = outline || ghost;
  const dimming = row.delta === "unchanged" ? compare : 0;
  const dim = 1 - dimming * 0.6;
  fill.color.setHex(ghost ? COLORS.removed : COLORS[basis]);
  fill.opacity = weight * dim * (ghost ? 0.035 : basis === "envelope" ? 0.06 : 0);
  if (solid) {
    solid.color.copy(baseColor).lerp(mutedColor, dimming);
    solid.opacity = weight;
    const transparent = weight < 0.999;
    if (solid.transparent !== transparent) {
      solid.transparent = transparent;
      solid.needsUpdate = true;
    }
    solid.depthWrite = weight > 0.55;
  }

  const variant = ghost ? edge.ghost : edge.diff && accent > 0 ? edge.diff : edge.base;
  if (variant === edge.diff) variant.color.setHex(COLORS[basis]).lerp(entry.accentColor, accent);
  const baseAlpha = outline ? 0.82 : basis === "custom" ? 0.32 : 0.48;
  variant.opacity = weight * dim * (ghost ? 1 : THREE.MathUtils.lerp(baseAlpha, 1, accent));

  for (const mesh of surface) {
    mesh.material = translucent ? fill : solid;
    mesh.visible = basis !== "unknown" || ghost;
    mesh.castShadow = !translucent && weight >= 0.49;
    mesh.receiveShadow = !translucent;
    if (mesh.castShadow) mesh.layers.enable(CONTACT_LAYER);
    else mesh.layers.disable(CONTACT_LAYER);
  }
  lines.forEach((line) => { line.material = variant; });
}

function makeEntries(assets, index, scene, resources) {
  const entries = new Map();
  const own = (resource) => {
    resources.add(resource);
    return resource;
  };
  for (const [revision, { gltf, sidecar }] of Object.entries(assets)) {
    if (!gltf || !sidecar) continue;
    const { associations, json } = gltf.parser;
    const mm = sidecar.glb_scale_to_mm;
    const scale = new THREE.Matrix4().makeScale(mm, mm, mm);
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse((source) => {
      if (!source.isMesh) return;
      // The loader sanitizes Object3D.name. Read the original glTF name via its node association.
      let row;
      for (let node = source; node && node !== gltf.scene; node = node.parent) {
        const nodeIndex = associations.get(node)?.nodes;
        if (nodeIndex === undefined) continue;
        row = rowForNode(index, revision, json.nodes[nodeIndex].name, nodeIndex);
        break;
      }
      if (!row) return;
      let entry = entries.get(row.key);
      if (!entry) {
        const { basis, outline } = classifyPart(row.part);
        const group = new THREE.Group();
        const vector = new THREE.Vector3();
        const pattern = basis === "envelope" ? [4, 2.5] : basis === "unknown" ? [0.9, 2.8] : null;
        const solid = outline ? null : own(solidMaterial(basis));
        const baseColor = new THREE.Color(COLORS[basis]);
        const gray = baseColor.r * 0.2126 + baseColor.g * 0.7152 + baseColor.b * 0.0722;
        const mutedColor = baseColor.clone().lerp(new THREE.Color().setRGB(gray, gray, gray), 0.65).multiplyScalar(0.4);
        const fill = own(new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false }));
        const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
        if (basis === "envelope") applyHatch(fill, 8, pixelRatio);
        if (basis === "proxy") applyHatch(solid, 8, pixelRatio);
        entry = {
          row, basis, outline, group, vector, bounds: new THREE.Box3(), hover: 0,
          accentColor: new THREE.Color(COLORS[row.delta]),
          style: {
            solid, baseColor, mutedColor, fill,
            edge: {
              base: own(edgeMaterial(COLORS[basis], pattern, 1)),
              diff: ["added", "changed"].includes(row.delta) ? own(edgeMaterial(COLORS[row.delta], pattern, 1.5)) : null,
              ghost: row.delta === "removed" ? own(edgeMaterial(COLORS.removed, [5, 3], 1.5)) : null,
            },
            surface: [], lines: [],
          },
        };
        entries.set(row.key, entry);
        scene.add(group);
      }

      // Bake the GLB's node hierarchy into mm so presentation offsets remain in scene axes.
      const geometry = own(source.geometry.clone().applyMatrix4(new THREE.Matrix4().multiplyMatrices(scale, source.matrixWorld)));
      if (!geometry.getAttribute("normal")) geometry.computeVertexNormals();
      geometry.computeBoundingBox();
      entry.bounds.union(geometry.boundingBox);
      const { style, group } = entry;
      const mesh = new THREE.Mesh(geometry, style.solid ?? style.fill);
      style.surface.push(mesh);
      group.add(mesh);

      const edges = new THREE.EdgesGeometry(geometry, 28);
      const segments = own(new LineSegmentsGeometry());
      segments.setPositions(edges.getAttribute("position").array);
      edges.dispose();
      const line = new LineSegments2(segments, style.edge.base);
      if (style.edge.base.dashed || style.edge.ghost) line.computeLineDistances();
      style.lines.push(line);
      group.add(line);
    });
  }
  return entries;
}

function boundsFor(entries, explode) {
  const bounds = new THREE.Box3();
  const box = new THREE.Box3();
  const vector = new THREE.Vector3();
  const amount = typeof explode === "function" ? explode : () => explode;
  for (const entry of entries) {
    bounds.union(box.copy(entry.bounds).translate(vector.copy(entry.vector).multiplyScalar(amount(entry))));
  }
  return bounds;
}

function groupExplode(entries) {
  const center = boundsFor(entries, 0).getCenter(new THREE.Vector3());
  // Share layer clearances across revisions so removed geometry stays aligned in Compare.
  const layers = [
    ["foot", 0], ["seam", 8], ["enclosure", 8], ["face", 44], ["display-spacer", 19], ["display", 29],
  ].map(([kind, gap]) => ({ kind, gap, bounds: new THREE.Box3(), groups: [] }));
  const byKind = new Map(layers.map((layer) => [layer.kind, layer]));
  const groups = new Map();
  for (const entry of entries) {
    const { part, revision } = entry.row;
    const id = part.part_id;
    const kind = id === "fan-guard" ? "face"
      : id.match(/^(face|seam|foot|display-spacer)-/)?.[1] ?? id;
    const layer = byKind.get(kind) ?? byKind.get("enclosure");
    const name = id === "fan-duct" ? "fan-envelope" : part.group ?? id;
    const key = `${revision}:${layer.kind}:${name}`;
    if (!groups.has(key)) {
      const group = { members: [], bounds: new THREE.Box3() };
      groups.set(key, group);
      layer.groups.push(group);
    }
    const group = groups.get(key);
    group.members.push(entry);
    group.bounds.union(entry.bounds);
  }

  // Trays and their contents share a height band. The contents lift within that band.
  for (const layer of layers) {
    for (const group of layer.groups) {
      const relative = group.bounds.getCenter(new THREE.Vector3()).sub(center);
      const tray = group.members[0].row.part.part_id.startsWith("tray-");
      const inside = layer.kind === "enclosure" && !tray;
      const outward = layer.kind === "foot" ? 0.19 : tray ? 0.16 : inside ? 0.1 : 0;
      group.offset = relative.multiply(new THREE.Vector3(outward, outward, inside ? 0.19 : 0));
      if (inside) group.offset.z += 18;
      layer.bounds.union(group.bounds.clone().translate(group.offset));
    }
  }
  const present = layers.filter(({ groups }) => groups.length);
  const anchor = Math.max(0, present.findIndex(({ kind }) => kind === "enclosure"));
  const lift = explodeGroupOffsets(present.map(({ bounds, gap }) => ({
    minZ: bounds.min.z, maxZ: bounds.max.z, gap,
  })), anchor, DEFAULT_EXPLODE);
  for (const [i, { groups }] of present.entries()) {
    for (const group of groups) {
      group.offset.z += lift[i];
      group.offset.divideScalar(DEFAULT_EXPLODE);
      for (const entry of group.members) {
        entry.vector.copy(group.offset);
        // Upper layers start first so lower layers don't close the gap during the lift.
        entry.explodeDelay = i <= anchor ? 0 : 70 * Math.min(2, present.length - 1 - i);
      }
    }
  }
}

function createContactShadow(scene, renderer, bounds, resources) {
  const size = 512;
  const center = bounds.getCenter(new THREE.Vector3());
  const spread = bounds.getSize(new THREE.Vector3());
  const width = spread.x + 100;
  const height = spread.y + 100;
  const target = new THREE.WebGLRenderTarget(size, size);
  const blurTarget = new THREE.WebGLRenderTarget(size, size, { depthBuffer: false });
  const capture = new THREE.OrthographicCamera(-width / 2, width / 2, height / 2, -height / 2,
    0, Math.max(80, spread.z * 1.1));
  capture.layers.set(CONTACT_LAYER);
  const depth = new THREE.ShaderMaterial({
    side: THREE.DoubleSide,
    vertexShader: `void main() {
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
    fragmentShader: `void main() {
      gl_FragColor = vec4(0.0, 0.0, 0.0, pow(1.0 - gl_FragCoord.z, 2.0));
    }`,
  });

  const quadGeometry = new THREE.PlaneGeometry(2, 2);
  const blurCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 2);
  blurCamera.position.z = 1;
  const blurScene = new THREE.Scene();
  const blurMaterial = (shader) => new THREE.ShaderMaterial({
    ...shader, uniforms: THREE.UniformsUtils.clone(shader.uniforms), depthTest: false, depthWrite: false,
  });
  const horizontal = blurMaterial(HorizontalBlurShader);
  const vertical = blurMaterial(VerticalBlurShader);
  horizontal.uniforms.tDiffuse.value = target.texture;
  horizontal.uniforms.h.value = 1.4 / size;
  vertical.uniforms.tDiffuse.value = blurTarget.texture;
  vertical.uniforms.v.value = 1.4 / size;
  const quad = new THREE.Mesh(quadGeometry, horizontal);
  blurScene.add(quad);

  // Looking up from the ground mirrors the X axis in the captured texture.
  target.texture.repeat.x = -1;
  target.texture.offset.x = 1;
  const groundGeometry = new THREE.PlaneGeometry(width, height);
  const groundMaterial = new THREE.MeshBasicMaterial({
    map: target.texture, transparent: true, depthWrite: false, opacity: 0.66, toneMapped: false,
  });
  const ground = new THREE.Mesh(groundGeometry, groundMaterial);
  ground.renderOrder = -1;
  const poolMaterial = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, toneMapped: false,
    uniforms: { tint: { value: new THREE.Color(0x9baebf) } },
    vertexShader: `
      varying vec2 floorUv;
      void main() {
        floorUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      uniform vec3 tint;
      varying vec2 floorUv;
      void main() {
        float falloff = 1.0 - smoothstep(0.0, 1.0, length(floorUv * 2.0 - 1.0));
        gl_FragColor = vec4(tint, 0.085 * falloff * falloff);
        #include <colorspace_fragment>
      }`,
  });
  const pool = new THREE.Mesh(quadGeometry, poolMaterial);
  pool.scale.set(width * 0.74, height * 0.74, 1);
  pool.renderOrder = -2;
  scene.add(ground, pool);
  [target, blurTarget, depth, quadGeometry, horizontal, vertical, groundGeometry, groundMaterial, poolMaterial]
    .forEach((resource) => resources.add(resource));

  return (floor) => {
    pool.visible = ground.visible = Number.isFinite(floor);
    if (!ground.visible) return;
    ground.position.set(center.x, center.y, floor - 1);
    pool.position.set(center.x, center.y, floor - 1.1);
    capture.position.copy(ground.position);
    capture.lookAt(center.x, center.y, floor + 1);

    // Depth from below, then two separable blur passes before compositing the ground.
    const override = scene.overrideMaterial;
    const shadowUpdates = renderer.shadowMap.autoUpdate;
    renderer.shadowMap.autoUpdate = false;
    renderer.setRenderTarget(target);
    scene.overrideMaterial = depth;
    renderer.render(scene, capture);
    scene.overrideMaterial = override;
    quad.material = horizontal;
    renderer.setRenderTarget(blurTarget);
    renderer.render(blurScene, blurCamera);
    quad.material = vertical;
    renderer.setRenderTarget(target);
    renderer.render(blurScene, blurCamera);
    renderer.setRenderTarget(null);
    renderer.shadowMap.autoUpdate = shadowUpdates;
  };
}

function modelWeights(mode) {
  return { seven: mode === "7" ? 1 : 0, five: mode === "7" ? 0 : 1, compare: mode === "compare" ? 1 : 0 };
}

function layoutAnnotations(host, camera, entries, width, height, canvasTop, panels, placeLabels) {
  const origin = host.getBoundingClientRect();
  const viewport = {
    left: Math.max(8, 8 - origin.left),
    top: Math.max(canvasTop + 8, 8 - origin.top),
    right: Math.min(width, document.documentElement.clientWidth - origin.left) - 8,
    bottom: Math.min(canvasTop + height, document.documentElement.clientHeight - origin.top) - 8,
  };
  function rectFor(panel) {
    const { left, right, top, bottom } = panel.getBoundingClientRect();
    return { left: left - origin.left, right: right - origin.left, top: top - origin.top, bottom: bottom - origin.top };
  }
  const project = (point) => {
    const { x, y, z } = point.project(camera);
    if (z < -1 || z > 1) return null;
    return { x: (x + 1) * width / 2, y: canvasTop + (1 - y) * height / 2 };
  };
  const boundsForKey = (key) => {
    const entry = entries.get(key);
    return entry?.group.visible ? entry.bounds.clone().translate(entry.group.position) : null;
  };
  const centerFor = (key) => {
    const bounds = boundsForKey(key);
    return bounds && project(bounds.getCenter(new THREE.Vector3()));
  };
  function position(node, point) {
    const visible = point && point.x >= viewport.left && point.x <= viewport.right
      && point.y >= viewport.top && point.y <= viewport.bottom;
    node.style.visibility = visible ? "visible" : "hidden";
    if (visible) node.style.transform = `translate(${point.x}px, ${point.y}px)`;
  }
  function outlineFor(bounds, pad = 0) {
    if (!bounds) return null;
    const corners = [bounds.min.x, bounds.max.x].flatMap((x) =>
      [bounds.min.y, bounds.max.y].flatMap((y) =>
        [bounds.min.z, bounds.max.z].map((z) => project(new THREE.Vector3(x, y, z)))));
    if (corners.some((point) => !point)) return null;
    const xs = corners.map(({ x }) => x);
    const ys = corners.map(({ y }) => y);
    return {
      left: Math.min(...xs) - pad, right: Math.max(...xs) + pad,
      top: Math.min(...ys) - pad, bottom: Math.max(...ys) + pad,
    };
  }

  const pinRects = [];
  for (const node of host.querySelectorAll("[data-pin-anchor]")) {
    position(node, centerFor(node.dataset.pinAnchor));
    if (placeLabels && node.style.visibility === "visible") pinRects.push(rectFor(node));
  }
  for (const path of host.querySelectorAll("[data-bracket]")) {
    const outline = outlineFor(boundsForKey(path.dataset.bracket), 6);
    if (!outline) {
      path.removeAttribute("d");
      continue;
    }
    const { left, right, top, bottom } = outline;
    const size = Math.min(12, (right - left) / 3, (bottom - top) / 3);
    path.setAttribute("d", [left, right].flatMap((x, i) => [top, bottom].map((y, j) => {
      const dx = i ? -size : size;
      const dy = j ? -size : size;
      return `M${x + dx},${y}H${x}v${dy}`;
    })).join(" "));
  }

  for (const node of host.querySelectorAll("[data-route-label]")) {
    const from = centerFor(node.dataset.from);
    const to = centerFor(node.dataset.to);
    const midpoint = from && to ? { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 } : null;
    position(node, midpoint);
    if (placeLabels && node.style.visibility === "visible") pinRects.push(rectFor(node));
  }

  if (!placeLabels) return;
  const labels = [...host.querySelectorAll("[data-anchor]")];
  if (!labels.length) return;
  const occupied = panels.filter((panel) => panel.getClientRects().length).map(rectFor);
  const outlines = [...entries.values()].filter(({ group }) => group.visible)
    .map(({ row }) => outlineFor(boundsForKey(row.key))).filter(Boolean);
  const placements = placeCallouts(viewport, occupied, labels.map((node) => {
    const anchor = centerFor(node.dataset.anchor);
    return { anchor, width: node.offsetWidth, height: node.offsetHeight, elbow: true };
  }), [...outlines, ...pinRects]);
  for (const [i, node] of labels.entries()) {
    const line = host.querySelector(`[data-leader="${i}"]`);
    const placement = placements[i];
    node.style.visibility = line.style.visibility = placement ? "visible" : "hidden";
    if (!placement) continue;
    const { rect, leader } = placement;
    node.style.transform = `translate(${rect.left}px, ${rect.top}px)`;
    line.querySelector("path").setAttribute("d", leader.map(({ x, y }, j) => `${j ? "L" : "M"}${x},${y}`).join(" "));
    const dot = line.querySelector("circle");
    dot.setAttribute("cx", leader.at(-1).x);
    dot.setAttribute("cy", leader.at(-1).y);
  }
}

export function createFielddeckStage(host, assets, index, callbacks) {
  const scene = new THREE.Scene();
  const resources = new Set();
  const entries = makeEntries(assets, index, scene, resources);
  const all = [...entries.values()];
  if (!all.length) {
    resources.forEach((resource) => resource.dispose());
    throw new Error("No GLB mesh names match the Fielddeck sidecars.");
  }

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  } catch (error) {
    resources.forEach((resource) => resource.dispose());
    throw error;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.domElement.setAttribute("aria-label", "Interactive Fielddeck assembly");
  host.prepend(renderer.domElement);

  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  room.rotation.x = Math.PI / 2;
  const environment = pmrem.fromScene(room, 0.04);
  room.dispose();
  pmrem.dispose();
  scene.environment = environment.texture;
  scene.environmentIntensity = 0.55;

  const modeEntries = {
    "7": all.filter(({ row }) => row.revision === "7"),
    "5": all.filter(({ row }) => row.revision === "5"),
    compare: all.filter(({ row }) => row.revision === "5" || row.delta === "removed"),
  };
  groupExplode(all);
  const extended = boundsFor(all, 1).union(boundsFor(all, 0));
  const renderContact = createContactShadow(scene, renderer, extended, resources);
  const assembled = boundsFor(all, 0);
  const center = assembled.getCenter(new THREE.Vector3());
  const radius = extended.getSize(new THREE.Vector3()).length() / 2;
  const key = new THREE.DirectionalLight(0xfff1e0, 2.6);
  key.position.set(-4, -5, 9).normalize().multiplyScalar(radius * 2).add(center);
  key.target.position.copy(center);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.radius = 6;
  key.shadow.normalBias = 0.02;
  key.shadow.autoUpdate = false;
  Object.assign(key.shadow.camera, {
    left: -radius, right: radius, top: radius, bottom: -radius, near: 1, far: 4 * radius,
  });
  key.shadow.camera.updateProjectionMatrix();
  const rim = new THREE.DirectionalLight(0x9fc0ff, 1.4);
  rim.position.set(5, 6, 3).normalize().multiplyScalar(radius * 2).add(center);
  rim.target.position.copy(center);
  scene.add(key, key.target, rim, rim.target);

  const camera = new THREE.PerspectiveCamera(26, 1, 0.5, radius * 15);
  camera.up.copy(UP);
  camera.position.copy(VIEW).multiplyScalar(radius * 4).add(center);
  const canvas = renderer.domElement;
  const controls = new OrbitControls(camera, canvas);
  controls.target.copy(center);
  controls.enableDamping = true;
  controls.dampingFactor = 0.15;
  controls.minDistance = radius * 0.2;
  controls.maxDistance = radius * 13;
  controls.update();

  let config;
  let lastConfig;
  let width = 1;
  let height = 1;
  let frameHeight = 1;
  let frameWidth = 1;
  let frameCenterX = 0;
  let canvasTop = 0;
  let frameCenter = 0;
  let mobile = false;
  let resized = true;
  let layoutDirty = true;
  let frame;
  let previousTime = 0;
  let lastLayout = -Infinity;
  let pressed;
  let pointer;
  let pointerMoved = false;
  let hovered;
  let pickable = [];
  let opaque = [];
  let blend;
  let cameraMove;
  let latestCue;
  let lastHero = null;
  let firstFrame = true;
  const ray = new THREE.Raycaster();
  const [header, bottomChrome, tree, inspector, sheet, legend] = [
    ".fd-header", ".fd-bottom", ".fd-tree", ".fd-inspector", ".fd-sheet", ".fd-legend",
  ]
    .map((selector) => host.querySelector(selector));
  const panels = [header, bottomChrome, tree, inspector, sheet, legend];
  const mobileView = window.matchMedia(FIELDDECK_NARROW);
  const invalidateLayout = () => { layoutDirty = true; };

  function resize() {
    const nextWidth = Math.max(1, canvas.clientWidth);
    const nextHeight = Math.max(1, canvas.clientHeight);
    const phone = mobileView.matches;
    const { left: originX, top: originY } = host.getBoundingClientRect();
    const upper = (phone ? bottomChrome : header).getBoundingClientRect().bottom - originY;
    const nextCanvasTop = canvas.offsetTop;
    const lower = phone ? nextHeight + nextCanvasTop : bottomChrome.getBoundingClientRect().top - originY;
    const left = phone ? 0 : Math.max(0, tree.getBoundingClientRect().right - originX);
    const right = phone ? nextWidth : Math.min(nextWidth, inspector.getBoundingClientRect().left - originX);
    const nextFrameHeight = Math.max(1, lower - upper);
    const nextFrameWidth = Math.max(1, right - left);
    const nextFrameCenter = (upper + lower) / 2 - nextCanvasTop;
    const nextFrameCenterX = (left + right) / 2;
    if (nextWidth !== width || nextHeight !== height || resized) renderer.setSize(nextWidth, nextHeight, false);
    resized ||= width !== nextWidth || height !== nextHeight || phone !== mobile
      || frameHeight !== nextFrameHeight || frameWidth !== nextFrameWidth
      || frameCenter !== nextFrameCenter || frameCenterX !== nextFrameCenterX;
    width = nextWidth;
    height = nextHeight;
    mobile = phone;
    canvasTop = nextCanvasTop;
    frameHeight = nextFrameHeight;
    frameWidth = nextFrameWidth;
    frameCenter = nextFrameCenter;
    frameCenterX = nextFrameCenterX;
    const aspect = width / height;
    camera.fov = mobile ? THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(13)) / aspect)) : 26;
    camera.setViewOffset(width, height, width / 2 - frameCenterX, height / 2 - frameCenter, width, height);
    controls.enablePan = !mobile;
    controls.enableZoom = !mobile;
    layoutDirty = true;
  }
  const observer = new ResizeObserver(resize);
  [host, ...panels].forEach((element) => observer.observe(element));
  mobileView.addEventListener("change", resize);
  window.addEventListener("resize", invalidateLayout);
  window.addEventListener("scroll", invalidateLayout, true);
  resize();

  function fit(bounds, angle, horizontal) {
    const target = bounds.getCenter(new THREE.Vector3());
    const direction = VIEW.clone().applyAxisAngle(UP, THREE.MathUtils.degToRad(angle));
    const right = UP.clone().cross(direction).normalize();
    const up = direction.clone().cross(right);
    const tangent = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const horizontalFit = tangent * camera.aspect * (mobile ? horizontal : frameWidth / width * 0.92);
    const verticalFit = tangent * Math.min(1, frameHeight / height) * 0.9;
    if (mobile) {
      const sphere = bounds.getBoundingSphere(new THREE.Sphere());
      const distance = sphere.radius / Math.sin(Math.atan(Math.min(horizontalFit, verticalFit)));
      controls.maxDistance = Math.max(radius * 13, distance);
      camera.far = controls.maxDistance + radius * 2;
      camera.updateProjectionMatrix();
      return { target: sphere.center, position: direction.multiplyScalar(distance).add(sphere.center) };
    }
    let distance = controls.minDistance;
    for (const x of [bounds.min.x, bounds.max.x]) {
      for (const y of [bounds.min.y, bounds.max.y]) {
        for (const z of [bounds.min.z, bounds.max.z]) {
          const p = new THREE.Vector3(x, y, z).sub(target);
          distance = Math.max(distance, p.dot(direction) + Math.max(
            Math.abs(p.dot(right)) / horizontalFit,
            Math.abs(p.dot(up)) / verticalFit,
          ));
        }
      }
    }
    return { target, position: direction.multiplyScalar(distance).add(target) };
  }

  function assemblyPose(mode, explode, turn = mode === "compare" ? 1 : 0) {
    const framed = !mobile && modeEntries[mode].length ? modeEntries[mode] : all;
    return fit(boundsFor(framed, explode), TOUR[0].angle * turn, mobile ? 0.93 : 0.76);
  }

  function tourPose(stopIndex) {
    if (mobile) return assemblyPose(config.mode, config.explode);
    const stop = TOUR[stopIndex];
    const framed = modeEntries[config.mode].length ? modeEntries[config.mode] : all;
    const targetItems = framed.filter(({ row }) => config.selectedKeys.includes(row.key)
      || stop.diff && row.delta === stop.diff);
    const bounds = boundsFor(targetItems.length ? targetItems : framed, config.explode);
    bounds.expandByScalar(stopIndex === 1 ? 26 : 36);
    return fit(bounds, stop.angle, mobile ? 0.89 : 0.72);
  }

  function moveCamera(pose, now, duration, ease) {
    cameraMove = { pose, start: now, duration, ease, from: camera.position.clone(), target: controls.target.clone() };
  }

  function setCamera({ position, target }, amount = 1, from = camera.position, fromTarget = controls.target) {
    camera.position.lerpVectors(from, position, amount);
    controls.target.lerpVectors(fromTarget, target, amount);
    camera.lookAt(controls.target);
  }

  function getHit(event) {
    const rect = canvas.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(
      (event.clientX - rect.left) * 2 / width - 1,
      1 - (event.clientY - rect.top) * 2 / height,
    ), camera);
    return ray.intersectObjects(opaque, false)[0] ?? ray.intersectObjects(pickable, false)[0];
  }
  function down(event) {
    if (event.isPrimary && event.button === 0) pressed = [event.clientX, event.clientY];
    if (config?.heroStart != null) callbacks.onInterrupt();
    cameraMove = null;
  }
  function up(event) {
    if (!pressed || !event.isPrimary) return;
    const distance = Math.hypot(event.clientX - pressed[0], event.clientY - pressed[1]);
    pressed = undefined;
    if (distance > 5) return;
    callbacks.onPick(getHit(event)?.object.userData.fielddeckKey ?? null);
  }
  function move(event) {
    if (event.pointerType !== "mouse") return;
    pointer = event;
    pointerMoved = true;
  }
  function leave() {
    pointer = undefined;
    hovered = undefined;
    pressed = undefined;
    pointerMoved = true;
  }
  canvas.addEventListener("pointerdown", down);
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointermove", move);
  canvas.addEventListener("pointerleave", leave);
  canvas.addEventListener("pointercancel", leave);
  canvas.addEventListener("wheel", () => { cameraMove = null; }, { passive: true });
  for (const entry of all) {
    entry.style.surface.forEach((mesh) => { mesh.userData.fielddeckKey = entry.row.key; });
  }
  const nextPosition = new THREE.Vector3();

  function animate(now) {
    frame = requestAnimationFrame(animate);
    if (!config) return;
    const tick = Math.min(50, now - previousTime);
    previousTime = now;
    const { mode, heroStart, reduced, explode, explodeMotion, cameraCue } = config;
    const heroElapsed = heroStart == null ? null : now - heroStart;
    let dirty = config !== lastConfig || resized || layoutDirty || heroElapsed !== null;
    const motion = heroElapsed === null ? explodeMotion : { from: 0, to: DEFAULT_EXPLODE, start: heroStart + 400 };
    const offsetFor = motion && motion.to > motion.from && !reduced
      ? ({ explodeDelay }) => {
          const phase = outCubic(clamp((now - motion.start - explodeDelay) / (1100 - explodeDelay)));
          return THREE.MathUtils.lerp(motion.from, motion.to, phase);
        } : () => explode;
    if (!blend || mode !== blend.mode) {
      const next = modelWeights(mode);
      blend = { mode, start: now, from: blend?.current ?? next, to: next, current: next };
    }
    const progress = clamp((now - blend.start) / (reduced ? 100 : 450));
    const mix = reduced ? progress : inOutCubic(progress);
    blend.current = {
      seven: THREE.MathUtils.lerp(blend.from.seven, blend.to.seven, mix),
      five: THREE.MathUtils.lerp(blend.from.five, blend.to.five, mix),
      compare: THREE.MathUtils.lerp(blend.from.compare, blend.to.compare, mix),
    };
    const accentProgress = clamp((now - blend.start - (reduced ? 0 : 700)) / (reduced ? 100 : 180));
    dirty ||= progress < 1 || (mode === "compare" && accentProgress < 1);

    if (heroElapsed !== null) {
      const turn = damped(clamp((heroElapsed - 4200) / 800));
      setCamera(assemblyPose(mode, offsetFor, turn));
    } else if (mobile && (firstFrame || resized || lastHero !== null || mode !== lastConfig.mode
      || explode !== lastConfig.explode || explodeMotion || lastConfig.explodeMotion)) {
      cameraMove = null;
      setCamera(assemblyPose(mode, offsetFor));
    } else if (cameraCue && cameraCue !== latestCue) {
      latestCue = cameraCue;
      moveCamera(tourPose(cameraCue.stopIndex), now, 1600, damped);
    } else if (firstFrame || lastHero !== null) {
      setCamera(assemblyPose(mode, offsetFor));
    } else if (mode !== lastConfig.mode) {
      moveCamera(assemblyPose(mode, offsetFor), now, 450, inOutCubic);
    } else if (resized) {
      const pose = cameraCue ? tourPose(cameraCue.stopIndex) : assemblyPose(mode, offsetFor);
      const remaining = cameraMove && cameraMove.duration - (now - cameraMove.start);
      moveCamera(pose, now, Math.max(240, remaining || 0), outCubic);
    } else if (explodeMotion) {
      const pose = assemblyPose(mode, offsetFor);
      if (cameraMove) cameraMove.pose = pose;
      else setCamera(pose, reduced ? 1 : 1 - Math.exp(-tick / 85));
      dirty = true;
    } else if (explode !== lastConfig.explode || lastConfig.explodeMotion) {
      moveCamera(assemblyPose(mode, explode), now, 220, outCubic);
    }
    if (cameraMove) {
      const progress = reduced ? 1 : clamp((now - cameraMove.start) / cameraMove.duration);
      setCamera(cameraMove.pose, cameraMove.ease(progress), cameraMove.from, cameraMove.target);
      dirty = true;
      if (progress === 1) cameraMove = null;
    }
    controls.enableDamping = !reduced;
    dirty = controls.update() || dirty;

    if (!dirty && !wasAnimating && !pointerMoved) return;
    if (pointer && !pressed && (dirty || pointerMoved)) {
      camera.updateMatrixWorld();
      hovered = getHit(pointer)?.object.userData.fielddeckKey;
    }
    pointerMoved = false;
    canvas.style.cursor = hovered ? "pointer" : "grab";

    const pick = [];
    const block = [];
    let floor = Infinity;
    let contactDirty = firstFrame;
    for (const entry of all) {
      const { row, group, vector } = entry;
      const removed = row.revision === "7" && row.delta === "removed";
      const ghost = removed && (mode === "compare" || blend.current.compare > 0 || heroElapsed >= 1600);
      const weight = row.revision === "5" ? blend.current.five
        : ghost ? Math.max(blend.current.seven, blend.current.compare) : blend.current.seven;
      const visible = weight > 0.001;
      const wasCasting = group.visible && entry.style.surface[0].castShadow;
      dirty ||= visible !== group.visible;
      group.visible = visible;
      if (!visible) {
        contactDirty ||= wasCasting;
        continue;
      }
      const hover = Number(hovered === row.key);
      dirty ||= hover !== entry.hover;
      const distance = reduced ? 1 : tick / 120;
      entry.hover += Math.sign(hover - entry.hover) * Math.min(distance, Math.abs(hover - entry.hover));
      const length = vector.length();
      const offset = offsetFor(entry) + (length && !reduced ? 2 * outCubic(entry.hover) / length : 0);
      nextPosition.copy(vector).multiplyScalar(offset);
      const moved = !group.position.equals(nextPosition);
      group.position.copy(nextPosition);
      const accent = (reduced ? accentProgress : outCubic(accentProgress)) * blend.current.compare;
      stylePart(entry, blend.current.compare, weight, ghost, entry.style.edge.diff ? accent : 0);
      const casts = entry.style.surface[0].castShadow;
      contactDirty ||= casts !== wasCasting || casts && moved;
      if (casts) floor = Math.min(floor, entry.bounds.min.z + group.position.z);
      if (row.revision === (mode === "7" ? "7" : "5") || mode === "compare" && ghost) {
        pick.push(...entry.style.surface);
        if (!entry.outline && !ghost) block.push(...entry.style.surface);
      }
    }

    // A step that lands after the final animation frame still needs to draw its exact endpoint.
    if (dirty || wasAnimating) {
      if (contactDirty) {
        renderContact(floor);
        key.shadow.needsUpdate = true;
      }
      renderer.render(scene, camera);
      pickable = pick;
      opaque = block;
      const placeLabels = layoutDirty || resized || config !== lastConfig || !dirty || now - lastLayout > 60;
      layoutAnnotations(host, camera, entries, width, height, canvasTop, panels, placeLabels);
      if (placeLabels) lastLayout = now;
    }
    if (firstFrame) {
      canvas.dataset.fielddeckCanvas = "rendered";
      callbacks.onFrame();
    }
    wasAnimating = dirty;
    firstFrame = false;
    lastConfig = config;
    lastHero = heroStart;
    resized = false;
    layoutDirty = false;
  }
  let wasAnimating = false;
  frame = requestAnimationFrame(animate);

  return {
    linked: new Set(entries.keys()),
    update: (next) => { config = next; },
    dispose() {
      cancelAnimationFrame(frame);
      observer.disconnect();
      mobileView.removeEventListener("change", resize);
      window.removeEventListener("resize", invalidateLayout);
      window.removeEventListener("scroll", invalidateLayout, true);
      controls.dispose();
      environment.dispose();
      key.shadow.dispose();
      resources.forEach((resource) => resource.dispose());
      renderer.dispose();
      canvas.remove();
    },
  };
}
