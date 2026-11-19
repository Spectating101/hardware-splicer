import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Line2 } from "three/examples/jsm/lines/Line2.js";
import { LineGeometry } from "three/examples/jsm/lines/LineGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { mergeVertices, toCreasedNormals } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { HorizontalBlurShader } from "three/examples/jsm/shaders/HorizontalBlurShader.js";
import { VerticalBlurShader } from "three/examples/jsm/shaders/VerticalBlurShader.js";
import {
  BlendFunction, Effect, EffectComposer, EffectPass, RenderPass,
  SMAAEffect, SMAAPreset, ToneMappingEffect, ToneMappingMode,
} from "postprocessing";
import { N8AOPostPass } from "n8ao";
import { fielddeckSceneUrl } from "../api.js";
import {
  bracketPath, chooseTier, CREASE_INK, DIMMED_VENDOR, pairMovedFeatures, closedEdgeLoops, cullIsolatedChains, totalChainLength, classifyPart, convexHull, cullCoincidentChains, DEFAULT_EXPLODE, diffAccentChains,
  DIFF_COLORS, explodeGroupOffsets, FIELDDECK_NARROW, footprintDeltaPair, ghostDeltaKey,
  ghostOutlineLoops, materialSpec, repelPins, meshMeasures, nearestPoint, placeBesideEndpoint, placeCallouts,
  projectedFitScale, QUALITY_SAMPLE_COUNT, rowForNode, weldEdgeChains,
  FACE_APERTURE_PARTS, formatEvidenceValue, formatGapValue, halfGapLabel, linearDimension, minimumSideGap,
  perHalfGaps, projectedSideGaps, sectionSegments, seamLabel, vertexCentroid,
} from "./fielddeckLogic.js";

const TOUR_ANGLES = [18, -5, 24];
const CONTACT_LAYER = 1;
const EXPOSURE = 0.92;
const TIERS = {
  high: { dpr: 2, shadowSize: 2048 },
  standard: { dpr: 1.25, shadowSize: 1024 },
  reduced: { dpr: 1, shadowSize: 0 },
};
const UP = new THREE.Vector3(0, 0, 1);
const VIEW = new THREE.Vector3(8.2, -9.6, 9.1).normalize();
const clamp = (n) => Math.min(1, Math.max(0, n));
const outCubic = (t) => 1 - (1 - t) ** 3;
const inOutCubic = (t) => t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
const FACE_UP = new THREE.Vector3(0, 1, 0);
const FACE_FOV = 4;
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

function solidMaterial({ color, roughness, metalness }) {
  return new THREE.MeshStandardMaterial({
    color, metalness, roughness,
    polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
  });
}

function applyHatch(material, { angle, spacing, contrast }, pixelRatio) {
  material.onBeforeCompile = (shader) => {
    const radians = THREE.MathUtils.degToRad(angle);
    shader.uniforms.hatchDirection = { value: new THREE.Vector2(-Math.sin(radians), Math.cos(radians)) };
    shader.uniforms.hatchStep = { value: spacing };
    shader.uniforms.hatchContrast = { value: contrast };
    shader.uniforms.hatchDpr = pixelRatio;
    shader.fragmentShader = shader.fragmentShader.replace("#include <common>",
      "#include <common>\nuniform vec2 hatchDirection;\nuniform float hatchStep, hatchContrast, hatchDpr;");
    shader.fragmentShader = shader.fragmentShader.replace("#include <color_fragment>", `
      #include <color_fragment>
      float hatch = step(0.8, fract(dot(gl_FragCoord.xy, hatchDirection) / (hatchStep * hatchDpr)));
      diffuseColor.rgb *= 1.0 - hatch * hatchContrast;
    `);
  };
}

function edgeMaterial(color, pattern, linewidth) {
  const material = new LineMaterial({
    color, linewidth, dashed: Boolean(pattern), dashSize: pattern?.[0] ?? 1, gapSize: pattern?.[1] ?? 1,
    // No alphaToCoverage: without MSAA it turned every partial opacity into a solid line, so 50%
    // and 35% strokes drew at full strength.
    worldUnits: false, transparent: true, depthWrite: false, toneMapped: false, alphaToCoverage: false,
    polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
  });
  // Widths are CSS pixels. applyTier scales them by the drawing-buffer ratio so a 1.5 px line
  // stays 1.5 px after the browser downsamples a DPR 2 canvas, instead of a soft 0.75 px fringe.
  material.userData.cssWidth = linewidth;
  if (pattern) {
    material.onBeforeCompile = (shader) => {
      // Interpolate the projected distance in screen space, including on slanted edges.
      shader.vertexShader = shader.vertexShader.replace("#include <fog_vertex>",
        "vLineDistance *= gl_Position.w;\n#include <fog_vertex>");
      shader.fragmentShader = shader.fragmentShader.replace(/vLineDistance(?=\s*\+\s*dashOffset)/g,
        "(vLineDistance * gl_FragCoord.w)");
    };
  }
  return material;
}

// Change colour draws each pixel once (stencil), so parallel edges that overlap on screen do
// not stack a 50% stroke back up to full strength.
// An added part whose shape is unknown still reads as added: a teal 1.5 px outline of its end
// loops. It draws before the violet strokes and wins the shared stencil where an added cap meets
// a changed part, so the two colours never merge into one ring.
function addedOutlineMaterial() {
  const material = diffMaterial(DIFF_COLORS.added, 1.25);
  material.polygonOffsetFactor = material.polygonOffsetUnits = -2;
  return material;
}

function diffMaterial(color, width = 1.5) {
  const material = edgeMaterial(color, null, width);
  Object.assign(material, {
    stencilWrite: true, stencilRef: 1, stencilFunc: THREE.NotEqualStencilFunc,
    stencilZPass: THREE.ReplaceStencilOp, stencilFail: THREE.KeepStencilOp, stencilZFail: THREE.KeepStencilOp,
  });
  return material;
}

const STAGE_BACKGROUND = new THREE.Color(0x0e1116);
// Compare focus: a part above the selection that overlaps it goes to a neutral veil.
const FADED_VEIL = new THREE.Color(0x8e8b85);
const FADED_OPACITY = 0.14;
const UNKNOWN_BODY = 0xa3a29d;

function stylePart(entry, compare, weight, ghost, accent, emphasis, focus = null) {
  const { outline, row } = entry;
  const { solid, baseColor, mutedColor, fill, edge, surface, lines, accents } = entry.style;
  const translucent = outline || ghost;
  const dimming = row.delta === "unchanged" ? compare : 0;
  if (fill) fill.opacity = weight * entry.spec.fillOpacity;
  if (solid) {
    solid.color.copy(baseColor).lerp(mutedColor, dimming);
    // Compare focus: parts that recede shift 40% toward the stage background.
    if (focus?.recede) solid.color.lerp(STAGE_BACKGROUND, focus.recede);
    // A settled solid is fully opaque; only a revision cross-fade, or a part above the selection
    // that overlaps it on screen (a neutral 14% veil, no depth write), is ever blended.
    const faded = Boolean(focus?.fade);
    if (faded) solid.color.copy(FADED_VEIL);
    const transparent = weight < 0.999 || faded;
    solid.opacity = faded ? weight * FADED_OPACITY : transparent ? weight : 1;
    if (solid.transparent !== transparent) {
      solid.transparent = transparent;
      solid.needsUpdate = true;
    }
    solid.depthWrite = faded ? false : !transparent || weight > 0.55;
  }

  // Unchanged parts in Compare take their edges to 25%.
  const edgeOpacity = outline ? entry.outlineOpacity ?? 1 : entry.spec.creaseOpacity;
  edge.base.opacity = weight * THREE.MathUtils.lerp(edgeOpacity, Math.min(edgeOpacity, 0.25), dimming)
    * (outline && row.delta === "added" ? emphasis : 1);
  if (edge.diff) edge.diff.opacity = weight * accent * emphasis * (entry.accentScale ?? 1);
  if (focus) {
    // Everything but the selection keeps its edges at 20%.
    edge.base.opacity = Math.min(edge.base.opacity, 0.2 * weight);
    if (edge.diff) edge.diff.opacity = Math.min(edge.diff.opacity, 0.2 * weight);
  }
  // A faded occluder draws no creases: only its outer silhouette in ink at 25%, behind a
  // front-face depth pre-pass so its own hidden loops and internal edges stay hidden.
  const veiled = Boolean(focus?.fade) && !ghost;
  if (entry.veil) {
    entry.veil.prepass.visible = entry.veil.silhouette.visible = veiled;
    entry.veil.material.opacity = 0.25 * weight;
  }

  for (const mesh of surface) {
    mesh.visible = Boolean(solid || fill) && !ghost;
    mesh.castShadow = !translucent && weight >= 0.49;
    // Part-on-part key shadows separate the stacked layers; the frustum is fitted to the model.
    mesh.receiveShadow = !translucent;
    if (mesh.castShadow) mesh.layers.enable(CONTACT_LAYER);
    else mesh.layers.disable(CONTACT_LAYER);
  }
  lines.forEach((line) => { line.visible = !ghost && !veiled; });
  accents.forEach((line) => { line.visible = !ghost && !veiled && accent > 0; });
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
  if (material.dashed) line.computeLineDistances();
  return line;
}

function chainSegments(chains) {
  const positions = [];
  for (const points of chains) {
    for (let i = 1; i < points.length; i++) positions.push(...points[i - 1], ...points[i]);
  }
  return positions;
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

// Removed and old-revision geometry: a screen-space 6/4 dash, 1.25 px, #F17E70. Small closed
// old-revision loops (AABB under 6 mm) are solid 1 px circles at 40%, never dashed fragments.
function makeGhost(chains, own, { xray = false } = {}) {
  const object = new THREE.Group();
  const material = own(edgeMaterial(DIFF_COLORS.removed, [6, 4], 1.25));
  // Old rims of small features (standoffs, holes) are coral dashed circles, 1.25 px, 6/4.
  const small = own(edgeMaterial(DIFF_COLORS.removed, [6, 4], 1.25));
  // The old revision often lies inside the current solid; draw it through so the change is visible.
  if (xray) material.depthTest = small.depthTest = false;
  const loops = xray ? closedEdgeLoops(chainSegments(chains), 0.01).filter(({ min, max }) =>
    Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]) < 6) : [];
  const inSmallLoop = (points) => loops.some(({ min, max }) => points.every((point) =>
    point.every((value, axis) => value >= min[axis] - 0.01 && value <= max[axis] + 0.01)));
  const add = (points, lineMaterial) => {
    const geometry = own(new LineGeometry());
    geometry.setPositions(points.flat());
    const line = new Line2(geometry, lineMaterial);
    if (lineMaterial.dashed) line.computeLineDistances();
    line.renderOrder = 3;
    object.add(line);
  };
  loops.forEach(({ points }) => add(points, small));
  const outlineChains = chains.filter((points) => points.length >= 2 && !inSmallLoop(points));
  outlineChains.forEach((points) => add(points, material));
  object.visible = false;
  return {
    object,
    // Old geometry drawn outside the small feature loops: what "old outline" may claim.
    outlineLength: totalChainLength(outlineChains),
    // Small old features, for centre crosses and moved-feature leaders in the annotation layer.
    features: loops.map(({ min, max }) => ({
      center: [0, 1, 2].map((axis) => (min[axis] + max[axis]) / 2),
      size: Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]),
    })),
    setOpacity(weight) {
      material.opacity = weight * 0.7;
      small.opacity = weight * 0.7;
    },
  };
}

