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
import { classifyPart, DEFAULT_EXPLODE, explodeGroupOffsets, FIELDDECK_NARROW, placeCallouts, formatEvidenceValue, rowForNode, TOUR } from "./fielddeckLogic.js";

const COLORS = {
  custom: 0xd8ccb6, vendor_step: 0x8e979e, envelope: 0xa5aeb5,
  unknown: 0x9097a0, proxy: 0xa6a098, changed: 0xe0a040, added: 0x2dd4bf,
  removed: 0xf17e70,
};
const CONTACT_LAYER = 1;
const UP = new THREE.Vector3(0, 0, 1);
const VIEW = new THREE.Vector3(8.2, -9.6, 9.1).normalize();
const clamp = (n) => Math.min(1, Math.max(0, n));
const outCubic = (t) => 1 - (1 - t) ** 3;
const inOutCubic = (t) => t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
const FACE_UP = new THREE.Vector3(0, 1, 0);
const introEase = (x) => {
  if (x === 0 || x === 1) return x;
  // Evaluate the timing curve by solving its X coordinate before evaluating Y.
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 16; i++) {
    const t = (lo + hi) / 2;
    const curveX = 3 * (1 - t) ** 2 * t * 0.22 + 3 * (1 - t) * t ** 2 * 0.36 + t ** 3;
    if (curveX < x) lo = t;
    else hi = t;
  }
  return 1 - (1 - (lo + hi) / 2) ** 3;
};
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
    color: COLORS[basis], metalness: 0, roughness: basis === "vendor_step" ? 0.82 : 0.84,
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
  fill.opacity = weight * (basis === "envelope" && !ghost ? 0.06 : 0);
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

  const variant = ghost ? edge.ghost : basis !== "envelope" && edge.diff && accent > 0 ? edge.diff : edge.base;
  if (variant === edge.diff) variant.color.setHex(COLORS[basis]).lerp(entry.accentColor, accent);
  const baseAlpha = outline ? 0.82 : basis === "custom" ? 0.32 : 0.48;
  variant.opacity = weight * (basis === "envelope" || ghost ? 1 : dim * THREE.MathUtils.lerp(baseAlpha, 1, accent));

  for (const mesh of surface) {
    mesh.material = translucent ? fill : solid;
    mesh.visible = basis !== "unknown" && !ghost;
    mesh.castShadow = !translucent && weight >= 0.49;
    mesh.receiveShadow = !translucent;
    if (mesh.castShadow) mesh.layers.enable(CONTACT_LAYER);
    else mesh.layers.disable(CONTACT_LAYER);
  }
  lines.forEach((line) => { line.material = variant; });
  return variant;
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
        const pattern = basis === "envelope" ? [4, 3] : basis === "unknown" ? [0.9, 2.8] : null;
        const solid = outline ? null : own(solidMaterial(basis));
        const baseColor = new THREE.Color(COLORS[basis]);
        const gray = baseColor.r * 0.2126 + baseColor.g * 0.7152 + baseColor.b * 0.0722;
        const mutedColor = baseColor.clone().lerp(new THREE.Color().setRGB(gray, gray, gray), 0.65).multiplyScalar(0.4);
        const fill = own(new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false }));
        const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
        if (basis === "proxy") applyHatch(solid, 8, pixelRatio);
        entry = {
          row, basis, outline, group, vector, bounds: new THREE.Box3(),
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

      function featureEdges(threshold, material) {
        const edges = new THREE.EdgesGeometry(geometry, threshold);
        const segments = own(new LineSegmentsGeometry());
        segments.setPositions(edges.getAttribute("position").array);
        edges.dispose();
        const line = new LineSegments2(segments, material);
        line.computeLineDistances();
        return line;
      }

      const line = featureEdges(row.delta === "removed" ? 40 : 28, style.edge.base);
      style.lines.push(line);
      group.add(line);

      const display = row.part.part_id === "display";
      if (display || revision === "7" && (row.delta === "changed"
        || index.byPart.get(`5:${row.part.part_id}`)?.delta === "changed")) {
        if (!entry.overlay) {
          const material = own(edgeMaterial(display && revision === "5" ? COLORS.added : COLORS.removed,
            display && revision === "5" ? null : [5, 3], 1.5));
          const object = new THREE.Group();
          object.visible = false;
          entry.overlay = { object, material };
          scene.add(object);
        }
        entry.overlay.object.add(featureEdges(40, entry.overlay.material));
      }
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

function layoutAnnotations(host, camera, entries, width, height, canvasTop, panels, placeLabels, displayOpacity, showDimensions) {
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

  const occupied = panels.filter((panel) => panel.getClientRects().length).map(rectFor);
  const pinRects = [];
  const markers = [];
  const pinLeaders = [];
  for (const node of host.querySelectorAll("[data-pin-anchor]")) {
    const anchor = centerFor(node.dataset.pinAnchor);
    const clear = (point) => point.x >= viewport.left + 12 && point.x <= viewport.right - 12
      && point.y >= viewport.top + 12 && point.y <= viewport.bottom - 12
      && !occupied.some((rect) => point.x > rect.left - 12 && point.x < rect.right + 12
        && point.y > rect.top - 12 && point.y < rect.bottom + 12)
      && markers.every((other) => Math.hypot(point.x - other.x, point.y - other.y) >= 24);
    let point = anchor;
    if (anchor && !clear(anchor)) {
      const angles = [0, 1, -1, 2, -2, 3, -3, 4].map((step) => step * Math.PI / 4);
      point = angles.map((angle) => ({ x: anchor.x + 36 * Math.cos(angle), y: anchor.y + 36 * Math.sin(angle) }))
        .find(clear);
      if (point) {
        const dx = (point.x - anchor.x) / 3;
        const dy = (point.y - anchor.y) / 3;
        pinLeaders.push(`M${anchor.x + dx},${anchor.y + dy}l${dx},${dy}`);
      }
    }
    position(node, point);
    if (node.style.visibility === "visible") {
      markers.push(point);
      if (placeLabels) pinRects.push(rectFor(node));
    }
  }
  host.querySelector("[data-pin-leaders]").setAttribute("d", pinLeaders.join(" "));

  for (const group of host.querySelectorAll("[data-dimensions]")) {
    const bounds = entries.get(`${group.dataset.dimensions}:part:display`)?.bounds;
    const older = group.dataset.dimensions === "7";
    const path = group.querySelector("path");
    const texts = group.querySelectorAll("text");
    group.style.visibility = "hidden";
    if (!showDimensions || !bounds || bounds.isEmpty()) continue;
    const { min, max } = bounds;
    const z = max.z;
    const corners = [project(new THREE.Vector3(min.x, older ? max.y : min.y, z)),
      project(new THREE.Vector3(max.x, older ? max.y : min.y, z)),
      project(new THREE.Vector3(older ? min.x : max.x, max.y, z)),
      project(new THREE.Vector3(older ? min.x : max.x, min.y, z))];
    if (corners.some((point) => !point)) continue;
    const [a, b, c, d] = corners;
    const y = (older ? Math.min(a.y, b.y) : Math.max(a.y, b.y)) + (older ? -16 : 16);
    const x = (older ? Math.min(c.x, d.x) : Math.max(c.x, d.x)) + (older ? -16 : 16);
    path.setAttribute("d", `M${a.x},${a.y}V${y + (older ? -4 : 4)} M${b.x},${b.y}V${y + (older ? -4 : 4)}
      M${a.x},${y}H${b.x} M${c.x},${c.y}H${x + (older ? -4 : 4)} M${d.x},${d.y}H${x + (older ? -4 : 4)}
      M${x},${c.y}V${d.y}`);
    const dimension = (value) => `${formatEvidenceValue({ field: "dimension_mm", value })} · computed`;
    texts[0].textContent = dimension(max.x - min.x);
    texts[0].setAttribute("x", (a.x + b.x) / 2);
    texts[0].setAttribute("y", y + (older ? -5 : 13));
    texts[1].textContent = dimension(max.y - min.y);
    texts[1].setAttribute("transform", `translate(${x + (older ? -5 : 13)},${(c.y + d.y) / 2}) rotate(-90)`);
    group.style.visibility = "visible";
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

  const labels = [...host.querySelectorAll("[data-anchor]")];
  if (!labels.length) return;
  const outlines = placeLabels ? [...entries.keys()].map((key) => outlineFor(boundsForKey(key))).filter(Boolean) : [];
  const model = {
    left: Math.min(...outlines.map(({ left }) => left)),
    right: Math.max(...outlines.map(({ right }) => right)),
  };
  const placements = placeLabels && placeCallouts(viewport, occupied, labels.map((node) => {
    const anchor = centerFor(node.dataset.anchor);
    const outline = outlineFor(boundsForKey(node.dataset.anchor));
    return {
      anchor, model, width: node.offsetWidth, height: node.offsetHeight, elbow: true,
      leftAnchor: outline && { ...anchor, x: outline.left },
      rightAnchor: outline && { ...anchor, x: outline.right },
    };
  }), pinRects);
  for (const [i, node] of labels.entries()) {
    const line = host.querySelector(`[data-leader="${i}"]`);
    node.style.opacity = line.style.opacity = displayOpacity;
    if (!placements) continue;
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
  const grid = new THREE.GridHelper(600, 30, 0x59636e, 0x59636e);
  grid.rotation.x = Math.PI / 2;
  grid.position.copy(assembled.getCenter(new THREE.Vector3()));
  grid.material.transparent = true;
  grid.material.depthWrite = false;
  grid.material.opacity = 0.2;
  scene.add(grid);
  resources.add(grid.geometry);
  resources.add(grid.material);
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
  const rim = new THREE.DirectionalLight(0xffffff, 1.4);
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
  const minimumDistance = radius * 0.2;
  controls.minDistance = minimumDistance;
  controls.maxDistance = radius * 13;
  controls.update();

  let config;
  let lastConfig;
  let width = 1;
  let height = 1;
  let baseFov = 26;
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
  let priorCamera;
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
    const lower = phone
      ? Math.min(nextHeight + nextCanvasTop, ...[tree, inspector, legend].filter((panel) => panel.getClientRects().length)
        .map((panel) => panel.getBoundingClientRect().top - originY))
      : bottomChrome.getBoundingClientRect().top - originY;
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
    baseFov = mobile ? THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(13)) / aspect)) : 26;
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

  function fit(bounds, angle, horizontal, options = {}) {
    const { target = bounds.getCenter(new THREE.Vector3()), margin, face = false,
      direction = face ? UP.clone() : VIEW.clone().applyAxisAngle(UP, THREE.MathUtils.degToRad(angle)),
    } = options;
    const right = (face ? FACE_UP : UP).clone().cross(direction).normalize();
    const up = direction.clone().cross(right);
    const tangent = Math.tan(THREE.MathUtils.degToRad((face ? 12 : baseFov) / 2));
    const usable = (size) => size > 2 * margin ? size - 2 * margin : size / 3;
    const horizontalFit = tangent * camera.aspect * (margin === undefined
      ? mobile ? horizontal : frameWidth / width * horizontal : usable(frameWidth) / width);
    const verticalFit = tangent * (margin === undefined
      ? Math.min(1, frameHeight / height) * 0.9 : usable(frameHeight) / height);
    if (mobile && margin === undefined) {
      const sphere = bounds.getBoundingSphere(new THREE.Sphere());
      const distance = sphere.radius / Math.sin(Math.atan(Math.min(horizontalFit, verticalFit)));
      controls.maxDistance = Math.max(radius * 13, distance);
      camera.far = controls.maxDistance + radius * 2;
      camera.updateProjectionMatrix();
      return { target: sphere.center, position: direction.multiplyScalar(distance).add(sphere.center) };
    }
    let distance = minimumDistance;
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
    controls.maxDistance = Math.max(radius * 13, distance);
    camera.far = controls.maxDistance + radius * 2;
    camera.updateProjectionMatrix();
    return { target, position: direction.clone().multiplyScalar(distance).add(target) };
  }

  const displays = all.filter(({ row }) => row.part.part_id === "display");
  const displayBounds = boundsFor(displays, 0);

  function facePose(target) {
    return { ...fit(displayBounds, 0, 1, { target, face: true, margin: 48 }), fov: 12, up: FACE_UP };
  }

  function cablePose(direction) {
    const endpoints = config.selectedKeys.map((key) => entries.get(key)).filter(Boolean);
    if (config.selectedKeys.length < 2 || !endpoints.length) return null;
    return fit(boundsFor(endpoints, config.explode), TOUR[1].angle, 1, { margin: 48, direction });
  }

  function assemblyPose(mode, explode) {
    const framed = !mobile && modeEntries[mode].length ? modeEntries[mode] : all;
    return fit(boundsFor(framed, explode), mode === "compare" ? TOUR[0].angle : 0, mobile ? 0.93 : 0.76);
  }

  function tourPose(stopIndex) {
    if (stopIndex === 1) return cablePose() ?? assemblyPose(config.mode, config.explode);
    if (mobile) return assemblyPose(config.mode, config.explode);
    const stop = TOUR[stopIndex];
    const framed = modeEntries[config.mode].length ? modeEntries[config.mode] : all;
    const targetItems = framed.filter(({ row }) => config.selectedKeys.includes(row.key)
      || stop.diff && row.delta === stop.diff);
    const bounds = boundsFor(targetItems.length ? targetItems : framed, config.explode);
    bounds.expandByScalar(36);
    return fit(bounds, stop.angle, mobile ? 0.89 : 0.72);
  }

  function moveCamera(pose, now, duration, ease) {
    cameraMove = { pose, start: now, duration, ease, from: camera.position.clone(), target: controls.target.clone() };
  }

  function setCamera({ position, target, fov = baseFov, up = UP }, amount = 1,
    from = camera.position, fromTarget = controls.target, faceTransition) {
    controls.target.lerpVectors(fromTarget, target, amount);
    if (faceTransition) {
      const fromOffset = from.clone().sub(fromTarget);
      const toOffset = position.clone().sub(target);
      const direction = fromOffset.clone().normalize();
      const turn = new THREE.Quaternion().setFromUnitVectors(direction, toOffset.clone().normalize());
      direction.applyQuaternion(new THREE.Quaternion().slerp(turn, amount));
      camera.position.copy(direction.multiplyScalar(THREE.MathUtils.lerp(fromOffset.length(), toOffset.length(), amount))
        .add(controls.target));
      camera.up.lerpVectors(faceTransition.up, up, amount).normalize();
      fov = THREE.MathUtils.lerp(faceTransition.fov, fov, amount);
    } else {
      camera.position.lerpVectors(from, position, amount);
      camera.up.copy(up);
    }
    camera.fov = fov;
    camera.updateProjectionMatrix();
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
    if (!cameraMove?.faceTransition) cameraMove = null;
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
  canvas.addEventListener("wheel", () => { if (!cameraMove?.faceTransition) cameraMove = null; }, { passive: true });
  for (const entry of all) {
    entry.style.surface.forEach((mesh) => { mesh.userData.fielddeckKey = entry.row.key; });
  }
  const nextPosition = new THREE.Vector3();

  function animate(now) {
    frame = requestAnimationFrame(animate);
    if (!config) return;
    const tick = Math.min(50, now - previousTime);
    previousTime = now;
    const { mode, heroStart, reduced, explode, explodeMotion, cameraCue, faceView, ghostDeltaKey } = config;
    const heroElapsed = heroStart == null ? null : Math.max(0, now - heroStart);
    const displayOpacity = heroElapsed === null ? 1 : clamp((heroElapsed - 850) / 250);
    let dirty = config !== lastConfig || resized || layoutDirty || heroElapsed !== null;
    const motion = explodeMotion;
    const offsetFor = heroElapsed !== null
      ? () => DEFAULT_EXPLODE * introEase(clamp((heroElapsed - 250) / 600))
      : motion && motion.to > motion.from && !reduced
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

    const cable = config.selectedKeys.length >= 2;
    if (heroElapsed !== null) {
      setCamera(assemblyPose(mode, DEFAULT_EXPLODE));
    } else if (faceView !== Boolean(lastConfig?.faceView)) {
      if (faceView && !priorCamera) priorCamera = { position: camera.position.clone(), target: controls.target.clone() };
      moveCamera(faceView ? facePose(controls.target.clone()) : priorCamera, now, 240, inOutCubic);
      cameraMove.faceTransition = { up: camera.up.clone(), fov: camera.fov };
    } else if (faceView) {
      if (resized) {
        const pose = facePose(controls.target.clone());
        if (cameraMove) cameraMove.pose = pose;
        else setCamera(pose);
      }
    } else if (!cameraMove?.faceTransition) {
      if (cable && (firstFrame || resized || mode !== lastConfig.mode || explode !== lastConfig.explode
        || cameraCue !== latestCue || config.selectedKeys.join() !== lastConfig.selectedKeys.join())) {
        latestCue = cameraCue;
        cameraMove = null;
        setCamera(cablePose() ?? assemblyPose(mode, offsetFor));
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
      } else if (explodeMotion && !cable) {
        const pose = assemblyPose(mode, offsetFor);
        if (cameraMove) cameraMove.pose = pose;
        else setCamera(pose, reduced ? 1 : 1 - Math.exp(-tick / 85));
        dirty = true;
      } else if (!cable && (explode !== lastConfig.explode || lastConfig.explodeMotion)) {
        moveCamera(assemblyPose(mode, explode), now, 220, outCubic);
      }
    }
    controls.enabled = !faceView && !cameraMove?.faceTransition && heroElapsed === null;
    if (cameraMove) {
      const { pose, ease, from, target, faceTransition } = cameraMove;
      const progress = reduced ? 1 : clamp((now - cameraMove.start) / cameraMove.duration);
      setCamera(pose, ease(progress), from, target, faceTransition);
      dirty = true;
      if (progress === 1) {
        if (faceTransition && !faceView) priorCamera = null;
        cameraMove = null;
      }
    }
    controls.enableDamping = !reduced;
    controls.enablePan = !mobile && !cable;
    controls.minDistance = minimumDistance;
    if (controls.enabled) {
      dirty = controls.update() || dirty;
      if (cable && dirty) {
        const offset = camera.position.clone().sub(controls.target);
        const pose = cablePose(offset.clone().normalize());
        if (pose && offset.lengthSq() < pose.position.distanceToSquared(pose.target)) setCamera(pose);
      }
    }

    if (!dirty && !wasAnimating && !pointerMoved) return;
    if (pointer && !pressed && (dirty || pointerMoved)) {
      camera.updateMatrixWorld();
      hovered = getHit(pointer)?.object.userData.fielddeckKey;
    }
    pointerMoved = false;
    canvas.style.cursor = hovered ? "pointer" : "grab";

    camera.updateMatrixWorld();
    function scaleDashes(material, entry, position) {
      if (!material.dashed) return;
      const center = entry.bounds.getCenter(new THREE.Vector3()).add(position).applyMatrix4(camera.matrixWorldInverse);
      material.dashScale = height / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * Math.max(1, -center.z));
    }
    grid.visible = !faceView;
    grid.material.opacity = 0.2 * (heroElapsed === null ? 1 : clamp(heroElapsed / 250));

    const pick = [];
    const block = [];
    let floor = Infinity;
    let contactDirty = firstFrame;
    for (const entry of all) {
      const { row, group, vector } = entry;
      const removed = row.revision === "7" && row.delta === "removed";
      const ghost = removed && (mode === "compare" || blend.current.compare > 0);
      const weight = row.revision === "5" ? blend.current.five
        : ghost ? Math.max(blend.current.seven, blend.current.compare) * displayOpacity : blend.current.seven;
      if (entry.overlay) {
        const { object, material } = entry.overlay;
        object.visible = faceView ? row.part.part_id === "display" : row.key === ghostDeltaKey;
        object.position.set(0, 0, 0);
        if (object.visible && !faceView) {
          // Apply the selected layer's presentation offset to both CAD transforms.
          const selected = entries.get(config.selectedKeys[0]);
          if (selected) object.position.copy(selected.vector).multiplyScalar(offsetFor(selected));
        }
        if (object.visible) {
          material.depthTest = faceView;
          scaleDashes(material, entry, object.position);
        }
      }
      const visible = !faceView && weight > 0.001;
      const wasCasting = group.visible && entry.style.surface[0].castShadow;
      dirty ||= visible !== group.visible;
      group.visible = visible;
      if (!visible) {
        contactDirty ||= wasCasting;
        continue;
      }
      nextPosition.copy(vector).multiplyScalar(offsetFor(entry));
      const moved = !group.position.equals(nextPosition);
      group.position.copy(nextPosition);
      const accent = (reduced ? accentProgress : outCubic(accentProgress)) * blend.current.compare;
      const material = stylePart(entry, blend.current.compare, weight, ghost, entry.style.edge.diff ? accent : 0);
      scaleDashes(material, entry, group.position);
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
      grid.position.z = Number.isFinite(floor) ? floor - 0.9 : assembled.min.z - 0.9;
      if (contactDirty) {
        renderContact(floor);
        key.shadow.needsUpdate = true;
      }
      renderer.render(scene, camera);
      pickable = pick;
      opaque = block;
      const placeLabels = layoutDirty || resized || config !== lastConfig || !dirty || now - lastLayout > 60;
      layoutAnnotations(host, camera, entries, width, height, canvasTop, panels, placeLabels, displayOpacity, !cameraMove);
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
