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
import { classifyPart, DEFAULT_EXPLODE, DIFF_COLORS, dimensionLabel, explodeGroupOffsets, FIELDDECK_NARROW, placeCallouts, placeRoutingLabel, projectedFitScale, footprintDelta, materialFor, rowForNode } from "./fielddeckLogic.js";

const TOUR_ANGLES = [18, -5, 24];
const OLD_REVISION_RED = 0xc83e31;
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

function solidMaterial(basis, color, emissive) {
  return new THREE.MeshStandardMaterial({
    color, emissive, metalness: 0, roughness: basis === "vendor_step" ? 0.82 : 0.84,
    flatShading: basis === "vendor_step",
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
    polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
  });
}

function stylePart(entry, compare, weight, ghost, accent, selected) {
  const { basis, outline, row } = entry;
  const { solid, baseColor, mutedColor, fill, edge, surface, lines, halos } = entry.style;
  const translucent = outline || ghost;
  const dimming = row.delta === "unchanged" ? compare : 0;
  const dim = 1 - dimming * 0.6;
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
  if (variant === edge.diff) variant.color.copy(baseColor).lerp(entry.accentColor, accent);
  const baseAlpha = outline ? 0.82 : basis === "custom" ? 0.32 : 0.48;
  const selectedChange = selected && row.delta === "changed";
  variant.linewidth = ghost || selectedChange || row.delta === "added" && variant === edge.diff ? 1.5
    : variant === edge.diff ? 2 : 1;
  variant.opacity = selectedChange ? 1
    : weight * (basis === "envelope" || ghost ? 1 : dim * THREE.MathUtils.lerp(baseAlpha, 1, accent));

  for (const mesh of surface) {
    mesh.material = translucent ? fill : solid;
    mesh.visible = basis !== "unknown" && !ghost;
    mesh.castShadow = !translucent && weight >= 0.49;
    // Vendor STEP can contain coincident surfaces that create self-shadow speckling.
    mesh.receiveShadow = !translucent && basis !== "vendor_step";
    if (mesh.castShadow) mesh.layers.enable(CONTACT_LAYER);
    else mesh.layers.disable(CONTACT_LAYER);
  }
  lines.forEach((line) => {
    line.material = variant;
    line.visible = !ghost || !entry.displayOverlay;
  });
  if (edge.halo) {
    edge.halo.linewidth = variant.linewidth + 2;
    edge.halo.opacity = weight * accent;
    halos.forEach((line) => { line.visible = variant === edge.diff; });
  }
  return variant;
}

function edgePositions(geometry, threshold) {
  const edges = new THREE.EdgesGeometry(geometry, threshold);
  const positions = edges.getAttribute("position").array;
  edges.dispose();
  return positions;
}

function featureLine(positions, material, own) {
  const segments = own(new LineSegmentsGeometry());
  segments.setPositions(positions);
  const line = new LineSegments2(segments, material);
  line.computeLineDistances();
  return line;
}