function makeEntries(assets, index, scene, technical, resources, { base, target, focusPart }) {
  const entries = new Map();
  let veilPrepassMaterial = null;
  let pickOnlyMaterial = null;
  let capInk = null;
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
        const spec = materialSpec(basis, row.delta);
        const group = new THREE.Group();
        const strokes = new THREE.Group();
        const vector = new THREE.Vector3();
        // An added part of unknown shape still has a body: a plain neutral solid that claims no
        // shape source. Its teal is the outline alone.
        const addedBody = outline && basis === "unknown" && row.delta === "added";
        const solid = outline && !addedBody ? null
          : own(solidMaterial(addedBody ? { ...spec, color: UNKNOWN_BODY, roughness: 0.85 } : spec));
        const baseColor = new THREE.Color(addedBody ? UNKNOWN_BODY : spec.color ?? spec.edgeColor);
        if (basis === "envelope" && row.part.geometry_basis === "donor_cad") {
          baseColor.lerp(new THREE.Color(materialSpec("donor_cad").color), 0.4);
        }
        const mutedColor = new THREE.Color(addedBody ? UNKNOWN_BODY : materialSpec(basis, row.delta, true).color ?? spec.edgeColor);
        // Rubber feet read as the dimmed vendor grey in every mode, never as near-white plastic.
        if (row.part.part_id.startsWith("foot-")) {
          baseColor.setHex(DIMMED_VENDOR);
          mutedColor.setHex(DIMMED_VENDOR);
        }
        const fill = spec.fillOpacity ? own(new THREE.MeshBasicMaterial({
          color: baseColor, transparent: true, depthWrite: false, toneMapped: false,
        })) : null;
        const hatchDpr = { value: 1 };
        if (spec.hatch) applyHatch(solid, spec.hatch, hatchDpr);
        const accent = !outline && ["added", "changed"].includes(row.delta);
        const paired = row.delta === "changed" ? ghostDeltaKey(index, "compare", row, { base, target }) : null;
        entry = {
          row, basis, outline, spec, group, strokes, vector, hatchDpr, bounds: new THREE.Box3(),
          meshStats: { volume: 0, area: 0 }, samples: [],
          ghostEdges: row.delta === "removed" || paired ? [] : null, paired,
          displayEdges: row.part.part_id === focusPart ? [] : null,
          style: {
            solid, baseColor, mutedColor, fill,
            edge: {
              base: outline && row.delta === "added" ? own(addedOutlineMaterial())
                : own(edgeMaterial(outline ? baseColor : spec.creaseColor, spec.pattern, basis === "unknown" ? 1.25 : 1)),
              diff: accent ? own(diffMaterial(spec.edgeColor)) : null,
            },
            surface: [], lines: [], accents: [],
          },
        };
        entries.set(row.key, entry);
        scene.add(group);
        technical.add(strokes);
      }

      // Bake the GLB's node hierarchy into mm so presentation offsets remain in scene axes.
      let geometry = source.geometry.clone().applyMatrix4(new THREE.Matrix4().multiplyMatrices(scale, source.matrixWorld));
      // Weld coincident vertices at 1e-4 mm first, so a smooth cylinder wall has no seam crease.
      if (geometry.getAttribute("color")) geometry.deleteAttribute("color");
      const welded = mergeVertices(geometry, 1e-4);
      if (welded !== geometry) geometry.dispose();
      geometry = welded;
      if (!geometry.getAttribute("normal")) {
        // The GLBs carry no normals. Smoothing shared vertices across 90° edges tilts the normals of
        // flat faces and streaks every triangle fan, so split normals at a 30° crease instead.
        const creased = toCreasedNormals(geometry, THREE.MathUtils.degToRad(30));
        if (creased !== geometry) geometry.dispose();
        geometry = creased;
      }
      own(geometry);
      geometry.computeBoundingBox();
      entry.bounds.union(geometry.boundingBox);
      const vertices = geometry.getAttribute("position");
      const { volume, area } = meshMeasures(vertices.array, geometry.index?.array);
      entry.meshStats.volume += volume;
      entry.meshStats.area += area;
      // A bounded sample of the part's own vertices, for tight screen boxes and silhouette anchors.
      const stride = Math.max(1, Math.ceil(vertices.count / 2500));
      for (let i = 0; i < vertices.count; i += stride) entry.samples.push(vertices.getX(i), vertices.getY(i), vertices.getZ(i));
      const { style, group, strokes } = entry;
      // An unknown shape has no surface material: its mesh stays for picking and draws nothing,
      // so an added spacer reads by its teal outline, not as a filled teal blob.
      const mesh = new THREE.Mesh(geometry, style.solid ?? style.fill ?? (pickOnlyMaterial ??= own(new THREE.MeshBasicMaterial({
        colorWrite: false, depthWrite: false, transparent: true,
      }))));
      style.surface.push(mesh);
      if (entry.outline && !style.solid) strokes.add(mesh);
      else group.add(mesh);

      const positions = edgePositions(geometry, entry.spec.threshold);
      if (positions.length && style.edge.base.dashed) {
        // Unknown shapes show their outer loop only. A dotted loop on a part a few millimetres across
        // reads as grey stipple, so a short loop is drawn as one thin, quieter stroke instead.
        const chains = entry.basis === "unknown"
          ? ghostOutlineLoops(positions, { maxChains: entry.row.delta === "added" ? 2 : 1, stacked: entry.row.delta === "added" })
          : weldEdgeChains(positions);
        if (entry.basis === "unknown" && entry.row.delta !== "added" && chains.length && chains.every((points) => points.length < 2
          || points.slice(1).reduce((sum, point, i) => sum + Math.hypot(...point.map((v, k) => v - points[i][k])), 0) < 40)) {
          style.edge.base = own(edgeMaterial(style.baseColor, null, 1));
          entry.outlineOpacity = 0.55;
        }
        if (entry.basis === "unknown" && entry.row.delta === "added") {
          // End caps and other creases of an added unknown part stay in ink at 25%.
          capInk ??= own(Object.assign(edgeMaterial(CREASE_INK, null, 1), { opacity: 0.25 }));
          const caps = featureLine(positions, capInk, own);
          style.lines.push(caps);
          strokes.add(caps);
        }
        for (const points of chains) {
          const chain = own(new LineGeometry());
          chain.setPositions(points.flat());
          const line = new Line2(chain, style.edge.base);
          line.renderOrder = 1;
          if (line.material.dashed) line.computeLineDistances();
          style.lines.push(line);
          strokes.add(line);
        }
      } else if (positions.length) {
        const line = featureLine(positions, style.edge.base, own);
        style.lines.push(line);
        strokes.add(line);
      }
      if (style.edge.diff) {
        // Added parts carry their outer outline only. Changed parts carry their outline and large
        // boundary loops; vent slots, small cutouts, hole rims and smooth walls stay in ink.
        // Changed parts get violet after both revisions load, only where geometry differs; their
        // outline is kept as the fallback when nothing measurable differs.
        if (entry.row.delta === "changed") {
          entry.outlineAccent = (entry.outlineAccent ?? []).concat(diffAccentChains(edgePositions(geometry, 60),
            geometry.boundingBox.getSize(new THREE.Vector3()).toArray()));
        }
        const chains = entry.row.delta === "added" ? ghostOutlineLoops(positions, { maxChains: 1 }) : [];
        if (chains.length) {
          const line = featureLine(chainSegments(chains), style.edge.diff, own);
          line.renderOrder = 2;
          style.accents.push(line);
          strokes.add(line);
        }
      }
      if (style.solid) {
        if (!entry.veil) {
          const prepass = new THREE.Group();
          const silhouette = new THREE.Group();
          // Pre-pass and silhouette draw last in the overlay, so other parts' lines are unaffected.
          prepass.visible = silhouette.visible = false;
          entry.veil = { prepass, silhouette, material: own(edgeMaterial(CREASE_INK, null, 1)) };
          strokes.add(prepass, silhouette);
        }
        const depthOnly = new THREE.Mesh(geometry, veilPrepassMaterial ??= own(new THREE.MeshBasicMaterial({
          colorWrite: false, depthWrite: true, transparent: true, side: THREE.FrontSide,
        })));
        depthOnly.renderOrder = 10;
        entry.veil.prepass.add(depthOnly);
        const loops = ghostOutlineLoops(positions, { maxChains: 2 });
        if (loops.length) {
          const outline = featureLine(chainSegments(loops), entry.veil.material, own);
          outline.renderOrder = 11;
          entry.veil.silhouette.add(outline);
        }
      }
      if (entry.ghostEdges) {
        for (const value of positions) entry.ghostEdges.push(value);
      }
      if (entry.displayEdges) entry.displayEdges.push(edgePositions(geometry, 40));
    });
  }
  for (const entry of entries.values()) {
    entry.samples = new Float32Array(entry.samples);
    const pairedEdges = entry.paired && entries.get(entry.paired)?.ghostEdges;
    if (entry.style.edge.diff && entry.row.delta === "changed" && entry.row.revision === target && pairedEdges) {
      // Diff-only violet: the ghost-culling coincidence test, run against the old revision.
      let chains = cullIsolatedChains(cullCoincidentChains(weldEdgeChains(entry.ghostEdges), pairedEdges));
      if (totalChainLength(chains) <= 3) {
        // Nothing measurable differs: one 1 px violet silhouette at 60% still marks the part as changed.
        chains = entry.outlineAccent ?? [];
        entry.style.edge.diff.userData.cssWidth = 1;
        entry.accentScale = 0.6;
      }
      entry.diffLength = totalChainLength(chains);
      entry.diffChains = chains;
      if (chains.length) {
        const line = featureLine(chainSegments(chains), entry.style.edge.diff, own);
        line.renderOrder = 2;
        entry.style.accents.push(line);
        entry.strokes.add(line);
      }
    }
    delete entry.outlineAccent;
    if (entry.ghostEdges && entry.row.revision === base) {
      if (entry.row.delta === "removed") {
        // The outer silhouette and at most one inner loop, never the PCB, FPC and tab edges.
        entry.removed = makeGhost(ghostOutlineLoops(entry.ghostEdges), own);
        technical.add(entry.removed.object);
      } else {
        const current = entries.get(entry.paired)?.ghostEdges ?? [];
        // Compare the original geometry before simplification can turn a matched arc into a chord.
        const chains = cullIsolatedChains(cullCoincidentChains(weldEdgeChains(entry.ghostEdges), current, { simplify: true }));
        entry.overlay = makeGhost(chains, own, { xray: true });
        // What the scene label may claim: the length of old-revision geometry actually drawn.
        entry.overlay.length = entry.overlay.outlineLength;
        technical.add(entry.overlay.object);
      }
    }
    if (!entry.displayEdges) continue;
    const { perimeter, interior, lug } = displayContours(entry);
    delete entry.displayEdges;
    const removed = entry.row.revision === base;
    const color = removed ? DIFF_COLORS.removed : DIFF_COLORS.added;
    const rim = own(edgeMaterial(color, removed ? [6, 4] : null, 1.5));
    const details = own(edgeMaterial(color, removed ? [6, 4] : null, 1));
    const object = new THREE.Group();
    object.visible = false;
    if (perimeter.length) object.add(featureLine(perimeter, rim, own));
    if (interior.length) object.add(featureLine(interior, details, own));
    entry.displayOverlay = { object, rim, details, lug };
    technical.add(object);
  }
  for (const entry of entries.values()) {
    // A moved old feature gets a leader to its new position only when the match is unambiguous.
    const newer = entry.overlay && entries.get(entry.paired)?.diffChains;
    if (newer) {
      const features = closedEdgeLoops(chainSegments(newer), 0.01).map(({ min, max }) => ({
        center: [0, 1, 2].map((axis) => (min[axis] + max[axis]) / 2),
        size: Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]),
      })).filter(({ size }) => size < 6);
      entry.overlay.pairs = pairMovedFeatures(entry.overlay.features, features);
    }
  }
  for (const entry of entries.values()) {
    delete entry.ghostEdges;
    delete entry.diffChains;
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

function triangleSoup(entry) {
  const soup = [];
  for (const mesh of entry.style.surface) {
    const position = mesh.geometry.getAttribute("position");
    const index = mesh.geometry.index;
    const count = index ? index.count : position.count;
    for (let i = 0; i < count; i++) {
      const vertex = index ? index.getX(i) : i;
      soup.push(position.getX(vertex), position.getY(vertex), position.getZ(vertex));
    }
  }
  return soup;
}

// Face view fit layer, in assembled coordinates (explode 0). The display face is the XY plane, so
// the faceplate is sectioned at its mid-thickness in Z and everything is projected onto XY.
function computeFaceFit(entries, { target, focusPart }) {
  const display = entries.get(`${target}:part:${focusPart}`);
  if (!display) return null;
  const centre = [(display.bounds.min.x + display.bounds.max.x) / 2, (display.bounds.min.y + display.bounds.max.y) / 2];
  const soup = triangleSoup(display);
  const points = [];
  for (let i = 0; i < soup.length; i += 3) points.push({ x: soup[i], y: soup[i + 1] });
  const outline = convexHull(points).map(({ x, y }) => [x, y]);
  const faces = FACE_APERTURE_PARTS.map((id) => entries.get(`${target}:part:${id}`));
  let level = null;
  let fit = { gaps: projectedSideGaps(outline, null, centre), seam: null, inner: [] };
  if (faces.every(Boolean)) {
    const bounds = boundsFor(faces, 0);
    level = (bounds.min.z + bounds.max.z) / 2;
    // Each half is measured on its own: the halves need not close into one aperture loop.
    fit = perHalfGaps(outline, faces.map((entry) => ({
      label: entry.row.part.label,
      side: (entry.bounds.min.x + entry.bounds.max.x) / 2 < centre[0] ? "left" : "right",
      segments: sectionSegments(triangleSoup(entry), level),
    })), centre);
  }
  const { gaps, seam, inner } = fit;
  const spacers = [...entries.values()]
    .filter(({ row }) => row.revision === target && row.part.part_id.startsWith("display-spacer-"))
    .map((entry) => ({ key: entry.row.key, point: vertexCentroid(triangleSoup(entry)) }))
    .filter(({ point }) => point);
  return { level, centre, outline, gaps, seam, inner, minimum: minimumSideGap(gaps), spacers, top: display.bounds.max.z };
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

function createContactShadow(scene, bounds, resources) {
  const size = 512;
  const center = bounds.getCenter(new THREE.Vector3());
  const spread = bounds.getSize(new THREE.Vector3());
  const width = spread.x + 100;
  const height = spread.y + 100;
  const target = new THREE.WebGLRenderTarget(size, size);
  const blurTarget = new THREE.WebGLRenderTarget(size, size, { depthBuffer: false });
  const bakes = [1.4, 0.5, 0.25].map((blur) => ({
    blur, target: new THREE.WebGLRenderTarget(size, size, { depthBuffer: false }),
  }));
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
  vertical.uniforms.tDiffuse.value = blurTarget.texture;
  const quad = new THREE.Mesh(quadGeometry, horizontal);
  blurScene.add(quad);

  // Looking up from the ground mirrors the X axis in the captured texture.
  const groundGeometry = new THREE.PlaneGeometry(width, height);
  const ground = bakes.map(({ target }, i) => {
    target.texture.repeat.x = -1;
    target.texture.offset.x = 1;
    const material = new THREE.MeshBasicMaterial({
      map: target.texture, transparent: true, depthWrite: false, opacity: i === 2 ? 0.55 : 0.45, toneMapped: false,
    });
    resources.add(target);
    resources.add(material);
    const mesh = new THREE.Mesh(groundGeometry, material);
    mesh.renderOrder = -1;
    return mesh;
  });
  const poolMaterial = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, toneMapped: false,
    uniforms: { tint: { value: new THREE.Color(0xc9c3b8) } },
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
        // A ring of light around the footprint, so the floor under the assembly stays darker.
        float r = length(floorUv * 2.0 - 1.0);
        float ring = smoothstep(0.3, 0.55, r) * (1.0 - smoothstep(0.55, 1.0, r));
        gl_FragColor = vec4(tint, 0.1 * ring);
        #include <colorspace_fragment>
      }`,
  });
  const pool = new THREE.Mesh(quadGeometry, poolMaterial);
  pool.scale.set(width * 1.1, height * 1.1, 1);
  pool.renderOrder = -2;
  // A soft shadow pool under the assembly footprint: about 9% darker, fading out past its edge.
  const shadowPoolMaterial = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, toneMapped: false,
    vertexShader: `
      varying vec2 floorUv;
      void main() {
        floorUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      varying vec2 floorUv;
      void main() {
        vec2 p = abs(floorUv * 2.0 - 1.0);
        float d = pow(pow(p.x, 4.0) + pow(p.y, 4.0), 0.25);
        gl_FragColor = vec4(0.0, 0.0, 0.0, 0.5 * (1.0 - smoothstep(0.7, 1.0, d)));
      }`,
  });
  const shadowPool = new THREE.Mesh(quadGeometry, shadowPoolMaterial);
  shadowPool.scale.set(spread.x * 0.9, spread.y * 0.9, 1);
  shadowPool.renderOrder = -1.5;
  // The key light's own shadow on the floor, inside the light pool, so the assembly sits down.
  // It spans the scene bounds × 1.2 and fades radially to zero, so it never shows a hard edge.
  const keyFloorMaterial = new THREE.ShadowMaterial({ opacity: 0.3, depthWrite: false });
  keyFloorMaterial.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader.replace("void main() {", "varying vec2 floorLocal;\nvoid main() {\n  floorLocal = position.xy;");
    shader.fragmentShader = shader.fragmentShader.replace("void main() {", "varying vec2 floorLocal;\nvoid main() {")
      .replace("gl_FragColor = vec4( color, opacity * ( 1.0 - getShadowMask() ) );",
        "gl_FragColor = vec4( color, opacity * ( 1.0 - getShadowMask() ) * ( 1.0 - smoothstep( 0.35, 1.0, length( floorLocal ) ) ) );");
  };
  const keyFloor = new THREE.Mesh(quadGeometry, keyFloorMaterial);
  keyFloor.scale.set(spread.x * 0.6, spread.y * 0.6, 1);
  keyFloor.receiveShadow = true;
  keyFloor.renderOrder = -1;
  scene.add(...ground, pool, shadowPool, keyFloor);
  [target, blurTarget, depth, quadGeometry, horizontal, vertical, groundGeometry, poolMaterial, shadowPoolMaterial, keyFloorMaterial]
    .forEach((resource) => resources.add(resource));

  return (renderer, floor, withAssembled = (render) => render(), withFeetOnly = (render) => render()) => {
    pool.visible = keyFloor.visible = shadowPool.visible = Number.isFinite(floor);
    // Bake and composite at the lowest assembly z so the feet touch their contact shadow.
    ground.forEach((mesh) => {
      mesh.visible = pool.visible;
      mesh.position.set(center.x, center.y, floor - 0.05);
    });
    if (!pool.visible) return;
    pool.position.set(center.x, center.y, floor - 0.2);
    shadowPool.position.set(center.x, center.y, floor - 0.15);
    keyFloor.position.set(center.x, center.y, floor - 0.03);
    capture.position.copy(ground[0].position);
    capture.lookAt(center.x, center.y, floor + 1);

    // Depth from below, then two separable blur passes per scale before compositing the ground.
    // The 1.4/512 footprint scale is baked at explode 0 so it sits under the assembled footprint;
    // the tight 0.5/512 scale uses the current pose so every foot touches its own dark spot.
    const override = scene.overrideMaterial;
    const shadowUpdates = renderer.shadowMap.autoUpdate;
    renderer.shadowMap.autoUpdate = false;
    const renderDepth = () => {
      renderer.setRenderTarget(target);
      renderer.clear();
      scene.overrideMaterial = depth;
      renderer.render(scene, capture);
      scene.overrideMaterial = override;
    };
    const blurInto = ({ blur, target: output }) => {
      horizontal.uniforms.h.value = vertical.uniforms.v.value = blur / size;
      quad.material = horizontal;
      renderer.setRenderTarget(blurTarget);
      renderer.render(blurScene, blurCamera);
      quad.material = vertical;
      renderer.setRenderTarget(output);
      renderer.render(blurScene, blurCamera);
    };
    withAssembled(renderDepth);
    blurInto(bakes[0]);
    renderDepth();
    blurInto(bakes[1]);
    // A third, tight 0.25/512 layer at 0.55 from the feet alone, so each foot sits on a dark spot.
    withFeetOnly(renderDepth);
    blurInto(bakes[2]);
    renderer.setRenderTarget(null);
    renderer.shadowMap.autoUpdate = shadowUpdates;
  };
}

function createGrid(center, footprint, radius, resources) {
  // The grid must reach past the assembly to be seen: full strength inside the footprint, fading
  // to zero 0.6 × the model radius beyond it. A fade that ended inside the footprint hid the grid.
  const fadeStart = footprint;
  const fadeRadius = footprint + radius * 0.6;
  const geometry = new THREE.PlaneGeometry(fadeRadius * 2, fadeRadius * 2);
  const material = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, toneMapped: false,
    uniforms: {
      fadeStart: { value: fadeStart }, fadeRadius: { value: fadeRadius }, opacity: { value: 1 }, dpr: { value: 1 },
      tint: { value: new THREE.Color(0x9097a0) },
    },
    vertexShader: `
      varying vec2 mm;
      void main() {
        mm = position.xy;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      varying vec2 mm;
      uniform float fadeStart, fadeRadius, opacity, dpr;
      uniform vec3 tint;
      // mm per drawing-buffer pixel comes from fwidth, so a line is one CSS pixel wide at any DPR.
      float grid(float spacing) {
        vec2 width = max(fwidth(mm), vec2(1e-4));
        vec2 dist = abs(fract(mm / spacing - 0.5) - 0.5) * spacing / width;
        vec2 line = 1.0 - smoothstep(vec2(0.5 * dpr), vec2(0.5 * dpr + 1.0), dist);
        return max(line.x, line.y);
      }
      void main() {
        float fade = 1.0 - smoothstep(fadeStart, fadeRadius, length(mm));
        gl_FragColor = vec4(tint, max(0.035 * grid(10.0), 0.07 * grid(50.0)) * fade * opacity);
        #include <colorspace_fragment>
      }`,
  });
  const grid = new THREE.Mesh(geometry, material);
  grid.name = "Grid 10 mm";
  grid.position.copy(center);
  resources.add(geometry);
  resources.add(material);
  return grid;
}

function screenQuad(fragmentShader, uniforms, options) {
  return new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
    uniforms, ...options,
    vertexShader: `varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = vec4(position.xy, 0.0, 1.0);
      }`,
    fragmentShader,
  }));
}

class TechnicalPass extends RenderPass {
  constructor(scene, camera) {
    super(scene, camera);
    this.clearPass.enabled = false;
    this.needsDepthTexture = true;
    this.target = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, stencilBuffer: true });
    this.quads = new THREE.Scene();
    this.quadCamera = new THREE.Camera();
    this.quads.add(this.depthCopy = screenQuad(`
      uniform sampler2D sceneDepth;
      varying vec2 vUv;
      void main() {
        gl_FragDepth = texture2D(sceneDepth, vUv).r;
        gl_FragColor = vec4(0.0);
      }`, { sceneDepth: { value: null } }, { colorWrite: false, depthFunc: THREE.AlwaysDepth }));
    this.quads.add(this.sobel = screenQuad(`
      #include <packing>
      uniform sampler2D sceneDepth;
      uniform vec2 pixel, clip;
      uniform vec3 ink;
      varying vec2 vUv;
      float distanceAt(float x, float y) {
        float z = texture2D(sceneDepth, vUv + vec2(x, y) * pixel).r;
        return -perspectiveDepthToViewZ(z, clip.x, clip.y);
      }
      void main() {
        float nw = distanceAt(-1.0, 1.0), n = distanceAt(0.0, 1.0), ne = distanceAt(1.0, 1.0);
        float w = distanceAt(-1.0, 0.0), e = distanceAt(1.0, 0.0);
        float sw = distanceAt(-1.0, -1.0), s = distanceAt(0.0, -1.0), se = distanceAt(1.0, -1.0);
        // A first-derivative (Sobel) test flags every sloped plane in perspective.
        // A depth discontinuity shows up as a large second derivative relative to
        // distance, which planar surfaces do not produce.
        float c = distanceAt(0.0, 0.0);
        float lap = abs(n + s + e + w - 4.0 * c) + 0.5 * abs(nw + ne + sw + se - 4.0 * c);
        float edge = smoothstep(0.012 * c, 0.03 * c, lap);
        gl_FragColor = vec4(ink, 0.35 * edge);
      }`, {
      sceneDepth: { value: null }, pixel: { value: new THREE.Vector2() }, clip: { value: new THREE.Vector2() },
      ink: { value: new THREE.Color(0x0b0d10) },
    }, { transparent: true, depthTest: false, depthWrite: false }));
    this.depthCopy.frustumCulled = this.sobel.frustumCulled = false;
    this.cameraForDepth = camera;
  }

  setSize(width, height) {
    this.target.setSize(width, height);
  }

  setDepthTexture(texture) {
    this.depthCopy.material.uniforms.sceneDepth.value = texture;
    this.sobel.material.uniforms.sceneDepth.value = texture;
  }

  render(renderer) {
    if (!this.depthCopy.material.uniforms.sceneDepth.value) throw new Error("Scene depth unavailable");
    const { near, far } = this.cameraForDepth;
    const dpr = renderer.getPixelRatio();
    this.sobel.material.uniforms.clip.value.set(near, far);
    this.sobel.material.uniforms.pixel.value.set(dpr / this.target.width, dpr / this.target.height);
    this.sobel.visible = this.high;
    // AO can swap the composer's color buffers. Copy only the original scene depth,
    // then retain it across the technical RenderPass with its clear pass disabled.
    renderer.setRenderTarget(this.target);
    // The overlay must start fully transparent, or its clear colour is composited
    // over the whole assembly and darkens it.
    const clearColor = renderer.getClearColor(new THREE.Color());
    const clearAlpha = renderer.getClearAlpha();
    renderer.setClearColor(0x000000, 0);
    renderer.clear();
    renderer.setClearColor(clearColor, clearAlpha);
    renderer.render(this.quads, this.quadCamera);
    super.render(renderer, this.target);
  }

  dispose() {
    this.target.dispose();
    for (const quad of this.quads.children) {
      quad.geometry.dispose();
      quad.material.dispose();
    }
    super.dispose();
  }
}

function createComposer(renderer, scene, technical, camera) {
  const composer = new EffectComposer(renderer, { frameBufferType: THREE.HalfFloatType });
  const passes = [];
  const add = (pass) => {
    passes.push(pass);
    composer.addPass(pass);
  };
  try {
    add(new RenderPass(scene, camera));
    const ao = new N8AOPostPass(scene, camera, 1, 1);
    add(ao);
    ao.setQualityMode("Medium");
    for (const [key, value] of Object.entries({
      aoRadius: 5, distanceFalloff: 1, intensity: 3, aoSamples: 16, denoiseSamples: 8,
      denoiseRadius: 12, gammaCorrection: false, screenSpaceRadius: false, halfRes: false,
    })) {
      if (ao.configuration[key] !== undefined) ao.configuration[key] = value;
    }
    const overlay = new TechnicalPass(technical, camera);
    add(overlay);
    const exposure = new Effect("Bench exposure", `
      uniform float exposure;
      void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
        outputColor = vec4(inputColor.rgb * exposure, inputColor.a);
      }`, {
      blendFunction: BlendFunction.SRC,
      uniforms: new Map([["exposure", new THREE.Uniform(EXPOSURE)]]),
    });
    const tone = new ToneMappingEffect({ mode: ToneMappingMode.NEUTRAL });
    // The overlay is premultiplied in its own linear buffer. Apply exposure to the
    // assembly only, then mix the drafting colors after the neutral tone curve.
    const composite = new Effect("Technical overlay", `
      uniform sampler2D technical;
      void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
        vec4 overlay = texture2D(technical, uv);
        outputColor = overlay + inputColor * (1.0 - overlay.a);
      }`, {
      blendFunction: BlendFunction.SRC,
      uniforms: new Map([["technical", new THREE.Uniform(overlay.target.texture)]]),
    });
    add(new EffectPass(camera, exposure, tone, composite));
    add(new EffectPass(camera, new SMAAEffect({ preset: SMAAPreset.HIGH })));
    return {
      setSize: (width, height) => composer.setSize(width, height, false),
      render(tier, orbiting) {
        overlay.high = tier === "high";
        // N8AO 2.0 builds its half-resolution targets only at construction, so toggling
        // halfRes at runtime leaves them undefined. Cost is controlled by the tier's DPR,
        // and AO is skipped entirely while orbiting on the standard tier.
        ao.enabled = !(orbiting && tier === "standard");
        composer.render();
      },
      dispose: () => composer.dispose(),
    };
  } catch (error) {
    // A pass that failed initialization may not yet belong to the composer.
    for (const pass of passes) {
      if (!composer.passes.includes(pass)) pass.dispose();
    }
    composer.dispose();
    throw error;
  }
}

function updateScreenDashes(scene, camera, width, height) {
  const point = new THREE.Vector3();
  const start = new THREE.Vector2();
  const end = new THREE.Vector2();
  const toScreen = (attribute, instance, matrix, out) => {
    point.fromBufferAttribute(attribute, instance).applyMatrix4(matrix).applyMatrix4(camera.matrixWorldInverse);
    point.z = Math.min(point.z, -camera.near);
    point.applyMatrix4(camera.projectionMatrix);
    return out.set(point.x * width * 0.5, point.y * height * 0.5);
  };
  scene.updateMatrixWorld();
  scene.traverseVisible((line) => {
    if (!line.isLineSegments2 || !line.material.dashed) return;
    const { instanceStart, instanceEnd, instanceDistanceStart, instanceDistanceEnd } = line.geometry.attributes;
    let distance = 0;
    for (let i = 0; i < instanceStart.count; i++) {
      toScreen(instanceStart, i, line.matrixWorld, start);
      toScreen(instanceEnd, i, line.matrixWorld, end);
      instanceDistanceStart.setX(i, distance);
      distance += start.distanceTo(end);
      instanceDistanceEnd.setX(i, distance);
    }
    instanceDistanceStart.data.needsUpdate = true;
  });
}

function createFrameSampler(renderer) {
  const gl = renderer.getContext();
  const timer = gl.getExtension("EXT_disjoint_timer_query_webgl2");
  const samples = [];
  const pending = [];
  let started = 0;
  return {
    begin(start) {
      if (started >= QUALITY_SAMPLE_COUNT) return null;
      started++;
      const query = timer && gl.createQuery();
      if (query) gl.beginQuery(timer.TIME_ELAPSED_EXT, query);
      return { query, start };
    },
    end(sample) {
      if (!sample) return;
      if (sample.query) gl.endQuery(timer.TIME_ELAPSED_EXT);
      const submitted = performance.now();
      pending.push({ query: sample.query, cpu: submitted - sample.start, submitted });
    },
    collect() {
      const disjoint = timer && (gl.isContextLost() || gl.getParameter(timer.GPU_DISJOINT_EXT));
      while (pending.length) {
        const { query, cpu, submitted } = pending[0];
        const available = query && !disjoint && gl.getQueryParameter(query, gl.QUERY_RESULT_AVAILABLE);
        if (query && !disjoint && !available && performance.now() - submitted < 250) break;
        const gpu = available ? gl.getQueryParameter(query, gl.QUERY_RESULT) / 1e6 : 0;
        if (query) gl.deleteQuery(query);
        samples.push(Math.max(cpu, gpu));
        pending.shift();
      }
      return samples;
    },
    waiting: () => started === QUALITY_SAMPLE_COUNT && pending.length > 0,
    dispose() {
      for (const { query } of pending) {
        if (query) gl.deleteQuery(query);
      }
    },
  };
}

const SVG_NS = "http://www.w3.org/2000/svg";
function svgNode(parent, tag, attributes, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  if (text != null) node.textContent = text;
  parent.append(node);
  return node;
}

// Face view drafting (ISO 128 / 129-1) in the SVG overlay, projected through the same camera as
// the 3D contours so every mark sits on its feature. Returns the drawing's lower edge for the strip.
function drawFace(host, project, entries, face, visible, { base, target, focusPart }) {
  const layer = host.querySelector("[data-face-drawing]");
  if (!layer) return null;
  layer.replaceChildren();
  if (!visible || !face) return null;
  const { mode, fit, compact, sources } = face;
  const older = mode !== target ? entries.get(`${base}:part:${focusPart}`)?.bounds : null;
  const newer = mode !== base ? entries.get(`${target}:part:${focusPart}`)?.bounds : null;
  const outlineOf = (bounds) => {
    if (!bounds) return null;
    const a = project(new THREE.Vector3(bounds.min.x, bounds.max.y, bounds.max.z));
    const b = project(new THREE.Vector3(bounds.max.x, bounds.min.y, bounds.max.z));
    return a && b ? { left: a.x, top: a.y, right: b.x, bottom: b.y } : null;
  };
  const o = outlineOf(older);
  const n = outlineOf(newer);
  if (!o && !n) return null;
  const extent = [o, n].filter(Boolean).reduce((a, b) => ({
    left: Math.min(a.left, b.left), right: Math.max(a.right, b.right),
    top: Math.min(a.top, b.top), bottom: Math.max(a.bottom, b.bottom),
  }));
  const label = (feature, value, revision) => ({
    short: `${compact ? feature.replace(" display outline", "") : feature} · ${formatEvidenceValue({ field: "dimension_mm", value })}${compact ? "" : " · computed"}`,
    source: compact ? "" : ` from ${sources?.[revision] ?? `${revision}-inch GLB`}`,
  });
  const dimensions = [];
  if (o) {
    dimensions.push({ kind: "removed", from: [o.left, o.top], to: [o.right, o.top], normal: [0, -1], offset: 28,
      text: label("7-inch display outline", older.max.x - older.min.x, base) });
    dimensions.push({ kind: "removed", from: [o.left, o.bottom], to: [o.left, o.top], normal: [-1, 0], offset: 28,
      text: label("7-inch display outline", older.max.y - older.min.y, base) });
  }
  let lowest = extent.bottom;
  if (n) {
    // 5-inch dimensions take the sides the 7-inch ones leave free. They sit in the band between the
    // two outlines when it is wide enough to stay 24 px clear of the 7-inch outline, else outside it.
    const place = (band) => (!o ? 28 : band >= 52 ? 22 : band + 40);
    const below = place(o ? o.bottom - n.bottom : 0);
    const beside = place(o ? o.right - n.right : 0);
    dimensions.push({ kind: "added", from: [n.left, n.bottom], to: [n.right, n.bottom], normal: [0, 1], offset: below,
      text: label("5-inch glass", newer.max.x - newer.min.x, target) });
    dimensions.push({ kind: "added", from: [n.right, n.bottom], to: [n.right, n.top], normal: [1, 0], offset: beside,
      text: label("5-inch glass", newer.max.y - newer.min.y, target) });
    lowest = Math.max(lowest, n.bottom + below + 4);
  }
  for (const { kind, from, to, normal, offset, text } of dimensions) {
    const dimension = linearDimension(from, to, normal, offset);
    const group = svgNode(layer, "g", { class: "fd-dim", "data-kind": kind });
    svgNode(group, "path", { class: "fd-dim-extension", d: dimension.extensions });
    svgNode(group, "path", { class: "fd-dim-line", d: dimension.line });
    svgNode(group, "path", { class: "fd-dim-arrow", d: dimension.arrows });
    const node = svgNode(group, "text", {
      class: "fd-dim-text", "text-anchor": "middle",
      transform: `translate(${dimension.text.x},${dimension.text.y}) rotate(${dimension.text.rotate})`,
    }, text.short + text.source);
    // Text stays within its dimension line; the GLB name moves to the strip's source line if not.
    if (text.source && node.getComputedTextLength?.() > dimension.length - 16) node.textContent = text.short;
  }
  if (n && fit) {
    const at = ([x, y], z) => project(new THREE.Vector3(x, y, z));
    // Aperture: the inner-facing section edges of each faceplate half that bound it.
    const inner = fit.inner.map(([a, b]) => [at(a, fit.level), at(b, fit.level)]).filter(([a, b]) => a && b);
    if (inner.length) svgNode(layer, "path", { class: "fd-aperture", d: inner.map(([a, b]) => `M${a.x},${a.y}L${b.x},${b.y}`).join("") });
    // The seam between the halves, as its own short ink dimension.
    if (fit.seam) {
      const from = at(fit.seam.from, fit.level);
      const to = at(fit.seam.to, fit.level);
      if (from && to) {
        const seam = linearDimension([from.x, from.y], [to.x, to.y], [0, 1], 0, { gap: 0, overrun: 0 });
        const group = svgNode(layer, "g", { class: "fd-gap fd-seam", "data-known": "true" });
        svgNode(group, "path", { class: "fd-dim-line", d: seam.line });
        svgNode(group, "path", { class: "fd-dim-arrow", d: seam.arrows });
        svgNode(group, "text", { class: "fd-gap-text", "text-anchor": "middle", x: (from.x + to.x) / 2, y: from.y + 14 },
          compact ? `Seam ${fit.seam.gap.toFixed(2)} mm` : seamLabel(fit.seam));
      }
    }
    // Spacer mesh centroids: a 12 px cross each.
    const crosses = fit.spacers.map(({ point }) => project(new THREE.Vector3(...point))).filter(Boolean)
      .map(({ x, y }) => `M${x - 6},${y}h12M${x},${y - 6}v12`).join("");
    if (crosses) svgNode(layer, "path", { class: "fd-spacer-marks", d: crosses });
    // Projected gaps per side: a signed dimension when derived, otherwise a dotted "?" stub.
    const [, cy] = fit.centre;
    // Top and bottom gap marks sit left of the seam so they never cover it.
    const middle = { left: [n.left, (n.top + n.bottom) / 2], right: [n.right, (n.top + n.bottom) / 2],
      top: [n.left + (n.right - n.left) * 0.2, n.top], bottom: [n.left + (n.right - n.left) * 0.2, n.bottom] };
    const inward = { left: [1, 0], right: [-1, 0], top: [0, 1], bottom: [0, -1] };
    for (const side of ["left", "right", "top", "bottom"]) {
      const gap = fit.gaps[side];
      const [x, y] = middle[side];
      const [ix, iy] = inward[side];
      const letter = side[0].toUpperCase();
      // Known gaps carry the short form on the drawing; the strip lists every full label.
      const text = gap.value == null ? (compact ? `Gap ${letter} ?` : halfGapLabel(side, gap)) : `${letter} ${formatGapValue(gap.value)}`;
      const vertical = side === "left" || side === "right";
      const group = svgNode(layer, "g", { class: "fd-gap", "data-side": side, "data-known": String(gap.value != null) });
      let textAt = null;
      if (gap.value == null) {
        svgNode(group, "path", { class: "fd-gap-unknown", d: `M${x - ix * 6},${y - iy * 6}L${x + ix * 14},${y + iy * 14}` });
      } else {
        // The aperture edge on this side, on the line through the display centre: the outline's
        // extreme minus the signed gap (left, bottom) or plus it (right, top).
        const axis = vertical ? 0 : 1;
        const extreme = side === "left" || side === "bottom"
          ? Math.min(...fit.outline.map((point) => point[axis])) - gap.value
          : Math.max(...fit.outline.map((point) => point[axis])) + gap.value;
        const xs = fit.outline.map((point) => point[0]);
        const markX = Math.min(...xs) + (Math.max(...xs) - Math.min(...xs)) * 0.2;
        const edge = at(vertical ? [extreme, cy] : [markX, extreme], fit.level);
        if (edge) {
          const dimension = linearDimension([x, y], vertical ? [edge.x, y] : [x, edge.y], vertical ? [0, -1] : [1, 0], 0, { gap: 0, overrun: 0 });
          svgNode(group, "path", { class: "fd-dim-line", d: dimension.line });
          svgNode(group, "path", { class: "fd-dim-arrow", d: dimension.arrows });
          // The value reads inside the aperture, just past the arrow at the aperture edge.
          textAt = {
            left: { x: edge.x + 6, y: y + 4, anchor: "start" }, right: { x: edge.x - 6, y: y + 4, anchor: "end" },
            top: { x: x + 6, y: edge.y + 14, anchor: "start" }, bottom: { x: x + 6, y: edge.y - 6, anchor: "start" },
          }[side];
        }
      }
      // Phones keep the marks; the strip carries the values.
      if (compact && gap.value != null) continue;
      const { x: tx, y: ty, rotate = 0, anchor = "middle" } = textAt
        ?? { x: x + ix * 18, y: y + iy * 18, rotate: vertical ? -90 : 0 };
      svgNode(group, "text", {
        class: "fd-gap-text", "text-anchor": anchor, "dominant-baseline": textAt ? "auto" : "central",
        transform: `translate(${tx},${ty}) rotate(${rotate})`,
      }, text);
    }
  }
  return { left: extent.left, right: extent.right, y: lowest };
}

function layoutAnnotations(host, camera, entries, width, height, canvasTop, panels, placeLabels, displayOpacity, showDimensions, sceneConfig, gridPoint, face) {
  const { base } = sceneConfig;
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
  // Project the part's own sampled vertices from whichever layer is drawn.
  function screenPointsFor(key) {
    const entry = entries.get(key);
    const object = entry?.group.visible ? entry.group : null;
    if (!object || !entry.samples.length) return [];
    const points = [];
    const vector = new THREE.Vector3();
    for (let i = 0; i < entry.samples.length; i += 3) {
      vector.set(entry.samples[i], entry.samples[i + 1], entry.samples[i + 2]).add(object.position);
      const point = project(vector);
      if (point) points.push(point);
    }
    return points;
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
  const footprint = host.querySelector("[data-footprint]");
  const faceTicks = [];
  const markPin = (node, anchor) => {
    const entry = footprint && entries.get(node.dataset.pinAnchor);
    if (entry?.displayOverlay && !anchor) {
      // Face view: a 7-inch question sits on the 7-inch outline; a 5-inch question sits beside the
      // display lug it is about, with a 1 px tick back to that lug.
      const { bounds } = entry;
      if (entry.row.revision === base) {
        const point = project(new THREE.Vector3(THREE.MathUtils.lerp(bounds.min.x, bounds.max.x, 0.12), bounds.max.y, bounds.max.z));
        return mark(node, point, true);
      }
      const lug = entry.displayOverlay.lug && project(entry.displayOverlay.lug.clone());
      if (lug) {
        const point = mark(node, { x: lug.x - 30, y: lug.y + 22 }, true);
        if (point) {
          const length = Math.hypot(lug.x - point.x, lug.y - point.y);
          faceTicks.push(`M${point.x + (lug.x - point.x) * 12 / length},${point.y + (lug.y - point.y) * 12 / length}L${lug.x},${lug.y}`);
        }
        return point;
      }
    }
    return mark(node, anchor ?? centerFor(node.dataset.pinAnchor), Boolean(footprint));
  };
  host.querySelectorAll("[data-pin-anchor]:not([data-endpoint-pin]):not([data-interface-question])")
    .forEach((node) => markPin(node));
  // Routing is unknown, so nothing is drawn between A and B: the pill sits beside endpoint B, clear
  // of every placed pin, and the interface's questions gather around the pill.
  const endpoint = endpointPositions.get("B") ?? endpointPositions.get("A");
  let routePoint = null;
  if (routeLabel) {
    routePoint = endpoint && placeBesideEndpoint(viewport, [...occupied, ...pinRects], endpoint,
      routeLabel.offsetWidth, routeLabel.offsetHeight);
    position(routeLabel, routePoint);
    if (routePoint) {
      const rect = rectFor(routeLabel);
      occupied.push(rect);
      pinRects.push(rect);
    }
  }
  const fixedMarkers = markers.slice();
  const interfacePins = [...host.querySelectorAll("[data-interface-question]")]
    .map((node) => ({ node, point: markPin(node, routePoint ?? endpoint) })).filter(({ point }) => point);
  const ticks = [];
  if (interfacePins.length) {
    // Repel in screen space: 24 px between pin centres, 12 px clear of the pill, then a 1 px amber
    // tick from each pin back to the pill it belongs to.
    const pill = routePoint && rectFor(routeLabel);
    const settled = repelPins([...fixedMarkers.map((point) => ({ ...point, fixed: true })),
      ...interfacePins.map(({ point }) => point)], { minDistance: 28, obstacles: pill ? [pill] : [], clearance: window.matchMedia(FIELDDECK_NARROW).matches ? 26 : 18 })
      .slice(fixedMarkers.length);
    interfacePins.forEach(({ node }, i) => {
      const point = settled[i];
      position(node, point);
      const target = pill ? { x: Math.min(pill.right, Math.max(pill.left, point.x)), y: Math.min(pill.bottom, Math.max(pill.top, point.y)) }
        : routePoint ?? endpoint;
      const length = Math.hypot(target.x - point.x, target.y - point.y);
      if (length > 13) {
        const ux = (target.x - point.x) / length;
        const uy = (target.y - point.y) / length;
        ticks.push(`M${point.x + ux * 12},${point.y + uy * 12}L${target.x},${target.y}`);
      }
    });
  }
  host.querySelector("[data-pin-ticks]")?.setAttribute("d", [...faceTicks, ...ticks].join(" "));
  host.querySelector("[data-pin-leaders]").setAttribute("d", pinLeaders.join(" "));

  if (footprint) {
    const bottom = drawFace(host, project, entries, face, showDimensions, sceneConfig);
    if (bottom !== null) {
      const { left, right } = bottom;
      const x = (left + right) / 2;
      const halfWidth = footprint.offsetWidth / 2;
      const clearance = Math.min(viewport.bottom, ...occupied.filter((rect) =>
        rect.top >= bottom.y && rect.left < x + halfWidth && rect.right > x - halfWidth).map((rect) => rect.top));
      position(footprint, { x, y: Math.max(bottom.y + 16, Math.min(bottom.y + 24, clearance - footprint.offsetHeight - 12)) });
    } else {
      position(footprint, null);
    }
  }
  const pointCache = new Map();
  const pointsFor = (key) => {
    if (!pointCache.has(key)) pointCache.set(key, screenPointsFor(key));
    return pointCache.get(key);
  };
  for (const path of host.querySelectorAll("[data-bracket]")) {
    // A tight box from the selected part's own projected vertices, not its 3D bounding box.
    const d = bracketPath(pointsFor(path.dataset.bracket), { arm: 10, offset: 8 });
    if (d) path.setAttribute("d", d);
    else path.removeAttribute("d");
  }

  // "Grid 10 mm" is pinned to the bottom-left of the free viewport, 16 px in, clear of the panels.
  const gridLabel = host.querySelector("[data-grid-label]");
  if (gridLabel) {
    const w = gridLabel.offsetWidth;
    const h = gridLabel.offsetHeight;
    let rect = { left: viewport.left + 16, right: viewport.left + 16 + w, top: viewport.bottom - 16 - h, bottom: viewport.bottom - 16 };
    for (let i = 0; i < 6; i++) {
      const blocker = occupied.find((panel) => rect.left < panel.right && rect.right > panel.left
        && rect.top < panel.bottom && rect.bottom > panel.top);
      if (!blocker) break;
      // Step right of a side panel, or above a bottom bar.
      if (blocker.bottom - blocker.top > 3 * (blocker.right - blocker.left) || blocker.top < rect.top - 200) {
        rect = { ...rect, left: blocker.right + 16, right: blocker.right + 16 + w };
      } else {
        rect = { ...rect, top: blocker.top - 16 - h, bottom: blocker.top - 16 };
      }
    }
    position(gridLabel, gridPoint ? { x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2 } : null);
  }

  // Old-revision small features: a moved one gets a 1 px leader from its old centre to its new
  // centre with a 5 px arrowhead and its computed centre distance; an unpaired one keeps a 6 px
  // centre cross.
  const marks = [];
  const links = host.querySelector("[data-ghost-links]");
  links?.replaceChildren();
  for (const entry of entries.values()) {
    const overlay = entry.overlay;
    if (!overlay?.object.visible) continue;
    const at = (center) => project(new THREE.Vector3(...center).add(overlay.object.position));
    const paired = new Set((overlay.pairs ?? []).map(([older]) => older));
    for (const feature of overlay.features) {
      const point = !paired.has(feature) && at(feature.center);
      if (point) marks.push(`M${point.x - 3},${point.y}h6M${point.x},${point.y - 3}v6`);
    }
    for (const [older, newer] of overlay.pairs ?? []) {
      const from = at(older.center);
      const to = at(newer.center);
      if (!from || !to || !links) continue;
      const length = Math.hypot(to.x - from.x, to.y - from.y);
      const distance = Math.hypot(...newer.center.map((value, axis) => value - older.center[axis]));
      const group = svgNode(links, "g", { class: "fd-ghost-link" });
      if (length > 6) {
        const ux = (to.x - from.x) / length;
        const uy = (to.y - from.y) / length;
        const half = 5 * Math.tan(Math.PI / 12);
        const bx = to.x - ux * 5;
        const by = to.y - uy * 5;
        svgNode(group, "path", { class: "fd-ghost-leader", d: `M${from.x},${from.y}L${bx},${by}` });
        svgNode(group, "path", { class: "fd-ghost-arrow", d: `M${to.x},${to.y}L${bx - uy * half},${by + ux * half}L${bx + uy * half},${by - ux * half}Z` });
      }
      svgNode(group, "text", { class: "fd-ghost-delta", x: (from.x + to.x) / 2 + 6, y: (from.y + to.y) / 2 - 6 },
        `Δ ${distance.toFixed(2)} mm · computed`);
    }
  }
  host.querySelector("[data-ghost-marks]")?.setAttribute("d", marks.join(""));

  const labels = [...host.querySelectorAll("[data-anchor]")];
  if (!labels.length) return;
  const outlines = placeLabels ? [...entries.keys()].map((key) => outlineFor(boundsForKey(key))).filter(Boolean) : [];
  const model = {
    left: Math.min(...outlines.map(({ left }) => left)),
    right: Math.max(...outlines.map(({ right }) => right)),
  };
  const hulls = new Map();
  const callouts = placeLabels && labels.map((node) => {
    const endpoint = node.dataset.endpointLabel;
    const anchor = endpoint ? endpointPositions.get(endpoint) : centerFor(node.dataset.anchor);
    // Leaders end on the part's near silhouette. An endpoint label ends on its A/B marker unless
    // the part is large on screen, where the leader would cross it (the 5-inch display).
    let hull = anchor ? convexHull(pointsFor(node.dataset.anchor)) : [];
    if (endpoint && hull.length) {
      const span = Math.max(...hull.map(({ x }) => x)) - Math.min(...hull.map(({ x }) => x));
      if (span < 160) hull = [];
    }
    hulls.set(node, hull);
    // Leaders land on the part's own silhouette: the extreme projected vertex on each side.
    const extreme = (sign) => hull.reduce((best, point) => !best || sign * (point.x - best.x) > 0 ? point : best, null);
    return {
      anchor, model, width: node.offsetWidth, height: node.offsetHeight, elbow: true,
      leftAnchor: extreme(-1) ?? anchor, rightAnchor: extreme(1) ?? anchor,
    };
  });
  const placements = callouts && placeCallouts(viewport, occupied, callouts, pinRects);
  const fallback = placements && placements.some((placement) => !placement)
    && placeCallouts(viewport, occupied, callouts.map((callout, i) => placements[i] ? {} : { ...callout, model: null }),
      [...pinRects, ...placements.flatMap((placement) => placement ? [placement.rect] : [])]);
  const cards = placements ? placements.map((placement, j) => (placement ?? fallback?.[j])?.rect).filter(Boolean) : [];
  for (const [i, node] of labels.entries()) {
    const line = host.querySelector(`[data-leader="${i}"]`);
    node.style.opacity = line.style.opacity = displayOpacity;
    if (!placements) continue;
    const placement = placements[i] ?? fallback?.[i];
    node.style.visibility = line.style.visibility = placement ? "visible" : "hidden";
    if (!placement) continue;
    const { rect } = placement;
    let { leader } = placement;
    const hull = hulls.get(node);
    let card = rect;
    if (hull?.length && leader.length === 3) {
      // Re-anchor on the silhouette vertex nearest the label's attachment point.
      const start = leader[0];
      const end = nearestPoint(hull, start);
      leader = [start, { x: end.x, y: start.y }, end];
    }
    const leaderLength = (path) => path.slice(1).reduce((sum, p, j) => sum + Math.hypot(p.x - path[j].x, p.y - path[j].y), 0);
    if (leaderLength(leader) > 120 && hull?.length) {
      // Leaders are capped at 120 px: set the card beside the part's own silhouette instead.
      const xs = hull.map(({ x }) => x);
      const ys = hull.map(({ y }) => y);
      const midY = (Math.min(...ys) + Math.max(...ys)) / 2;
      const cardHeight = rect.bottom - rect.top;
      const top = Math.min(Math.max(viewport.top, midY - cardHeight / 2), viewport.bottom - cardHeight);
      const tries = [Math.max(...xs) + 24, Math.min(...xs) - 24 - (rect.right - rect.left)];
      const blocked = (r) => r.left < viewport.left || r.right > viewport.right
        || [...occupied, ...cards.filter((other) => other !== rect)].some((panel) =>
          r.left < panel.right + 8 && r.right > panel.left - 8 && r.top < panel.bottom + 8 && r.bottom > panel.top - 8);
      const next = tries.map((left) => ({ left, right: left + rect.right - rect.left, top, bottom: top + rect.bottom - rect.top }))
        .find((r) => !blocked(r));
      if (next) {
        const start = { x: next.left > Math.max(...xs) - 1 ? next.left : next.right, y: (next.top + next.bottom) / 2 };
        const end = nearestPoint(hull, start);
        card = next;
        cards[cards.indexOf(rect)] = next;
        leader = [start, end];
      } else {
        node.style.visibility = line.style.visibility = "hidden";
        continue;
      }
    }
    node.style.transform = `translate(${card.left}px, ${card.top}px)`;
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
  const technical = new THREE.Scene();
  const entries = makeEntries(assets, index, scene, technical, resources, sceneConfig);
  const all = [...entries.values()];
  const faceFit = all.length ? computeFaceFit(entries, sceneConfig) : null;
  const glbSources = Object.fromEntries(Object.entries(assets)
    .map(([revision, { sidecar }]) => [revision, sidecar?.glb_source?.split("/").at(-1)]));
  if (!all.length) {
    resources.forEach((resource) => resource.dispose());
    throw new Error("No GLB mesh names match the Fielddeck sidecars.");
  }

  function createRenderer(antialias) {
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias });
    renderer.autoClear = false;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.domElement.setAttribute("aria-label", "Interactive Fielddeck assembly");
    return renderer;
  }
  function createEnvironment(renderer) {
    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    room.rotation.x = Math.PI / 2;
    try {
      const environment = pmrem.fromScene(room, 0.04);
      scene.environment = environment.texture;
      // A lower ambient floor lets the key carry the value structure: lit tops, darker walls.
      scene.environmentIntensity = 0.2;
      return environment;
    } finally {
      room.dispose();
      pmrem.dispose();
    }
  }

  const modeEntries = {
    [base]: all.filter(({ row }) => row.revision === base),
    [target]: all.filter(({ row }) => row.revision === target),
    compare: all.filter(({ row }) => row.revision === target || row.delta === "removed"),
  };
  groupExplode(all);
  const extended = boundsFor(all, 1).union(boundsFor(all, 0));
  const renderContact = createContactShadow(scene, extended, resources);
  const assembled = boundsFor(all, 0);
  const center = assembled.getCenter(new THREE.Vector3());
  const radius = extended.getSize(new THREE.Vector3()).length() / 2;
  const footprint = Math.hypot(assembled.max.x - assembled.min.x, assembled.max.y - assembled.min.y) / 2;
  const grid = createGrid(center, footprint, radius, resources);
  scene.add(grid);

  function light(color, intensity, x, y, elevation, spot = false) {
    const lamp = spot ? new THREE.SpotLight(color, intensity, 0, Math.PI / 4, 0.35, 0)
      : new THREE.DirectionalLight(color, intensity);
    const pitch = THREE.MathUtils.degToRad(elevation);
    lamp.position.set(x, y, 0).normalize().multiplyScalar(Math.cos(pitch));
    lamp.position.z = Math.sin(pitch);
    lamp.position.multiplyScalar(radius * (spot ? 2.2 : 2)).add(center);
    lamp.target.position.copy(center);
    scene.add(lamp, lamp.target);
    return lamp;
  }
  // The key is a spot at a finite distance, so its incidence changes across a plate and the
  // cream tops carry a gradient instead of one flat value.
  const key = light(0xfff3e6, 3.1, -3, -5, 55, true);
  // A cool fill, so shadow sides of the dimmed masses go cool grey instead of brown.
  light(0xe6eef7, 0.6, 6, -2, 17);
  // Rim from behind, strong enough to lift the back plate edges off the background.
  light(0xffffff, 2.4, 2, 7, 28);
  // Part-on-part shadows come from presentation offsets, so they read as soft form, not placement.
  key.shadow.radius = 6;
  key.shadow.intensity = 0.55;
  key.shadow.bias = -0.002;
  key.shadow.normalBias = 0.05;
  key.shadow.autoUpdate = false;
  {
    // Fit the cone and the shadow frustum to the model's assembled and exploded bounds.
    const axis = center.clone().sub(key.position).normalize();
    let widest = 0;
    let nearest = Infinity;
    let farthest = 0;
    for (const x of [extended.min.x, extended.max.x]) {
      for (const y of [extended.min.y, extended.max.y]) {
        for (const z of [extended.min.z, extended.max.z]) {
          const ray = new THREE.Vector3(x, y, z).sub(key.position);
          const depth = ray.dot(axis);
          widest = Math.max(widest, ray.angleTo(axis));
          nearest = Math.min(nearest, depth);
          farthest = Math.max(farthest, depth);
        }
      }
    }
    key.angle = Math.min(Math.PI / 2.2, widest * 1.4);
    Object.assign(key.shadow.camera, { near: Math.max(1, nearest - 5), far: farthest + 5 });
    key.shadow.camera.updateProjectionMatrix();
  }

  const camera = new THREE.PerspectiveCamera(26, 1, 0.5, radius * 15);
  camera.up.copy(UP);
  camera.position.copy(VIEW).multiplyScalar(radius * 4).add(center);
  // `?quality=high|standard|reduced` pins the tier and turns off automatic downgrade,
  // so reviews and slow software renderers see a fixed, named quality level.
  const pinnedTier = (() => {
    try {
      const value = new URLSearchParams(globalThis.location?.search ?? "").get("quality");
      return Object.hasOwn(TIERS, value) ? value : null;
    } catch { return null; }
  })();
  let tier = pinnedTier ?? (Object.hasOwn(TIERS, sceneConfig.quality) ? sceneConfig.quality : "standard");
  let renderer;
  let composer;
  let environment;
  try {
    renderer = createRenderer(tier === "reduced");
    if (tier !== "reduced") {
      try {
        composer = createComposer(renderer, scene, technical, camera);
      } catch (error) {
        // Keep the reason visible for diagnostics; the scene still renders plainly.
        host.dataset.qualityFallback = `composer: ${error?.message ?? error}`;
        console.warn("Fielddeck: post-processing unavailable, using the reduced tier.", error);
        renderer.dispose();
        renderer = createRenderer(true);
        tier = "reduced";
      }
    }
    environment = createEnvironment(renderer);
  } catch (error) {
    composer?.dispose();
    renderer?.dispose();
    resources.forEach((resource) => resource.dispose());
    throw error;
  }
  // CSS widths × DPR; phones draw every technical line at 1 px.
  let narrowLines = false;
  function updateLineWidths() {
    const dpr = renderer.getPixelRatio();
    technical.traverse((object) => {
      const { material } = object;
      if (material?.isLineMaterial) material.linewidth = (narrowLines ? 1 : material.userData.cssWidth) * dpr;
    });
  }
  function applyTier() {
    const { dpr, shadowSize } = TIERS[tier];
    renderer.setPixelRatio(dpr);
    for (const entry of all) entry.hatchDpr.value = dpr;
    updateLineWidths();
    grid.material.uniforms.dpr.value = dpr;
    renderer.toneMapping = composer ? THREE.NoToneMapping : THREE.NeutralToneMapping;
    renderer.toneMappingExposure = composer ? 1 : EXPOSURE;
    renderer.shadowMap.enabled = key.castShadow = shadowSize > 0;
    if (shadowSize) key.shadow.mapSize.set(shadowSize, shadowSize);
    key.shadow.needsUpdate = true;
    host.dataset.quality = tier;
  }
  applyTier();
  let canvas = renderer.domElement;
  host.prepend(canvas);
  const minimumDistance = radius * 0.2;
  let controls;

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
  let frame = null;
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
  let contactPending = true;
  let orbiting = false;
  let controlsMoving = false;
  let explodePointer = null;
  let sampler = tier === "reduced" || pinnedTier ? null : createFrameSampler(renderer);
  let nextTier = tier;
  const ray = new THREE.Raycaster();
  const [header, bottomChrome, tree, inspector, sheet, legend, options] = [
    ".fd-header", ".fd-bottom", ".fd-tree", ".fd-inspector", ".fd-sheet", ".fd-legend", ".fd-options",
  ]
    .map((selector) => host.querySelector(selector));
  const panels = [header, bottomChrome, tree, inspector, sheet, legend, options];
  const mobileView = window.matchMedia(FIELDDECK_NARROW);
  function invalidate() {
    if (frame === null) frame = requestAnimationFrame(animate);
  }
  const invalidateLayout = () => {
    layoutDirty = true;
    invalidate();
  };

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
    if (nextWidth !== width || nextHeight !== height || resized) {
      if (composer) composer.setSize(nextWidth, nextHeight);
      else renderer.setSize(nextWidth, nextHeight, false);
    }
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
    narrowLines = mobile;
    updateLineWidths();
    invalidateLayout();
  }
  const observer = new ResizeObserver(resize);
  [host, ...panels].forEach((element) => observer.observe(element));
  mobileView.addEventListener("change", resize);
  window.addEventListener("resize", invalidateLayout);
  window.addEventListener("scroll", invalidateLayout, true);
  controls = makeControls(center);
  resize();

  const displays = all.filter(({ row }) => row.part.part_id === focusPart);
  const displayBounds = boundsFor(displays, 0);

  function projectedPose(parts, direction, explode, { face = false, ghost } = {}) {
    const upAxis = face ? FACE_UP : UP;
    // Face view narrows to 4°, close to orthographic, so planes a few millimetres apart in depth
    // project to the same scale as the overlay drawn over them.
    const fov = face ? FACE_FOV : baseFov;
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
    // Face view keeps room for the dimensions on every side and the fit strip below.
    const topInset = Math.min(frameHeight / 4, face ? (mobile ? 64 : 76) : 32);
    const bottomInset = Math.min(frameHeight * (face ? 0.45 : 0.25), face ? (mobile ? 190 : 200) : 32);
    const rect = {
      left: -frameWidth / 2, right: frameWidth / 2,
      top: -frameHeight / 2 + topInset, bottom: frameHeight / 2 - bottomInset,
    };
    const centerY = (rect.top + rect.bottom) / 2;
    // Phones frame the assembly at about 70% of the stage width.
    // Phones fit the assembly to 85% of the stage width.
    const margin = { x: Math.min(frameWidth / 3, face ? (mobile ? 50 : 76) : mobile ? frameWidth * 0.075 : 32), y: 0 };
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
    invalidate();
  }
  function leave() {
    pointer = undefined;
    hovered = undefined;
    pressed = undefined;
    pointerMoved = true;
    invalidate();
  }
  function makeControls(target) {
    const controls = new OrbitControls(camera, canvas);
    controls.target.copy(target);
    controls.enableDamping = true;
    controls.dampingFactor = 0.15;
    controls.minDistance = minimumDistance;
    controls.maxDistance = radius * 13;
    controls.enableZoom = !mobile;
    controls.update();
    controls.addEventListener("start", () => { orbiting = true; });
    controls.addEventListener("end", () => {
      orbiting = false;
      controlsMoving = true;
      invalidate();
    });
    controls.addEventListener("change", () => {
      controlsMoving = true;
      invalidate();
    });
    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerleave", leave);
    canvas.addEventListener("pointercancel", leave);
    canvas.addEventListener("wheel", () => { if (!cameraMove?.faceTransition) cameraMove = null; }, { passive: true });
    return controls;
  }
  function startExplode(event) {
    if (event.target.id === "fd-explode") explodePointer = event.pointerId;
  }
  function settleExplode(event) {
    if (explodePointer === null || event.type !== "blur" && explodePointer !== event.pointerId) return;
    explodePointer = null;
    invalidate();
  }
  host.addEventListener("pointerdown", startExplode);
  window.addEventListener("pointerup", settleExplode);
  window.addEventListener("pointercancel", settleExplode);
  window.addEventListener("blur", settleExplode);

  function changeTier(next) {
    tier = nextTier = next;
    sampler?.dispose();
    sampler = null;
    key.shadow.dispose();
    key.shadow.map = null;
    if (tier === "reduced") {
      composer?.dispose();
      composer = null;
      let replacement;
      let replacementEnvironment;
      try {
        replacement = createRenderer(true);
        replacementEnvironment = createEnvironment(replacement);
      } catch {
        replacement?.dispose();
        replacement = null;
      }
      if (replacement) {
        const target = controls.target.clone();
        controls.dispose();
        environment.dispose();
        renderer.dispose();
        renderer.forceContextLoss();
        renderer = replacement;
        environment = replacementEnvironment;
        canvas.replaceWith(renderer.domElement);
        canvas = renderer.domElement;
        controls = makeControls(target);
        contactPending = true;
      }
    }
    applyTier();
    if (composer) composer.setSize(width, height);
    else renderer.setSize(width, height, false);
  }

  function renderFrame(floor, bake, interacting, orbitMotion, frameStart) {
    const sample = interacting && sampler?.begin(frameStart);
    try {
      if (bake) {
        renderContact(renderer, floor, withAssembledPose, withFeetOnly);
        contactPending = false;
      }
      updateScreenDashes(technical, camera, width, height);
      if (composer) composer.render(tier, orbitMotion);
      else renderPlain();
    } catch (error) {
      if (!composer) throw error;
      host.dataset.qualityFallback = `render: ${error?.message ?? error}`;
      console.warn("Fielddeck: post-processing failed while rendering, using the reduced tier.", error);
      sampler?.end(sample);
      changeTier("reduced");
      if (contactPending) {
        renderContact(renderer, floor);
        contactPending = false;
      }
      renderPlain();
      return;
    }
    sampler?.end(sample);
  }

  // The body goes back to explode 0 for the footprint bake; the feet stay where they are drawn,
  // so each foot keeps its own contact spot in both scales.
  function withAssembledPose(render) {
    const saved = all.map(({ group }) => group.position.clone());
    all.forEach(({ group, row }) => { if (!row.part.part_id.startsWith("foot-")) group.position.set(0, 0, 0); });
    scene.updateMatrixWorld();
    try {
      render();
    } finally {
      all.forEach(({ group }, i) => group.position.copy(saved[i]));
      scene.updateMatrixWorld();
    }
  }

  function withFeetOnly(render) {
    const hidden = all.filter(({ row }) => !row.part.part_id.startsWith("foot-"))
      .flatMap(({ style }) => style.surface).filter((mesh) => mesh.layers.isEnabled(CONTACT_LAYER));
    hidden.forEach((mesh) => mesh.layers.disable(CONTACT_LAYER));
    try {
      render();
    } finally {
      hidden.forEach((mesh) => mesh.layers.enable(CONTACT_LAYER));
    }
  }

  function renderPlain() {
    renderer.setRenderTarget(null);
    renderer.clear();
    renderer.render(scene, camera);
    renderer.render(technical, camera);
  }
  for (const entry of all) {
    entry.style.surface.forEach((mesh) => { mesh.userData.fielddeckKey = entry.row.key; });
  }
  const nextPosition = new THREE.Vector3();
  // "Grid 10 mm" sits at the front-right edge where the grid starts to fade, in the current view.
  function gridLabelPoint() {
    const toCamera = camera.position.clone().sub(center).setZ(0).normalize();
    const right = new THREE.Vector3(-toCamera.y, toCamera.x, 0);
    return toCamera.add(right).normalize().multiplyScalar(radius * 0.52).add(center).setZ(grid.position.z);
  }

  function animate(now) {
    frame = null;
    if (!config) return;
    const frameStart = performance.now();
    const samples = sampler?.collect();
    if (samples?.length === QUALITY_SAMPLE_COUNT) {
      nextTier = chooseTier(samples, tier);
      sampler.dispose();
      sampler = null;
    }
    if (sampler?.waiting()) invalidate();
    const tick = Math.min(50, now - previousTime);
    previousTime = now;
    const { mode, heroStart, reduced, explode, explodeMotion, cameraCue, faceView, ghostDeltaKey, selectedKey } = config;
    const heroElapsed = heroStart == null ? null : Math.max(0, now - heroStart);
    const displayOpacity = heroElapsed === null ? 1 : clamp((heroElapsed - 850) / 250);
    const orbitMotion = orbiting || controlsMoving && config === lastConfig && !cameraMove;
    const userMotion = orbitMotion || explodePointer !== null
      || lastConfig && explode !== lastConfig.explode && !explodeMotion;
    let dirty = config !== lastConfig || resized || layoutDirty || heroElapsed !== null || controlsMoving;
    controlsMoving = false;
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
      // Back to 3D restores the exact camera that was live when Face view opened: position,
      // target, up and field of view. Only a new tour cue or selection asks for a fresh pose.
      if (faceView && !priorCamera) {
        priorCamera = { position: camera.position.clone(), target: controls.target.clone(), up: camera.up.clone(), fov: camera.fov };
      }
      const pose = faceView ? facePose() : newCue || selectionChanged ? assemblyPose(mode, offsetFor) : priorCamera;
      if (!faceView) latestCue = cameraCue;
      moveCamera(pose, now, 650, inOutCubic);
      cameraMove.faceTransition = { up: camera.up.clone(), fov: camera.fov };
    } else if (faceView) {
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
    {
      // Depth precision for AO and flat floors: near scales with distance, far hugs the model.
      const distance = camera.position.distanceTo(controls.target);
      const near = Math.max(1, 0.02 * distance);
      const far = Math.max(4 * radius, distance + 2 * radius);
      if (camera.near !== near || camera.far !== far) {
        camera.near = near;
        camera.far = far;
        camera.updateProjectionMatrix();
      }
    }
    const settling = explodePointer === null && !orbitMotion && !motion && heroElapsed === null && progress === 1;
    if (nextTier !== tier && settling) {
      changeTier(nextTier);
      dirty = true;
    }
    dirty ||= settling && contactPending;
    if (!dirty && !wasAnimating && !pointerMoved) return;
    if (pointer && !pressed && (dirty || pointerMoved)) {
      camera.updateMatrixWorld();
      hovered = getHit(pointer)?.object.userData.fielddeckKey;
    }
    pointerMoved = false;
    canvas.style.cursor = hovered ? "pointer" : "grab";

    camera.updateMatrixWorld();
    grid.visible = !faceView;
    grid.material.uniforms.opacity.value = heroElapsed === null ? 1 : clamp(heroElapsed / 250);

    const pick = [];
    const block = [];
    let floor = Infinity;
    let shadowDirty = firstFrame;
    const displaySelected = config.selectedKeys.some((key) => entries.get(key)?.row.part.part_id === focusPart);
    // Compare focus on a part the user selected: overlapping parts in higher explode layers fade to
    // 22%, everything else recedes, and the selection keeps full-strength edges.
    const focused = mode === "compare" && !faceView && config.focusSelection ? entries.get(selectedKey) : null;
    const screenBox = (entry) => {
      const offset = entry.vector.clone().multiplyScalar(offsetFor(entry));
      const box = { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity };
      for (const x of [entry.bounds.min.x, entry.bounds.max.x]) {
        for (const y of [entry.bounds.min.y, entry.bounds.max.y]) {
          for (const z of [entry.bounds.min.z, entry.bounds.max.z]) {
            const point = new THREE.Vector3(x, y, z).add(offset).project(camera);
            box.left = Math.min(box.left, point.x);
            box.right = Math.max(box.right, point.x);
            box.top = Math.min(box.top, point.y);
            box.bottom = Math.max(box.bottom, point.y);
          }
        }
      }
      return box;
    };
    const focusBox = focused && screenBox(focused);
    const focusHeight = focused && focused.vector.z * offsetFor(focused);
    for (const entry of all) {
      const { row, group, strokes, vector } = entry;
      const removed = row.revision === base && row.delta === "removed";
      const ghost = removed && (mode === "compare" || blend.current.compare > 0);
      // With anything else selected, removed ghosts drop from 70% to 35%.
      const ghostOpacity = selectedKey && !displaySelected && entry.displayOverlay ? 0.5 : 1;
      const weight = row.revision === target ? blend.current.target
        : ghost ? Math.max(blend.current.base, blend.current.compare) * displayOpacity * ghostOpacity : blend.current.base;
      if (entry.overlay) {
        const { object, setOpacity } = entry.overlay;
        object.visible = !faceView && row.key === ghostDeltaKey;
        if (object.visible) {
          // Apply the selected layer's presentation offset to both CAD transforms.
          const selected = entries.get(selectedKey);
          if (selected) object.position.copy(selected.vector).multiplyScalar(offsetFor(selected));
          // Ghosts sit at 35% under a selection: dashes 0.7 × 0.5, small solid loops capped at 40%.
          setOpacity(0.5);
        }
      }
      if (entry.displayOverlay) {
        // Face view: the 5-inch mode shows only its own display; Compare keeps the 7-inch outline
        // at 35%, dashed, as the reference footprint.
        const { object, rim, details } = entry.displayOverlay;
        const faded = mode === "compare" && row.revision === base;
        object.visible = faceView && (mode === "compare" || row.revision === mode);
        if (object.visible) {
          object.position.set(0, 0, 0);
          // Lines composite in linear light, where 0.2 reads as about 35% on screen.
          rim.opacity = faded ? 0.2 : 1;
          details.opacity = faded ? 0.12 : 0.2;
        }
      }
      const visible = !faceView && weight > 0.001;
      const wasCasting = group.visible && entry.style.surface[0].castShadow;
      dirty ||= visible !== group.visible;
      group.visible = strokes.visible = visible;
      if (entry.removed) entry.removed.object.visible = visible && ghost;
      if (!visible) {
        shadowDirty ||= wasCasting;
        continue;
      }
      nextPosition.copy(vector).multiplyScalar(offsetFor(entry));
      const moved = !group.position.equals(nextPosition);
      group.position.copy(nextPosition);
      strokes.position.copy(nextPosition);
      if (entry.removed?.object.visible) {
        entry.removed.object.position.copy(nextPosition);
        entry.removed.setOpacity(weight);
      }
      const selected = selectedKey === row.key;
      const accent = selected && ghostDeltaKey ? 1 : (reduced ? accentProgress : outCubic(accentProgress)) * blend.current.compare;
      // With a selection, the other added and changed parts drop to half strength. The overlay is
      // composited in linear light, where 0.35 reads as about 50% on screen (measured 0.5-0.6).
      let focus = null;
      if (focused && !selected && !ghost) {
        const box = screenBox(entry);
        const overlaps = box.left < focusBox.right && box.right > focusBox.left
          && box.top < focusBox.bottom && box.bottom > focusBox.top;
        focus = overlaps && entry.vector.z * offsetFor(entry) > focusHeight + 0.5 ? { fade: 0.22 } : { recede: 0.4 };
      }
      stylePart(entry, blend.current.compare, weight, ghost, accent, selected || !selectedKey ? 1 : 0.35, focus);
      const casts = entry.style.surface[0].castShadow;
      shadowDirty ||= casts !== wasCasting || casts && moved;
      if (casts) floor = Math.min(floor, entry.bounds.min.z + group.position.z);
      if (row.revision === (mode === "compare" ? target : mode) || mode === "compare" && ghost) {
        pick.push(...entry.style.surface);
        if (!entry.outline && !ghost) block.push(...entry.style.surface);
      }
    }

    // A step that lands after the final animation frame still needs to draw its exact endpoint.
    if (dirty || wasAnimating) {
      grid.position.z = Number.isFinite(floor) ? floor - 0.1 : assembled.min.z - 0.1;
      contactPending ||= shadowDirty;
      if (shadowDirty) key.shadow.needsUpdate = true;
      renderFrame(floor, contactPending && (settling || firstFrame),
        userMotion && heroElapsed === null && !cameraMove, orbitMotion, frameStart);
      pickable = pick;
      opaque = block;
      const placeLabels = layoutDirty || resized || config !== lastConfig || !dirty || now - lastLayout > 60;
      layoutAnnotations(host, camera, entries, width, height, canvasTop, panels, placeLabels, displayOpacity, !cameraMove,
        sceneConfig, grid.visible ? gridLabelPoint() : null,
        faceView ? { mode, fit: faceFit, compact: mobile, sources: glbSources } : null);
      if (placeLabels) lastLayout = now;
    }
    canvas.dataset.fielddeckCanvas = "rendered";
    if (firstFrame) callbacks.onFrame();
    wasAnimating = dirty;
    firstFrame = false;
    lastConfig = config;
    lastHero = heroStart;
    resized = false;
    layoutDirty = false;
    if (dirty || sampler?.waiting()) invalidate();
  }
  let wasAnimating = false;

  return {
    linked: new Set(entries.keys()),
    meshStats: new Map(all.map(({ row, meshStats }) => [row.key, meshStats])),
    ghostLengths: new Map(all.filter(({ overlay }) => overlay).map(({ row, overlay }) => [row.key, overlay.length])),
    ghostMoves: new Map(all.filter(({ overlay }) => overlay).map(({ row, overlay }) => [row.key, overlay.pairs?.length ?? 0])),
    faceFit: faceFit && {
      gaps: faceFit.gaps, minimum: faceFit.minimum, seam: seamLabel(faceFit.seam),
      spacers: faceFit.spacers.length, level: faceFit.level,
      footprint: entries.has(`${base}:part:${focusPart}`)
        ? footprintDeltaPair(entries.get(`${base}:part:${focusPart}`).bounds, entries.get(`${target}:part:${focusPart}`).bounds) : null,
    },
    update: (next) => { config = next; resize(); },
    dispose() {
      if (frame !== null) cancelAnimationFrame(frame);
      observer.disconnect();
      mobileView.removeEventListener("change", resize);
      window.removeEventListener("resize", invalidateLayout);
      window.removeEventListener("scroll", invalidateLayout, true);
      host.removeEventListener("pointerdown", startExplode);
      window.removeEventListener("pointerup", settleExplode);
      window.removeEventListener("pointercancel", settleExplode);
      window.removeEventListener("blur", settleExplode);
      controls.dispose();
      sampler?.dispose();
      composer?.dispose();
      environment.dispose();
      key.shadow.dispose();
      resources.forEach((resource) => resource.dispose());
      renderer.dispose();
      canvas.remove();
      delete host.dataset.quality;
    },
  };
}
