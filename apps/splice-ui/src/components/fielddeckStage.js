import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { fielddeckSceneUrl } from "../api.js";
import { classifyPart, rowForNode, TOUR } from "./fielddeckLogic.js";

const COLORS = {
  custom: 0xc9d1da, vendor_step: 0x7f93a6, envelope: 0x8fa8c4,
  unknown: 0xa6b0bc, proxy: 0xa6b0bc, changed: 0xf2b84b, added: 0x4cc2a8,
  removed: 0xff7a6b, focus: 0x8ab4ff,
};
const UP = new THREE.Vector3(0, 0, 1);
const VIEW = new THREE.Vector3(8.2, -9.6, 6.4).normalize();
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

function solidMaterial(basis, hatch) {
  const material = basis === "custom"
    ? new THREE.MeshPhysicalMaterial({ color: 0xabb6c2, roughness: 0.46, clearcoat: 0.25 })
    : new THREE.MeshStandardMaterial({ color: COLORS.vendor_step, roughness: 0.82, flatShading: true });
  if (hatch) {
    material.onBeforeCompile = (shader) => {
      shader.uniforms.fielddeckHatch = hatch;
      shader.fragmentShader = shader.fragmentShader.replace("#include <common>",
        "#include <common>\nuniform float fielddeckHatch;");
      shader.fragmentShader = shader.fragmentShader.replace("#include <color_fragment>", `
        #include <color_fragment>
        float stripe = fract((gl_FragCoord.x + gl_FragCoord.y) / 12.0);
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.88, 0.53, 0.12),
          (1.0 - smoothstep(0.18, 0.29, stripe)) * fielddeckHatch * 0.46);
      `);
    };
  }
  return material;
}

function edgeMaterial(color, pattern) {
  const options = { color, transparent: true, depthWrite: false };
  return pattern
    ? new THREE.LineDashedMaterial({ ...options, dashSize: pattern[0], gapSize: pattern[1] })
    : new THREE.LineBasicMaterial(options);
}

function stylePart(entry, compare, weight, ghost, emphasis, accent, dimmed) {
  const { basis, outline } = entry;
  const { solid, fill, edge, focus, hull, surface, lines, rings, shells, hatch } = entry.style;
  const translucent = outline || ghost;
  const dim = dimmed ? 1 - compare * (1 - emphasis) * 0.74 : 1;
  const fillAlpha = ghost ? 0.035 : basis === "envelope" ? 0.008 : 0.012;
  const detail = ghost ? COLORS.removed : COLORS[basis];
  const deltaColor = COLORS[entry.row.delta];
  const edgeAlpha = ghost || outline ? 0.82 : basis === "custom" ? 0.46 : 0.62;

  fill.color.setHex(detail);
  fill.opacity = fillAlpha * weight * dim;
  if (solid) {
    solid.opacity = weight * dim;
    const transparent = solid.opacity < 0.999;
    if (solid.transparent !== transparent) {
      solid.transparent = transparent;
      solid.needsUpdate = true;
    }
    solid.depthWrite = weight > 0.55;
  }

  const edgeVariant = ghost ? edge.ghost : edge.base;
  edgeVariant.color.setHex(detail);
  if (deltaColor && !ghost && accent > 0) edgeVariant.color.lerp(entry.accentColor, accent);
  edgeVariant.opacity = edgeAlpha * weight * dim;
  focus.opacity = emphasis * weight;
  if (hatch) hatch.value = accent;
  if (hull) {
    hull.opacity = accent * weight * 0.68;
    hull.visible = hull.opacity > 0.01 && !ghost;
  }

  for (const mesh of surface) {
    mesh.material = translucent ? fill : solid;
    mesh.castShadow = !translucent && weight > 0.99 && dim > 0.9;
    mesh.receiveShadow = !translucent;
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
        const vector = new THREE.Vector3().fromArray(row.part.explode_vector_mm);
        const pattern = basis === "envelope" ? [4, 2.5] : outline ? [1.3, 2.8] : null;
        const hatch = row.delta === "changed" ? { value: 0 } : null;
        const hull = ["added", "changed"].includes(row.delta) && !outline
          ? own(new THREE.MeshBasicMaterial({
              color: COLORS[row.delta], side: THREE.BackSide, transparent: true, depthWrite: false,
            })) : null;
        entry = {
          row, basis, outline, group, vector, bounds: new THREE.Box3(), emphasis: 0, hover: 0,
          accentColor: new THREE.Color(COLORS[row.delta]),
          style: {
            solid: outline ? null : own(solidMaterial(basis, hatch)),
            fill: own(new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide })),
            edge: { base: own(edgeMaterial(COLORS[basis], pattern)), ghost: own(edgeMaterial(COLORS.removed, [3.25, 2.25])) },
            focus: own(edgeMaterial(COLORS.focus, pattern)),
            hull, hatch, surface: [], lines: [], rings: [], shells: [],
          },
        };
        entries.set(row.key, entry);
        scene.add(group);
      }

      // Bake the GLB's node hierarchy into mm so presentation offsets remain in scene axes.
      const geometry = own(source.geometry.clone().applyMatrix4(new THREE.Matrix4().multiplyMatrices(scale, source.matrixWorld)));
      geometry.computeBoundingBox();
      entry.bounds.union(geometry.boundingBox);
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
        shell.scale.setScalar(1.022);
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
  for (const entry of entries) {
    bounds.union(entry.bounds.clone().translate(entry.vector.clone().multiplyScalar(explode)));
  }
  return bounds;
}

