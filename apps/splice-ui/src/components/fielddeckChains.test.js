// @vitest-environment node
// The worker path must draw exactly what the main thread drew: same chains, same points, same
// order. The fixture is real geometry, the Fielddeck 7-inch and 5-inch GLBs, edged as the stage edges them.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { describe, expect, it } from "vitest";
import { cullCoincidentChains, cullIsolatedChains, ghostOutlineLoops, weldEdgeChains } from "./fielddeckLogic.js";
import { decodeChains, encodeChains, runChainJob, runChainJobs } from "./fielddeckChains.js";

const root = fileURLToPath(new URL("../../../../projects/cyberdeck-real-trial-20261020/", import.meta.url));
const MM = 1000; // both GLBs are in metres; the stage bakes them to millimetres

async function edgesByNode(file) {
  const bytes = readFileSync(root + file);
  const gltf = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), "");
  gltf.scene.updateMatrixWorld(true);
  const scale = new THREE.Matrix4().makeScale(MM, MM, MM);
  const out = new Map();
  gltf.scene.traverse((mesh) => {
    if (!mesh.isMesh) return;
    let geometry = mesh.geometry.clone().applyMatrix4(new THREE.Matrix4().multiplyMatrices(scale, mesh.matrixWorld));
    if (geometry.getAttribute("color")) geometry.deleteAttribute("color");
    geometry = mergeVertices(geometry, 1e-4);
    const edges = new THREE.EdgesGeometry(geometry, 20).getAttribute("position").array;
    let name = mesh.name;
    for (let node = mesh; node && !gltf.parser.associations.get(node)?.nodes && node.parent; node = node.parent) name = node.parent.name;
    const values = out.get(name) ?? [];
    for (const value of edges) values.push(value); // as the stage collects ghostEdges: plain numbers
    out.set(name, values);
  });
  return out;
}

// Exactly the expressions makeEntries ran on the main thread before the worker existed.
const mainThread = {
  diff: (edges, paired) => cullIsolatedChains(cullCoincidentChains(weldEdgeChains(edges), paired)),
  overlay: (edges, paired) => cullIsolatedChains(cullCoincidentChains(weldEdgeChains(edges), paired, { simplify: true })),
  removed: (edges) => ghostOutlineLoops(edges),
};

// The worker's round trip: transfer as Float64Array, run, encode, decode.
function throughWorkerPath(job) {
  const wire = { kind: job.kind, edges: Float64Array.from(job.edges), paired: job.paired ? Float64Array.from(job.paired) : null };
  return decodeChains(encodeChains(runChainJob(wire)));
}

describe("fielddeck chain jobs", () => {
  it("draw the same chains in the worker as on the main thread, on the real Fielddeck parts", async () => {
    const [seven, five] = await Promise.all([edgesByNode("digital_v1/cad/FIELDDECK_7.glb"), edgesByNode("display_swap/cad/FIELDDECK_5.glb")]);
    const shared = [...five.keys()].filter((name) => seven.has(name));
    // The changed faces and trays carry the diff-only violet and the old-revision overlay.
    const changed = shared.filter((name) => /face_rear|tray_rear/i.test(name));
    expect(changed.length).toBeGreaterThan(0);
    let compared = 0;
    for (const name of changed) {
      for (const [kind, edges, paired] of [["diff", five.get(name), seven.get(name)], ["overlay", seven.get(name), five.get(name)]]) {
        const expected = mainThread[kind](edges, paired);
        expect(throughWorkerPath({ kind, edges, paired })).toEqual(expected);
        compared += expected.length;
      }
    }
    // The removed 7-inch display's outline loops.
    const removed = [...seven.keys()].find((name) => /touch_display.*7|display_7|7inch/i.test(name)) ?? [...seven.keys()].at(-1);
    expect(throughWorkerPath({ kind: "removed", edges: seven.get(removed) })).toEqual(mainThread.removed(seven.get(removed)));
    expect(compared).toBeGreaterThan(0);
  }, 120000);

  it("falls back to the main thread, with the same result, where no Worker exists", async () => {
    const edges = [0, 0, 0, 10, 0, 0, 10, 0, 0, 10, 10, 0, 10, 10, 0, 0, 10, 0, 0, 10, 0, 0, 0, 0];
    const paired = [0, 0, 0, 10, 0, 0];
    const [diff, removed] = await runChainJobs([{ kind: "diff", edges, paired }, { kind: "removed", edges }]);
    expect(diff).toEqual(mainThread.diff(edges, paired));
    expect(removed).toEqual(mainThread.removed(edges));
  });

  it("answers through the worker's own message handler with the main-thread result", async () => {
    const posted = [];
    globalThis.self = { postMessage: (message, transfer) => posted.push({ message, transfer }) };
    await import("./fielddeckChains.worker.js");
    const edges = [0, 0, 0, 10, 0, 0, 10, 0, 0, 10, 10, 0, 10, 10, 0, 0, 10, 0];
    const paired = [0, 0, 0, 10, 0, 0];
    globalThis.self.onmessage({ data: { id: 7, jobs: [{ kind: "overlay", edges: Float64Array.from(edges), paired: Float64Array.from(paired) }] } });
    expect(posted[0].message.id).toBe(7);
    expect(decodeChains(posted[0].message.results[0])).toEqual(mainThread.overlay(edges, paired));
    expect(posted[0].transfer.length).toBe(2);
    delete globalThis.self;
  });

  it("round-trips chains through the transfer encoding exactly", () => {
    const chains = [[[0.1, 0.2, 0.30000000000000004], [1e-9, -3.5, 7]], [], [[Math.PI, Math.E, -0]]];
    expect(decodeChains(encodeChains(chains))).toEqual(chains);
  });
});
