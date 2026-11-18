import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { HorizontalBlurShader } from "three/examples/jsm/shaders/HorizontalBlurShader.js";
import { VerticalBlurShader } from "three/examples/jsm/shaders/VerticalBlurShader.js";
import { fielddeckSceneUrl } from "../api.js";
import { classifyPart, DEFAULT_EXPLODE, explodeGroupOffsets, FIELDDECK_NARROW, placeCallouts, rowForNode, TOUR } from "./fielddeckLogic.js";

const COLORS = {
  custom: 0x35302a, vendor_step: 0x626b77, envelope: 0x8fa8c4,
  unknown: 0xa6b0bc, proxy: 0xa6b0bc, changed: 0xf2b84b, added: 0x4cc2a8,
  removed: 0xff7a6b, focus: 0x8ab4ff,
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

function solidMaterial(basis, displayTop) {
  if (basis === "custom") {
    return new THREE.MeshPhysicalMaterial({ color: 0xc5bdb2, roughness: 0.68, clearcoat: 0.07 });
  }
  if (!displayTop) {
    return new THREE.MeshStandardMaterial({ color: COLORS.vendor_step, roughness: 0.82, flatShading: true });
  }
  const material = new THREE.MeshPhysicalMaterial({ color: 0x39414a, roughness: 0.82, flatShading: true });
  // Shade the existing vendor mesh's front face in its baked CAD coordinates.
  material.onBeforeCompile = (shader) => {
    shader.uniforms.fielddeckDisplayTop = displayTop;
    shader.uniforms.fielddeckGlass = { value: new THREE.Color(0x101319) };
    shader.vertexShader = shader.vertexShader.replace("#include <common>",
      "#include <common>\nvarying vec2 fielddeckFace;");
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>",
      "#include <begin_vertex>\nfielddeckFace = vec2(position.z, normal.z);");
    shader.fragmentShader = shader.fragmentShader.replace("#include <common>", `
      #include <common>
      varying vec2 fielddeckFace;
      uniform float fielddeckDisplayTop;
      uniform vec3 fielddeckGlass;
    `);
    shader.fragmentShader = shader.fragmentShader.replace("#include <color_fragment>", `
      #include <color_fragment>
      float glass = step(fielddeckDisplayTop - 2.5, fielddeckFace.x) * smoothstep(0.85, 0.99, fielddeckFace.y);
      diffuseColor.rgb = mix(diffuseColor.rgb, fielddeckGlass, glass);
    `);
    shader.fragmentShader = shader.fragmentShader.replace("#include <roughnessmap_fragment>",
      "#include <roughnessmap_fragment>\nroughnessFactor = mix(roughnessFactor, 0.22, glass);");
  };
  return material;
}

function edgeMaterial(color, pattern) {
  const options = { color, transparent: true, depthWrite: false, toneMapped: false };
  return pattern
    ? new THREE.LineDashedMaterial({ ...options, dashSize: pattern[0], gapSize: pattern[1] })
    : new THREE.LineBasicMaterial(options);
}