function modelWeights(mode) {
  return { seven: mode === "7" ? 1 : 0, five: mode === "7" ? 0 : 1, compare: mode === "compare" ? 1 : 0 };
}

function layoutCallouts(host, camera, entries, meshes, width, height, ray) {
  const cards = [...host.querySelectorAll("[data-anchor]")];
  if (!cards.length) return;
  const ndc = new THREE.Vector2();
  const world = new THREE.Vector3();
  const project = (point) => {
    const p = point.clone().project(camera);
    return { x: (p.x + 1) * width / 2, y: (1 - p.y) * height / 2, z: p.z };
  };
  const hitAt = (x, y, objects) => {
    ray.setFromCamera(ndc.set(x * 2 / width - 1, 1 - y * 2 / height), camera);
    return ray.intersectObjects(objects, false)[0];
  };
  const columns = [[], []];
  const gutter = 12;
  const gap = 10;
  const marginTop = 12;
  const marginBottom = height - 14;

  for (const card of cards) {
    const line = host.querySelector(`[data-leader="${card.dataset.callout}"]`);
    const entry = entries.get(card.dataset.anchor);
    if (!entry?.group.visible) {
      card.style.visibility = line.style.visibility = "hidden";
      continue;
    }
    const center = entry.bounds.getCenter(world).add(entry.group.position);
    const point = project(center);
    if (point.z < -1 || point.z > 1 || point.x < 0 || point.x > width || point.y < 0 || point.y > height) {
      card.style.visibility = line.style.visibility = "hidden";
      continue;
    }
    const side = Number(point.x >= width / 2);
    const size = card.getBoundingClientRect();
    const item = { card, line, entry, point, w: size.width, h: size.height };
    columns[side].push(item);
    card.style.visibility = line.style.visibility = "visible";
  }

  const stackHeight = (column) => column.reduce((sum, item) => sum + item.h + gap, -gap);
  for (const [side, column] of columns.entries()) {
    const other = columns[1 - side];
    if (stackHeight(column) <= marginBottom - marginTop) continue;
    const moved = [...column].sort((a, b) => Math.abs(a.point.x - width / 2) - Math.abs(b.point.x - width / 2))
      .find((item) => stackHeight([...other, item]) <= marginBottom - marginTop);
    if (moved) other.push(...column.splice(column.indexOf(moved), 1));
  }
  for (const [side, column] of columns.entries()) {
    column.sort((a, b) => a.point.y - b.point.y);
    let next = marginTop;
    for (const item of column) {
      item.y = Math.max(next, Math.min(marginBottom - item.h, item.point.y - item.h / 2));
      next = item.y + item.h + gap;
    }
    next = marginBottom;
    for (const item of [...column].reverse()) {
      item.y = Math.min(item.y, next - item.h);
      next = item.y - gap;
    }
    for (const item of column) {
      const { entry, point, card, line, w, h, y } = item;
      const x = side ? width - w - gutter : gutter;
      const edgeX = side ? x : x + w;
      const edgeY = y + Math.min(h / 2, 36);
      const direction = side ? 1 : -1;
      card.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;

      // Pick the outer visible face when possible, then lift the leader into the annotation column.
      let surface;
      for (const offset of [18, 10, 4, 0]) {
        surface = hitAt(point.x + direction * offset, point.y, entry.style.surface);
        if (surface) break;
      }
      const anchor = surface ? project(surface.point) : point;
      const first = hitAt(anchor.x, anchor.y, meshes);
      const occluded = Boolean(first && !entry.style.surface.includes(first.object)
        && (!surface || first.distance < surface.distance - 0.1));
      const knee = edgeX - direction * Math.min(36, Math.max(0, direction * (edgeX - anchor.x)));
      const points = [[anchor.x, anchor.y], [knee, edgeY], [edgeX, edgeY]];
      // Break the leader over intervening geometry so it cannot connect visually to another part.
      const path = [];
      for (let i = 1; i < points.length; i++) {
        const [sx, sy] = points[i - 1];
        const [ex, ey] = points[i];
        const steps = Math.max(1, Math.ceil(Math.hypot(ex - sx, ey - sy) / 18));
        for (let j = 0; j < steps; j++) {
          const from = j / steps;
          const to = (j + 1) / steps;
          const middle = (from + to) / 2;
          const hit = hitAt(THREE.MathUtils.lerp(sx, ex, middle), THREE.MathUtils.lerp(sy, ey, middle), meshes);
          if (hit && !entry.style.surface.includes(hit.object)) continue;
          path.push(`M${THREE.MathUtils.lerp(sx, ex, from)},${THREE.MathUtils.lerp(sy, ey, from)}L${THREE.MathUtils.lerp(sx, ex, to)},${THREE.MathUtils.lerp(sy, ey, to)}`);
        }
      }
      line.querySelector("path").setAttribute("d", path.join(" "));
      const ring = line.querySelector("circle");
      ring.setAttribute("cx", anchor.x);
      ring.setAttribute("cy", anchor.y);
      ring.setAttribute("opacity", occluded ? 0.4 : 1);
    }
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

  const extended = boundsFor(all, 1);
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
  controls.maxDistance = radius * 9;
  controls.update();

  let config;
  let lastConfig;
  let width = 1;
  let height = 1;
  let resized = true;
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

  function resize() {
    width = Math.max(1, host.clientWidth);
    height = Math.max(1, host.clientHeight);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    resized = true;
  }
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  resize();

  function fit(bounds, target, angle, padding) {
    const direction = VIEW.clone().applyAxisAngle(UP, THREE.MathUtils.degToRad(angle));
    const right = UP.clone().cross(direction).normalize();
    const up = direction.clone().cross(right);
    const tangent = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * padding;
    let distance = controls.minDistance;
    for (const x of [bounds.min.x, bounds.max.x]) {
      for (const y of [bounds.min.y, bounds.max.y]) {
        for (const z of [bounds.min.z, bounds.max.z]) {
          const p = new THREE.Vector3(x, y, z).sub(target);
          distance = Math.max(distance, p.dot(direction) + Math.max(
            Math.abs(p.dot(right)) / (tangent * camera.aspect),
            Math.abs(p.dot(up)) / tangent,
          ));
        }
      }
    }
    return { target, position: direction.multiplyScalar(distance).add(target) };
  }

  function heroPose(explode, turn) {
    const bounds = boundsFor(all, explode);
    const target = bounds.getCenter(new THREE.Vector3())
      .lerp(new THREE.Vector3().fromArray(TOUR[0].target), 0.26 * turn);
    return fit(bounds, target, TOUR[0].angle * turn, width < 520 ? 0.91 : 0.84);
  }

  function tourPose(stopIndex) {
    const stop = TOUR[stopIndex];
    let framed = all.filter(({ row }) => row.revision === (config.mode === "7" ? "7" : "5"));
    if (!framed.length) framed = all;
    const targetItems = framed.filter(({ row }) => config.selectedKeys.includes(row.key)
      || stop.diff && row.delta === stop.diff);
    const bounds = boundsFor(targetItems.length ? targetItems : framed, config.explode);
    bounds.expandByScalar(stopIndex === 1 ? 42 : 65);
    const target = bounds.getCenter(new THREE.Vector3());
    return fit(bounds, target, stop.angle, 0.8);
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
  const layers = all.map(({ bounds }) => bounds.getCenter(new THREE.Vector3()).z);
  const bottom = Math.min(...layers);
  const layerRange = Math.max(1, Math.max(...layers) - bottom);

  function animate(now) {
    frame = requestAnimationFrame(animate);
    if (!config) return;
    const tick = Math.min(50, now - previousTime);
    previousTime = now;
    const { mode, heroStart, reduced, explode, cameraCue, selectedKeys } = config;
    const heroElapsed = heroStart == null ? null : now - heroStart;
    let dirty = config !== lastConfig || resized || heroElapsed !== null;
    if (!blend || mode !== blend.mode) {
      const next = modelWeights(mode);
      blend = { mode, start: now, from: blend?.current ?? next, to: next, current: next };
    }
    const progress = clamp((now - blend.start) / (reduced ? 100 : 450));
    const mix = inOutCubic(progress);
    blend.current = {
      seven: THREE.MathUtils.lerp(blend.from.seven, blend.to.seven, mix),
      five: THREE.MathUtils.lerp(blend.from.five, blend.to.five, mix),
      compare: THREE.MathUtils.lerp(blend.from.compare, blend.to.compare, mix),
    };
    const accentProgress = clamp((now - blend.start - (reduced ? 0 : 700)) / (reduced ? 100 : 180));
    dirty ||= progress < 1 || (mode === "compare" && accentProgress < 1);

    if (heroElapsed !== null) {
      setCamera(heroPose(outCubic(clamp((heroElapsed - 400) / 1100)), damped(clamp((heroElapsed - 4200) / 800))));
    } else if (cameraCue && cameraCue !== latestCue) {
      latestCue = cameraCue;
      const pose = tourPose(cameraCue.stopIndex);
      cameraMove = { pose, start: now, from: camera.position.clone(), target: controls.target.clone() };
    } else if (firstFrame || lastHero !== null) {
      setCamera(heroPose(explode, mode === "compare" ? 1 : 0));
    } else if (resized && !cameraMove) {
      const direction = camera.position.clone().sub(controls.target);
      const scale = Math.max(1, 0.9 / camera.aspect);
      if (direction.length() < radius * 2.6 * scale) {
        camera.position.copy(direction.setLength(radius * 2.6 * scale).add(controls.target));
      }
    }
    if (cameraMove) {
      const progress = reduced ? 1 : clamp((now - cameraMove.start) / 1600);
      setCamera(cameraMove.pose, damped(progress), cameraMove.from, cameraMove.target);
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
    for (const [i, entry] of all.entries()) {
      const { row, group, vector } = entry;
      const removed = row.revision === "7" && row.delta === "removed";
      const ghost = removed && (mode === "compare" || blend.current.compare > 0 || heroElapsed >= 1600);
      const weight = row.revision === "5" ? blend.current.five
        : ghost ? Math.max(blend.current.seven, blend.current.compare) : blend.current.seven;
      const visible = weight > 0.001;
      dirty ||= visible !== group.visible;
      group.visible = visible;
      if (!visible) continue;
      const selectedOrHovered = selected.has(row.key) || hovered === row.key;
      const emphasis = Number(selected.has(row.key)) || (selectedOrHovered ? 0.65 : 0);
      const distance = reduced ? 1 : tick / (selected.has(row.key) ? 160 : 120);
      const step = (value, target) => value + Math.sign(target - value) * Math.min(distance, Math.abs(target - value));
      dirty ||= emphasis !== entry.emphasis || Number(hovered === row.key) !== entry.hover;
      entry.emphasis = step(entry.emphasis, emphasis);
      entry.hover = step(entry.hover, Number(hovered === row.key));
      const delay = 70 * Math.round(2 * (layers[i] - bottom) / layerRange);
      const offset = heroElapsed !== null
        ? outCubic(clamp((heroElapsed - 400 - delay) / (1100 - delay))) : explode;
      group.position.copy(vector).multiplyScalar(offset);
      group.position.addScaledVector(vector.clone().normalize(), 2 * outCubic(entry.hover));
      const dimmed = row.revision === "5" && row.delta === "unchanged";
      const accent = outCubic(accentProgress) * blend.current.compare;
      stylePart(entry, blend.current.compare, weight, ghost, entry.emphasis, accent, dimmed);
      if (row.revision === (mode === "7" ? "7" : "5") || mode === "compare" && ghost) {
        pick.push(...entry.style.surface);
        if (!entry.outline && !ghost) block.push(...entry.style.surface);
      }
    }

    // A step that lands after the final animation frame still needs to draw its exact endpoint.
    if (dirty || wasAnimating) {
      renderer.render(scene, camera);
      pickable = pick;
      opaque = block;
      if (resized || config !== lastConfig || now - lastLayout > 60) {
        layoutCallouts(host, camera, entries, opaque, width, height, ray);
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
  }
  let wasAnimating = false;
  frame = requestAnimationFrame(animate);

  return {
    linked: new Set(entries.keys()),
    update: (next) => { config = next; },
    dispose() {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      environment.dispose();
      key.shadow.dispose();
      resources.forEach((resource) => resource.dispose());
      renderer.dispose();
      canvas.remove();
    },
  };
}