function displayContours(entry) {
  // The display is in the XY plane. Trace connected face edges at each depth so the two
  // ends of a bore and stacked rim edges do not join into the same contour.
  const vertices = new Map();
  const vertexFor = (xyz) => {
    const key = Array.from(xyz, (value) => Math.round(value * 1000)).join(",");
    if (!vertices.has(key)) {
      vertices.set(key, { id: vertices.size, point: new THREE.Vector3(...xyz), neighbors: new Set() });
    }
    return vertices.get(key);
  };
  for (const positions of entry.displayEdges) {
    for (let i = 0; i < positions.length; i += 6) {
      if (Math.abs(positions[i + 2] - positions[i + 5]) > 0.02) continue;
      const a = vertexFor(positions.slice(i, i + 3));
      const b = vertexFor(positions.slice(i + 3, i + 6));
      if (a !== b) {
        a.neighbors.add(b);
        b.neighbors.add(a);
      }
    }
  }
  const large = [];
  const holes = [];
  const seen = new Set();
  for (const vertex of vertices.values()) {
    if (seen.has(vertex)) continue;
    const component = [vertex];
    const positions = [];
    const bounds = new THREE.Box3();
    seen.add(vertex);
    for (const { id, point, neighbors } of component) {
      bounds.expandByPoint(point);
      for (const neighbor of neighbors) {
        if (!seen.has(neighbor)) {
          component.push(neighbor);
          seen.add(neighbor);
        }
        if (id < neighbor.id) positions.push(point.x, point.y, point.z, neighbor.point.x, neighbor.point.y, neighbor.point.z);
      }
    }
    const { x: width, y: height } = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const diameter = (width + height) / 2;
    const closed = component.every(({ neighbors }) => neighbors.size === 2);
    if (closed) {
      // Feed dashed lines in contour order so they do not restart at tessellation seams.
      positions.length = 0;
      let previous;
      let current = vertex;
      do {
        const next = [...current.neighbors].find((neighbor) => neighbor !== previous);
        current.point.toArray(positions, positions.length);
        next.point.toArray(positions, positions.length);
        previous = current;
        current = next;
      } while (current !== vertex);
    }
    const contour = { positions, center, width, height, closed };
    if (Math.max(width, height) >= 15) large.push(contour);
    else if (closed && diameter >= 2 && diameter <= 8 && component.length >= 6
      && Math.abs(width - height) <= diameter * 0.2
      && component.every(({ point }) => Math.abs(Math.hypot(point.x - center.x, point.y - center.y) - diameter / 2) <= diameter * 0.1)) {
      holes.push(contour);
    }
  }

  const [largest] = large.sort((a, b) => b.width * b.height - a.width * a.height);
  if (!largest) return { perimeter: [], interior: [], lug: null };
  const [perimeter] = large.filter((loop) => loop.width * loop.height >= largest.width * largest.height * 0.998)
    .sort((a, b) => Number(b.closed) - Number(a.closed) || b.center.z - a.center.z);
  const { center, width, height } = perimeter;
  const viewingArea = entry.row.part.evidence.find(({ field }) => field === "landscape_viewing_area_mm")?.value;
  const windowScore = (loop) => viewingArea
    ? Math.abs(loop.width - viewingArea[0]) + Math.abs(loop.height - viewingArea[1])
    : -loop.center.z;
  const [window] = large.filter((loop) => loop.width > width * 0.45 && loop.width < width * 0.95
    && loop.height > height * 0.45 && loop.height < height * 0.95
    && Math.abs(loop.center.x - center.x) < width * 0.1 && Math.abs(loop.center.y - center.y) < height * 0.1)
    .sort((a, b) => Number(b.closed) - Number(a.closed) || windowScore(a) - windowScore(b));
  const pitch = entry.row.part.evidence.find(({ field }) => field === "landscape_mount_pitch_mm")?.value;
  const mounts = [1, -1].flatMap((x) => [1, -1].map((y) => {
    const targetX = center.x + x * (pitch?.[0] ?? width) / 2;
    const targetY = center.y + y * (pitch?.[1] ?? height) / 2;
    const distance = (hole) => Math.hypot(hole.center.x - targetX, hole.center.y - targetY);
    return holes.filter((hole) => x * (hole.center.x - center.x) > width * 0.18
      && y * (hole.center.y - center.y) > height * 0.18).sort((a, b) => distance(a) - distance(b))[0];
  }));
  return {
    perimeter: perimeter.positions,
    interior: [window, ...mounts].flatMap((loop) => loop?.positions ?? []),
    lug: mounts[0]?.center,
  };
}