function stylePart(entry, compare, weight, ghost, emphasis, accent) {
  const { basis, outline, row } = entry;
  const { solid, baseColor, fill, edge, focus, hull, surface, lines, rings, shells } = entry.style;
  const translucent = outline || ghost;
  const dim = row.delta === "unchanged" ? 1 - compare * (1 - emphasis) * 0.38 : 1;
  const fillAlpha = ghost ? 0.035 : basis === "envelope" ? 0.008 : 0.012;
  const detail = ghost ? COLORS.removed : COLORS[basis];
  const edgeAlpha = ghost || outline ? 0.82 : basis === "custom" ? 0.32 : 0.48;
  const highlight = !ghost && (row.delta === "changed" || row.delta === "added");

  fill.color.setHex(detail);
  fill.opacity = fillAlpha * weight * dim;
  if (solid) {
    solid.color.copy(baseColor);
    if (row.delta === "changed") solid.color.lerp(entry.accentColor, accent * 0.12);
    solid.color.multiplyScalar(dim);
    solid.opacity = weight;
    const transparent = weight < 0.999;
    if (solid.transparent !== transparent) {
      solid.transparent = transparent;
      solid.needsUpdate = true;
    }
    solid.depthWrite = weight > 0.55;
  }

  const edgeVariant = ghost ? edge.ghost : edge.base;
  edgeVariant.color.setHex(detail);
  if (highlight) edgeVariant.color.lerp(entry.accentColor, accent);
  const opacity = ghost ? edgeAlpha + 0.18 * emphasis : THREE.MathUtils.lerp(edgeAlpha, 0.9, highlight ? accent : 0);
  edgeVariant.opacity = opacity * weight * dim;
  focus.opacity = ghost ? 0 : emphasis * weight * (highlight ? 1 - 0.75 * accent : 1);
  if (hull) {
    hull.opacity = accent * weight * 0.62;
    hull.visible = hull.opacity > 0.01 && !ghost;
  }

  for (const mesh of surface) {
    mesh.material = translucent ? fill : solid;
    mesh.castShadow = !translucent && weight >= 0.49;
    mesh.receiveShadow = !translucent;
    if (mesh.castShadow) mesh.layers.enable(CONTACT_LAYER);
    else mesh.layers.disable(CONTACT_LAYER);
  }
  lines.forEach((line) => { line.material = edgeVariant; });
  rings.forEach((line) => { line.visible = focus.opacity > 0.01; });
  shells.forEach((mesh) => { mesh.visible = hull.visible; });
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
        const pattern = basis === "envelope" ? [4, 2.5] : outline ? [1.3, 2.8] : null;
        const displayTop = basis === "vendor_step" && row.part.part_id === "display" ? { value: 0 } : null;
        const solid = outline ? null : own(solidMaterial(basis, displayTop));
        const hull = row.delta === "added" && !outline
          ? own(new THREE.MeshBasicMaterial({
              color: COLORS.added, side: THREE.BackSide, transparent: true, depthWrite: false, toneMapped: false,
            })) : null;
        entry = {
          row, basis, outline, group, vector, displayTop, bounds: new THREE.Box3(), emphasis: 0, hover: 0,
          accentColor: new THREE.Color(COLORS[row.delta]),
          style: {
            solid, baseColor: solid?.color.clone(),
            fill: own(new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide })),
            edge: { base: own(edgeMaterial(COLORS[basis], pattern)), ghost: own(edgeMaterial(COLORS.removed, [3.25, 2.25])) },
            focus: own(edgeMaterial(COLORS.focus, pattern)),
            hull, surface: [], lines: [], rings: [], shells: [],
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
      if (entry.displayTop) entry.displayTop.value = entry.bounds.max.z;
      const { style, group } = entry;
      const mesh = new THREE.Mesh(geometry, style.solid ?? style.fill);
      style.surface.push(mesh);
      group.add(mesh);

      const edges = own(new THREE.EdgesGeometry(geometry, 28));
      const line = new THREE.LineSegments(edges, style.edge.base);
      const ring = new THREE.LineSegments(edges, style.focus);
      line.computeLineDistances();
      ring.renderOrder = 2;
      style.lines.push(line);
      style.rings.push(ring);
      group.add(line, ring);

      if (style.hull) {
        const shell = new THREE.Mesh(geometry, style.hull);
        const center = geometry.boundingBox.getCenter(new THREE.Vector3());
        shell.scale.setScalar(1.012);
        shell.position.copy(center).multiplyScalar(1 - shell.scale.x);
        style.shells.push(shell);
        group.add(shell);
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

function layoutCallouts(host, camera, entries, meshes, width, height, ray, panels) {
  const annotations = [...host.querySelectorAll("[data-anchor]")];
  if (!annotations.length) return [];
  const origin = host.getBoundingClientRect();
  const viewport = {
    left: Math.max(0, -origin.left),
    top: Math.max(0, -origin.top),
    right: Math.min(origin.width, document.documentElement.clientWidth - origin.left),
    bottom: Math.min(origin.height, document.documentElement.clientHeight - origin.top),
  };
  const occupied = panels.map((panel) => panel.getBoundingClientRect())
    .filter((rect) => rect.width && rect.height)
    .map(({ left, right, top, bottom }) => ({
      left: left - origin.left, right: right - origin.left,
      top: top - origin.top, bottom: bottom - origin.top,
    }));
  const ndc = new THREE.Vector2();
  const project = (point) => {
    const p = point.project(camera);
    return { x: (p.x + 1) * width / 2, y: (1 - p.y) * height / 2, z: p.z };
  };
  const hitAt = (x, y, objects) => {
    ray.setFromCamera(ndc.set(x * 2 / width - 1, 1 - y * 2 / height), camera);
    return ray.intersectObjects(objects, false)[0];
  };
  const covered = (x, y, surface, hit) => {
    const first = hitAt(x, y, meshes);
    return first && !surface.includes(first.object) && (!hit || first.distance < hit.distance - 0.1);
  };

  const inputs = annotations.map((annotation) => {
    const entry = entries.get(annotation.dataset.anchor);
    if (!entry?.group.visible) return {};
    const bounds = entry.bounds.clone().translate(entry.group.position);
    const anchor = project(bounds.getCenter(new THREE.Vector3()));
    if (anchor.z < -1 || anchor.z > 1) return {};
    const corners = [];
    for (const x of [bounds.min.x, bounds.max.x]) {
      for (const y of [bounds.min.y, bounds.max.y]) {
        for (const z of [bounds.min.z, bounds.max.z]) {
          corners.push(project(new THREE.Vector3(x, y, z)));
        }
      }
    }
    const left = Math.min(...corners.map(({ x }) => x));
    const right = Math.max(...corners.map(({ x }) => x));
    const outline = corners.every(({ z }) => z >= -1 && z <= 1) ? {
      left: left - 5, right: right + 5,
      top: Math.min(...corners.map(({ y }) => y)) - 5,
      bottom: Math.max(...corners.map(({ y }) => y)) + 5,
    } : null;
    return { entry, anchor, outline, left, right };
  });

  const labels = placeCallouts(viewport, occupied, inputs.map(({ anchor, outline }, i) => {
    if (!outline) return {};
    const { width, height } = annotations[i].querySelector(".fd-label").getBoundingClientRect();
    return width && height ? { anchor, outline, width, height } : {};
  }));

  const cards = placeCallouts(viewport, [...occupied, ...labels.filter(Boolean).map(({ rect }) => rect)],
    inputs.map(({ anchor, entry, left, right }, i) => {
      if (!anchor || labels[i]) return {};
      const { width, height } = annotations[i].querySelector(".fd-callout").getBoundingClientRect();
      if (!width || !height) return {};

      // Use the part's silhouette on the side facing the fallback card when the center ray hits.
      const surface = entry.style.surface;
      const centerHit = hitAt(anchor.x, anchor.y, surface);
      function silhouette(outer) {
        if (!centerHit) return anchor;
        let inside = anchor.x;
        for (let i = 0; i < 8; i++) {
          const x = (inside + outer) / 2;
          if (hitAt(x, anchor.y, surface)) inside = x;
          else outer = x;
        }
        return { x: inside, y: anchor.y };
      }
      return { width, height, anchor, leftAnchor: silhouette(left), rightAnchor: silhouette(right) };
    }));

  const folded = [];
  for (const [i, annotation] of annotations.entries()) {
    const line = host.querySelector(`[data-leader="${annotation.dataset.callout}"]`);
    const label = annotation.querySelector(".fd-label");
    const card = annotation.querySelector(".fd-callout");
    const placement = labels[i] ?? cards[i];
    label.style.visibility = labels[i] ? "visible" : "hidden";
    card.style.visibility = cards[i] ? "visible" : "hidden";
    const { outline, entry, anchor } = inputs[i];
    line.style.visibility = outline || placement ? "visible" : "hidden";
    line.dataset.card = Boolean(cards[i]);
    const dimension = line.querySelector(".fd-dimension");
    const ticks = line.querySelector(".fd-ticks");
    if (outline) {
      const { left, top, right, bottom } = outline;
      const surface = entry.style.surface;
      const hit = hitAt(anchor.x, anchor.y, surface);
      const opacity = hit && covered(anchor.x, anchor.y, surface, hit) ? 0.4 : 1;
      dimension.setAttribute("opacity", opacity);
      ticks.setAttribute("opacity", opacity);
      dimension.setAttribute("d", `M${left},${top}H${right}V${bottom}H${left}Z`);
      ticks.setAttribute("d", [left, right].flatMap((x) => [top, bottom].map((y) =>
        `M${x - 3},${y}h6 M${x},${y - 3}v6`,
      )).join(" "));
    } else {
      dimension.removeAttribute("d");
      ticks.removeAttribute("d");
    }

    const path = line.querySelector(".fd-leader");
    if (!placement) {
      path.removeAttribute("d");
      folded.push(annotation.dataset.calloutKey);
      continue;
    }

    const { rect, leader } = placement;
    const text = labels[i] ? label : card;
    text.style.transform = `translate(${rect.left}px, ${rect.top}px)`;
    path.setAttribute("d", leader.map(({ x, y }, j) => `${j ? "L" : "M"}${x},${y}`).join(" "));
    if (!cards[i]) continue;
    const { x, y } = leader.at(-1);
    const surface = entry.style.surface;
    const hit = hitAt(x, y, surface);
    const ring = line.querySelector("circle");
    ring.setAttribute("cx", x);
    ring.setAttribute("cy", y);
    ring.setAttribute("opacity", !hit || covered(x, y, surface, hit) ? 0.4 : 1);
  }
  return folded;
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
  const [header, bottomChrome, tree, inspector] = [".fd-header", ".fd-bottom", ".fd-tree", ".fd-inspector"]
    .map((selector) => host.querySelector(selector));
  const panels = [header, bottomChrome, tree, inspector];
  const mobileView = window.matchMedia(FIELDDECK_NARROW);
  const invalidateLayout = () => { layoutDirty = true; };

  function resize() {
    const nextWidth = Math.max(1, host.clientWidth);
    const nextHeight = Math.max(1, host.clientHeight);
    const origin = host.getBoundingClientRect().top;
    const upper = header.getBoundingClientRect().bottom - origin;
    const openSheets = mobileView.matches
      ? [tree, inspector].map((panel) => panel.getBoundingClientRect()).filter((rect) => rect.height)
      : [];
    const lower = Math.min(bottomChrome.getBoundingClientRect().top, ...openSheets.map(({ top }) => top)) - origin;
    const nextFrameHeight = Math.max(1, lower - upper);
    const nextFrameCenter = (upper + lower) / 2;
    if (nextWidth !== width || nextHeight !== height) renderer.setSize(nextWidth, nextHeight, false);
    resized ||= width !== nextWidth || height !== nextHeight || Math.abs(frameHeight - nextFrameHeight) > 1
      || Math.abs(frameCenter - nextFrameCenter) > 1 || mobile !== mobileView.matches;
    width = nextWidth;
    height = nextHeight;
    mobile = mobileView.matches;
    frameHeight = nextFrameHeight;
    frameCenter = nextFrameCenter;
    camera.setViewOffset(width, height, mobile ? 0 : width * 0.012, height / 2 - frameCenter, width, height);
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
    const horizontalFit = tangent * camera.aspect * horizontal;
    const verticalFit = tangent * Math.min(1, frameHeight / height) * 0.9;
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
    const framed = modeEntries[mode].length ? modeEntries[mode] : all;
    return fit(boundsFor(framed, explode), TOUR[0].angle * turn, mobile ? 0.93 : 0.76);
  }

  function tourPose(stopIndex) {
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
    const { mode, heroStart, reduced, explode, explodeMotion, cameraCue, selectedKeys } = config;
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

    const selected = new Set(selectedKeys);
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
      const selectedOrHovered = selected.has(row.key) || hovered === row.key;
      const emphasis = Number(selected.has(row.key)) || (selectedOrHovered ? 0.65 : 0);
      const distance = reduced ? 1 : tick / (selected.has(row.key) ? 160 : 120);
      const step = (value, target) => value + Math.sign(target - value) * Math.min(distance, Math.abs(target - value));
      dirty ||= emphasis !== entry.emphasis || Number(hovered === row.key) !== entry.hover;
      entry.emphasis = step(entry.emphasis, emphasis);
      entry.hover = step(entry.hover, Number(hovered === row.key));
      const length = vector.length();
      const offset = offsetFor(entry) + (length && !reduced ? 2 * outCubic(entry.hover) / length : 0);
      nextPosition.copy(vector).multiplyScalar(offset);
      const moved = !group.position.equals(nextPosition);
      group.position.copy(nextPosition);
      const accent = (reduced ? accentProgress : outCubic(accentProgress)) * blend.current.compare;
      stylePart(entry, blend.current.compare, weight, ghost, entry.emphasis, accent);
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
      if (!mobile && (layoutDirty || resized || config !== lastConfig || !dirty || now - lastLayout > 60)) {
        callbacks.onCalloutLayout(layoutCallouts(host, camera, entries, opaque, width, height, ray, panels));
        lastLayout = now;
      }
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