function makeEntries(assets, index, scene, resources, { base, target, focusPart }) {
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
        const { color, emissive, edgeColor } = materialFor(basis, row.delta);
        const solid = outline ? null : own(solidMaterial(basis, color, emissive));
        const baseColor = new THREE.Color(color);
        const gray = baseColor.r * 0.2126 + baseColor.g * 0.7152 + baseColor.b * 0.0722;
        const mutedColor = basis === "custom" ? new THREE.Color(0x6e685f)
          : baseColor.clone().lerp(new THREE.Color().setRGB(gray, gray, gray), 0.65).multiplyScalar(0.4);
        const fill = own(new THREE.MeshBasicMaterial({ color, transparent: true, depthWrite: false }));
        const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
        if (basis === "proxy") applyHatch(solid, 8, pixelRatio);
        entry = {
          row, basis, outline, group, vector, bounds: new THREE.Box3(),
          accentColor: new THREE.Color(edgeColor),
          displayEdges: row.part.part_id === focusPart ? [] : null,
          style: {
            solid, baseColor, mutedColor, fill,
            edge: {
              base: own(edgeMaterial(color, pattern, 1)),
              diff: ["added", "changed"].includes(row.delta) ? own(edgeMaterial(edgeColor, pattern, row.delta === "changed" ? 2 : 1.5)) : null,
              halo: row.delta === "changed" ? own(edgeMaterial(0x0e1116, null, 4)) : null,
              ghost: row.delta === "removed" ? own(edgeMaterial(DIFF_COLORS.removed, [5, 3], 1.5)) : null,
            },
            surface: [], lines: [], halos: [],
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

      const positions = edgePositions(geometry, 28);
      const line = featureLine(positions, style.edge.base, own);
      if (style.edge.halo) {
        const halo = new LineSegments2(line.geometry, style.edge.halo);
        halo.renderOrder = 1;
        line.renderOrder = 2;
        style.halos.push(halo);
        group.add(halo);
      }
      style.lines.push(line);
      group.add(line);

      if (entry.displayEdges) {
        entry.displayEdges.push(edgePositions(geometry, 40));
      } else if (revision === base && (row.delta === "changed"
        || index.byPart.get(`${target}:${row.part.part_id}`)?.delta === "changed"
        || index.byNode.get(target)?.get(row.part.node_name)?.some((part) => part.delta === "changed"))) {
        if (!entry.overlay) {
          const material = own(edgeMaterial(OLD_REVISION_RED, [5, 3], 1.5));
          const halo = own(edgeMaterial(0x0e1116, [5, 3], 3.5));
          halo.opacity = 0.5;
          material.depthTest = halo.depthTest = false;
          const object = new THREE.Group();
          object.visible = false;
          entry.overlay = { object, material, halo };
          scene.add(object);
        }
        const stroke = featureLine(positions, entry.overlay.material, own);
        const halo = new LineSegments2(stroke.geometry, entry.overlay.halo);
        halo.renderOrder = 3;
        stroke.renderOrder = 4;
        entry.overlay.object.add(halo, stroke);
      }
    });
  }
  for (const entry of entries.values()) {
    if (!entry.displayEdges) continue;
    const { perimeter, interior, lug } = displayContours(entry);
    delete entry.displayEdges;
    const removed = entry.row.revision === base;
    const color = removed ? DIFF_COLORS.removed : DIFF_COLORS.added;
    const rim = own(edgeMaterial(color, removed ? [5, 3] : null, 1.5));
    const details = own(edgeMaterial(color, removed ? [5, 3] : null, 1));
    const object = new THREE.Group();
    object.visible = false;
    if (perimeter.length) object.add(featureLine(perimeter, rim, own));
    if (interior.length) object.add(featureLine(interior, details, own));
    entry.displayOverlay = { object, rim, details, lug };
    scene.add(object);
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

function layoutAnnotations(host, camera, entries, width, height, canvasTop, panels, placeLabels, displayOpacity, showDimensions, { base, target, focusPart }) {
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
    const object = [entry?.displayOverlay?.object, entry?.overlay?.object, entry?.group].find((layer) => layer?.visible);
    return object?.visible ? entry.bounds.clone().translate(object.position) : null;
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
  function outlineFor(bounds) {
    if (!bounds) return null;
    const corners = [bounds.min.x, bounds.max.x].flatMap((x) =>
      [bounds.min.y, bounds.max.y].flatMap((y) =>
        [bounds.min.z, bounds.max.z].map((z) => project(new THREE.Vector3(x, y, z)))));
    if (corners.some((point) => !point)) return null;
    const xs = corners.map(({ x }) => x);
    const ys = corners.map(({ y }) => y);
    return {
      left: Math.min(...xs), right: Math.max(...xs),
      top: Math.min(...ys), bottom: Math.max(...ys),
    };
  }

  const occupied = panels.filter((panel) => panel.getClientRects().length).map(rectFor);
  const pinRects = [];
  const markers = [];
  const pinLeaders = [];
  const endpointPositions = new Map();
  const routeLabel = host.querySelector("[data-route-label]");
  const routeLeaders = host.querySelector("[data-route-leaders]");
  function mark(node, anchor, fixed = false) {
    const clear = (point) => point.x >= viewport.left + 12 && point.x <= viewport.right - 12
      && point.y >= viewport.top + 12 && point.y <= viewport.bottom - 12
      && !occupied.some((rect) => point.x > rect.left - 12 && point.x < rect.right + 12
        && point.y > rect.top - 12 && point.y < rect.bottom + 12)
      && markers.every((other) => Math.hypot(point.x - other.x, point.y - other.y) >= 24);
    let point = anchor;
    const collides = anchor && markers.some((other) => Math.hypot(anchor.x - other.x, anchor.y - other.y) < 24);
    if (anchor && (fixed ? collides : !clear(anchor))) {
      const angles = [0, 1, -1, 2, -2, 3, -3, 4].map((step) => step * Math.PI / 4);
      point = [36, 64, 92].flatMap((radius) => angles.map((angle) => ({
        x: anchor.x + radius * Math.cos(angle), y: anchor.y + radius * Math.sin(angle),
      }))).find(clear) ?? anchor;
      if (point !== anchor && !node.dataset.interfaceQuestion) {
        const dx = (point.x - anchor.x) / 3;
        const dy = (point.y - anchor.y) / 3;
        pinLeaders.push(fixed ? `M${anchor.x},${anchor.y}L${point.x},${point.y}`
          : `M${anchor.x + dx},${anchor.y + dy}l${dx},${dy}`);
      }
    }
    position(node, point);
    if (node.style.visibility === "visible") {
      markers.push(point);
      if (placeLabels || routeLabel) pinRects.push(rectFor(node));
      return point;
    }
  }
  for (const node of host.querySelectorAll("[data-endpoint-pin]")) {
    endpointPositions.set(node.dataset.endpointPin, mark(node, centerFor(node.dataset.pinAnchor)));
  }
  const from = endpointPositions.get("A");
  const to = endpointPositions.get("B");
  const midpoint = from && to ? { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 } : from ?? to;
  const footprint = host.querySelector("[data-footprint]");
  for (const node of host.querySelectorAll("[data-pin-anchor]:not([data-endpoint-pin]), [data-interface-question]")) {
    const display = footprint && entries.get(node.dataset.pinAnchor)?.displayOverlay;
    const lug = display?.lug && project(display.lug.clone().add(display.object.position));
    mark(node, node.dataset.interfaceQuestion ? midpoint : lug ?? centerFor(node.dataset.pinAnchor), Boolean(footprint));
  }
  host.querySelector("[data-pin-leaders]").setAttribute("d", pinLeaders.join(" "));
  if (routeLabel) {
    const point = midpoint && placeRoutingLabel(viewport, occupied, pinRects, midpoint,
      routeLabel.offsetWidth, routeLabel.offsetHeight);
    position(routeLabel, point);
    routeLeaders.setAttribute("d", point
      ? [from, to].filter(Boolean).map(({ x, y }) => `M${point.x},${point.y}L${x},${y}`).join(" ") : "");
    if (point) pinRects.push(rectFor(routeLabel));
  }

  if (footprint) {
    const older = entries.get(`${base}:part:${focusPart}`)?.bounds;
    const newer = entries.get(`${target}:part:${focusPart}`)?.bounds;
    const outlines = showDimensions && older && newer && [outlineFor(older), outlineFor(newer)];
    const visible = outlines && outlines.every(Boolean);
    const outer = visible && {
      left: Math.min(...outlines.map(({ left }) => left)), right: Math.max(...outlines.map(({ right }) => right)),
      top: Math.min(...outlines.map(({ top }) => top)), bottom: Math.max(...outlines.map(({ bottom }) => bottom)),
    };
    for (const [i, revision] of [base, target].entries()) {
      const group = host.querySelector(`[data-dimensions="${revision}"]`);
      const widthLabel = host.querySelector(`[data-dimension-label="${revision}width"]`);
      const heightLabel = host.querySelector(`[data-dimension-label="${revision}height"]`);
      group.style.visibility = widthLabel.style.visibility = heightLabel.style.visibility = visible ? "visible" : "hidden";
      if (!visible) continue;
      const { left, right, top, bottom } = outlines[i];
      const sign = i === 0 ? -1 : 1;
      const y = (i === 0 ? outer.top : outer.bottom) + sign * 16;
      const x = (i === 0 ? outer.left : outer.right) + sign * 16;
      const edgeY = i === 0 ? top : bottom;
      const edgeX = i === 0 ? left : right;
      group.querySelector("path").setAttribute("d",
        `M${left},${edgeY}V${y}H${right}V${edgeY} M${edgeX},${top}H${x}V${bottom}H${edgeX}`);
      const bounds = i === 0 ? older : newer;
      widthLabel.textContent = dimensionLabel(revision, bounds, "x");
      heightLabel.textContent = dimensionLabel(revision, bounds, "y");
      widthLabel.style.transform = `translate(${(left + right) / 2}px, ${y + sign * (widthLabel.offsetHeight / 2 + 3)}px)`;
      heightLabel.style.transform = `translate(${x + sign * (heightLabel.offsetWidth / 2 + 3)}px, ${(top + bottom) / 2}px)`;
    }
    if (visible) {
      footprint.querySelector("[data-footprint-delta]").textContent = footprintDelta(older, newer);
      const x = (outer.left + outer.right) / 2;
      const halfWidth = footprint.offsetWidth / 2;
      const clearance = Math.min(viewport.bottom, ...occupied.filter((rect) =>
        rect.top >= outer.bottom && rect.left < x + halfWidth && rect.right > x - halfWidth).map((rect) => rect.top));
      position(footprint, { x, y: Math.min(outer.bottom + 42, clearance - footprint.offsetHeight - 16) });
    } else {
      position(footprint, null);
    }
  }
  for (const path of host.querySelectorAll("[data-bracket]")) {
    const bounds = boundsForKey(path.dataset.bracket);
    const corners = bounds && [
      [bounds.min.x, bounds.min.y], [bounds.max.x, bounds.min.y],
      [bounds.max.x, bounds.max.y], [bounds.min.x, bounds.max.y],
    ].map(([x, y]) => project(new THREE.Vector3(x, y, bounds.max.z)));
    if (!corners || corners.some((point) => !point)) {
      path.removeAttribute("d");
      continue;
    }
    path.setAttribute("d", corners.map(({ x, y }, i) => {
      const along = (offset) => {
        const neighbor = corners[(i + offset + 4) % 4];
        const dx = neighbor.x - x;
        const dy = neighbor.y - y;
        const fraction = Math.min(1 / 3, 12 / Math.hypot(dx, dy));
        return `${x + dx * fraction},${y + dy * fraction}`;
      };
      return `M${along(-1)}L${x},${y}L${along(1)}`;
    }).join(" "));
  }

  const labels = [...host.querySelectorAll("[data-anchor]")];
  if (!labels.length) return;
  const outlines = placeLabels ? [...entries.keys()].map((key) => outlineFor(boundsForKey(key))).filter(Boolean) : [];
  const model = {
    left: Math.min(...outlines.map(({ left }) => left)),
    right: Math.max(...outlines.map(({ right }) => right)),
  };
  const callouts = placeLabels && labels.map((node) => {
    const endpoint = node.dataset.endpointLabel;
    const anchor = endpoint ? endpointPositions.get(endpoint) : centerFor(node.dataset.anchor);
    const outline = !endpoint && outlineFor(boundsForKey(node.dataset.anchor));
    return {
      anchor, model, width: node.offsetWidth, height: node.offsetHeight, elbow: true,
      leftAnchor: outline ? { ...anchor, x: outline.left } : anchor,
      rightAnchor: outline ? { ...anchor, x: outline.right } : anchor,
    };
  });
  const placements = callouts && placeCallouts(viewport, occupied, callouts, pinRects);
  const fallback = placements && placements.some((placement) => !placement)
    && placeCallouts(viewport, occupied, callouts.map((callout, i) => placements[i] ? {} : { ...callout, model: null }),
      [...pinRects, ...placements.flatMap((placement) => placement ? [placement.rect] : [])]);
  for (const [i, node] of labels.entries()) {
    const line = host.querySelector(`[data-leader="${i}"]`);
    node.style.opacity = line.style.opacity = displayOpacity;
    if (!placements) continue;
    const placement = placements[i] ?? fallback?.[i];
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

export function createFielddeckStage(host, assets, index, callbacks, sceneConfig) {
  const { base, target, focusPart } = sceneConfig;
  const scene = new THREE.Scene();
  const resources = new Set();
  const entries = makeEntries(assets, index, scene, resources, sceneConfig);
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
    [base]: all.filter(({ row }) => row.revision === base),
    [target]: all.filter(({ row }) => row.revision === target),
    compare: all.filter(({ row }) => row.revision === target || row.delta === "removed"),
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
  const key = new THREE.DirectionalLight(0xfff1e0, 2.08);
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
  const [header, bottomChrome, tree, inspector, sheet, legend, options] = [
    ".fd-header", ".fd-bottom", ".fd-tree", ".fd-inspector", ".fd-sheet", ".fd-legend", ".fd-options",
  ]
    .map((selector) => host.querySelector(selector));
  const panels = [header, bottomChrome, tree, inspector, sheet, legend, options];
  const mobileView = window.matchMedia(FIELDDECK_NARROW);
  const invalidateLayout = () => { layoutDirty = true; };

  function resize() {
    const nextWidth = Math.max(1, canvas.clientWidth);
    const nextHeight = Math.max(1, canvas.clientHeight);
    const phone = mobileView.matches;
    const { left: originX, top: originY } = host.getBoundingClientRect();
    const nextCanvasTop = canvas.offsetTop;
    const upper = Math.max(nextCanvasTop, header.getBoundingClientRect().bottom - originY,
      phone ? bottomChrome.getBoundingClientRect().bottom - originY : 0);
    const lowerPanels = phone ? [sheet, tree, inspector, legend] : [bottomChrome, legend];
    const lower = Math.min(nextHeight + nextCanvasTop, ...lowerPanels.filter((panel) => panel.getClientRects().length)
      .map((panel) => panel.getBoundingClientRect().top - originY));
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

  const displays = all.filter(({ row }) => row.part.part_id === focusPart);
  const displayBounds = boundsFor(displays, 0);

  function projectedPose(parts, direction, explode, { face = false, ghost } = {}) {
    const upAxis = face ? FACE_UP : UP;
    const fov = face ? 12 : baseFov;
    const right = upAxis.clone().cross(direction).normalize();
    const up = direction.clone().cross(right);
    const target = (face ? displayBounds : boundsFor(parts, explode)).getCenter(new THREE.Vector3());
    const points = [];
    for (const entry of ghost ? [...parts, ghost] : parts) {
      const layer = entry === ghost ? entries.get(config.selectedKeys[0]) ?? entry : entry;
      const offset = layer.vector.clone().multiplyScalar(typeof explode === "function" ? explode(layer) : explode).sub(target);
      for (const mesh of entry.style.surface) {
        const { min, max } = mesh.geometry.boundingBox;
        for (const x of [min.x, max.x]) {
          for (const y of [min.y, max.y]) {
            for (const z of [min.z, max.z]) {
              const point = new THREE.Vector3(x, y, z).add(offset);
              points.push({ x: point.dot(right), y: point.dot(up), depth: point.dot(direction) });
            }
          }
        }
      }
    }

    // Reserve more room below the face drawing for the delta and the phone controls.
    const topInset = Math.min(frameHeight / 4, face ? 46 : 32);
    const bottomInset = Math.min(frameHeight * (face ? 0.4 : 0.25), face ? (mobile ? 145 : 84) : 32);
    const rect = {
      left: -frameWidth / 2, right: frameWidth / 2,
      top: -frameHeight / 2 + topInset, bottom: frameHeight / 2 - bottomInset,
    };
    const centerY = (rect.top + rect.bottom) / 2;
    const margin = { x: Math.min(frameWidth / 3, face ? 50 : mobile ? 16 : 32), y: 0 };
    const focalPixels = height / (2 * Math.tan(THREE.MathUtils.degToRad(fov / 2)));
    let shiftX = 0;
    let shiftY = 0;
    function project(distance) {
      const bounds = { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity };
      for (const { x, y, depth } of points) {
        const scale = focalPixels / (distance - depth);
        const sx = (x - shiftX) * scale;
        const sy = (shiftY - y) * scale;
        bounds.left = Math.min(bounds.left, sx);
        bounds.right = Math.max(bounds.right, sx);
        bounds.top = Math.min(bounds.top, sy);
        bounds.bottom = Math.max(bounds.bottom, sy);
      }
      return bounds;
    }
    const near = points.reduce((distance, { depth }) => Math.max(distance, depth + camera.near), minimumDistance);
    function fitDistance() {
      let low = near;
      let high = near;
      const fits = (distance) => projectedFitScale(project(distance), rect, margin) >= 1;
      while (!fits(high)) high *= 2;
      for (let i = 0; i < 16; i++) {
        const middle = (low + high) / 2;
        if (fits(middle)) high = middle;
        else low = middle;
      }
      return high;
    }
    let distance = fitDistance();
    for (let i = 0; i < 3; i++) {
      const bounds = project(distance);
      shiftX += (bounds.left + bounds.right) / 2 * distance / focalPixels;
      shiftY += (centerY - (bounds.top + bounds.bottom) / 2) * distance / focalPixels;
      distance = fitDistance();
    }
    target.addScaledVector(right, shiftX).addScaledVector(up, shiftY);
    return { target, position: direction.clone().multiplyScalar(distance).add(target), fov, up: upAxis };
  }

  function facePose() {
    return projectedPose(displays, UP, 0, { face: true });
  }

  function assemblyPose(mode, explode) {
    const parts = modeEntries[mode].length ? modeEntries[mode] : all;
    const angle = TOUR_ANGLES[config.cameraCue?.stopIndex]
      ?? (config.selectedKeys.length >= 2 ? TOUR_ANGLES[1] : mode === "compare" ? TOUR_ANGLES[0] : 0);
    const direction = VIEW.clone().applyAxisAngle(UP, THREE.MathUtils.degToRad(angle));
    return projectedPose(parts, direction, explode, { ghost: entries.get(config.ghostDeltaKey) });
  }

  function moveCamera(pose, now, duration, ease) {
    cameraMove = { pose, start: now, duration, ease, from: camera.position.clone(), target: controls.target.clone() };
  }

  function setCamera({ position, target, fov = baseFov, up = UP }, amount = 1,
    from = camera.position, fromTarget = controls.target, faceTransition) {
    controls.maxDistance = Math.max(radius * 13, position.distanceTo(target));
    camera.far = controls.maxDistance + radius * 2;
    controls.target.lerpVectors(fromTarget, target, amount);
    if (amount === 1) {
      camera.position.copy(position);
    } else {
      const fromOffset = from.clone().sub(fromTarget);
      const toOffset = position.clone().sub(target);
      const direction = fromOffset.clone().normalize();
      const turn = new THREE.Quaternion().setFromUnitVectors(direction, toOffset.clone().normalize());
      direction.applyQuaternion(new THREE.Quaternion().slerp(turn, amount));
      camera.position.copy(direction.multiplyScalar(THREE.MathUtils.lerp(fromOffset.length(), toOffset.length(), amount))
        .add(controls.target));
    }
    if (faceTransition) {
      camera.up.lerpVectors(faceTransition.up, up, amount).normalize();
      fov = THREE.MathUtils.lerp(faceTransition.fov, fov, amount);
    } else {
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
    const { mode, heroStart, reduced, explode, explodeMotion, cameraCue, faceView, ghostDeltaKey, selectedKey } = config;
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
      const next = {
        base: Number(mode === base), target: Number(mode !== base), compare: Number(mode === "compare"),
      };
      blend = { mode, start: now, from: blend?.current ?? next, to: next, current: next };
    }
    const progress = clamp((now - blend.start) / (reduced ? 100 : 450));
    const mix = reduced ? progress : inOutCubic(progress);
    blend.current = {
      base: THREE.MathUtils.lerp(blend.from.base, blend.to.base, mix),
      target: THREE.MathUtils.lerp(blend.from.target, blend.to.target, mix),
      compare: THREE.MathUtils.lerp(blend.from.compare, blend.to.compare, mix),
    };
    const accentProgress = clamp((now - blend.start - (reduced ? 0 : 700)) / (reduced ? 100 : 180));
    dirty ||= progress < 1 || (mode === "compare" && accentProgress < 1);

    const cable = config.selectedKeys.length >= 2;
    const selectionChanged = config.selectedKeys.join() !== lastConfig?.selectedKeys.join();
    const newCue = cameraCue && cameraCue !== latestCue;
    if (heroElapsed !== null) {
      setCamera(assemblyPose(mode, offsetFor));
    } else if (faceView !== Boolean(lastConfig?.faceView)) {
      if (faceView && !priorCamera) priorCamera = { position: camera.position.clone(), target: controls.target.clone() };
      const pose = faceView ? facePose()
        : newCue || selectionChanged || mode !== lastConfig.mode ? assemblyPose(mode, offsetFor) : priorCamera;
      if (!faceView) latestCue = cameraCue;
      moveCamera(pose, now, 240, inOutCubic);
      cameraMove.faceTransition = { up: camera.up.clone(), fov: camera.fov };
    } else if (faceView) {
      if (resized || selectionChanged || mode !== lastConfig.mode || explode !== lastConfig.explode) {
        priorCamera = assemblyPose(mode, offsetFor);
      }
      if (resized) {
        const pose = facePose();
        if (cameraMove) cameraMove.pose = pose;
        else setCamera(pose);
      }
    } else if (!cameraMove?.faceTransition) {
      if (newCue) {
        latestCue = cameraCue;
        moveCamera(assemblyPose(mode, offsetFor), now, 1600, damped);
      } else if (firstFrame || lastHero !== null || resized || mobile && (selectionChanged || mode !== lastConfig.mode)) {
        cameraMove = null;
        setCamera(assemblyPose(mode, offsetFor));
      } else if (mode !== lastConfig.mode) {
        moveCamera(assemblyPose(mode, offsetFor), now, 450, inOutCubic);
      } else if (selectionChanged) {
        moveCamera(assemblyPose(mode, offsetFor), now, 240, outCubic);
      } else if (explodeMotion) {
        const pose = assemblyPose(mode, offsetFor);
        if (cameraMove) cameraMove.pose = pose;
        else setCamera(pose, reduced ? 1 : 1 - Math.exp(-tick / 85));
        dirty = true;
      } else if (explode !== lastConfig.explode || lastConfig.explodeMotion) {
        cameraMove = null;
        setCamera(assemblyPose(mode, explode));
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
    const displaySelected = config.selectedKeys.some((key) => entries.get(key)?.row.part.part_id === focusPart);
    for (const entry of all) {
      const { row, group, vector } = entry;
      const removed = row.revision === base && row.delta === "removed";
      const ghost = removed && (mode === "compare" || blend.current.compare > 0);
      const ghostOpacity = selectedKey && !displaySelected && entry.displayOverlay ? 0.3 : 1;
      const weight = row.revision === target ? blend.current.target
        : ghost ? Math.max(blend.current.base, blend.current.compare) * displayOpacity * ghostOpacity : blend.current.base;
      if (entry.overlay) {
        const { object, material, halo } = entry.overlay;
        object.visible = !faceView && row.key === ghostDeltaKey;
        if (object.visible) {
          // Apply the selected layer's presentation offset to both CAD transforms.
          const selected = entries.get(selectedKey);
          if (selected) object.position.copy(selected.vector).multiplyScalar(offsetFor(selected));
          scaleDashes(material, entry, object.position);
          scaleDashes(halo, entry, object.position);
        }
      }
      if (entry.displayOverlay) {
        const { object, rim, details } = entry.displayOverlay;
        object.visible = faceView || ghost && weight > 0.001;
        if (object.visible) {
          object.position.copy(vector).multiplyScalar(faceView ? 0 : offsetFor(entry));
          rim.opacity = faceView ? 1 : weight;
          details.opacity = faceView ? 0.2 : weight;
          scaleDashes(rim, entry, object.position);
          scaleDashes(details, entry, object.position);
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
      const selected = selectedKey === row.key;
      const accent = selected && ghostDeltaKey ? 1 : (reduced ? accentProgress : outCubic(accentProgress)) * blend.current.compare;
      const material = stylePart(entry, blend.current.compare, weight, ghost, entry.style.edge.diff ? accent : 0, selected);
      scaleDashes(material, entry, group.position);
      const casts = entry.style.surface[0].castShadow;
      contactDirty ||= casts !== wasCasting || casts && moved;
      if (casts) floor = Math.min(floor, entry.bounds.min.z + group.position.z);
      if (row.revision === (mode === "compare" ? target : mode) || mode === "compare" && ghost) {
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
      layoutAnnotations(host, camera, entries, width, height, canvasTop, panels, placeLabels, displayOpacity, !cameraMove, sceneConfig);
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
    update: (next) => { config = next; resize(); },
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
