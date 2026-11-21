// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { decodeChains, encodeChains, runChainJob } from "./fielddeckChains.js";
import { loadChainModule } from "./fielddeckChainsWasm.js";

const here = (path) => new URL(path, import.meta.url);
const wasmBytes = () => readFileSync(here("./wasm/fielddeck_chains.wasm"));

function capturedJobs() {
  const { jobs } = JSON.parse(readFileSync(here("./__fixtures__/fielddeck-chain-jobs.json"), "utf8"));
  const raw = readFileSync(here("./__fixtures__/fielddeck-chain-jobs.bin"));
  const values = new Float64Array(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength));
  const byKind = {};
  for (const { kind, key, offset, length } of jobs) {
    (byKind[kind] ??= { kind })[key] = Array.from(values.subarray(offset, offset + length));
  }
  return Object.values(byKind);
}

describe("Rust chain module", () => {
  it("returns the JavaScript chains exactly, on captured Fielddeck jobs", async () => {
    const wasm = await loadChainModule(wasmBytes());
    expect(wasm).not.toBeNull();
    const jobs = capturedJobs();
    expect(jobs.map((job) => job.kind)).toEqual(["diff", "overlay"]);
    for (const job of jobs) {
      const expected = runChainJob(job);
      expect(expected.length).toBeGreaterThan(0);
      expect(decodeChains(wasm.runEncoded(job))).toEqual(expected);
    }
  });

  it("matches on small synthetic cases, including no change and a moved edge", async () => {
    const wasm = await loadChainModule(wasmBytes());
    const square = [0, 0, 0, 10, 0, 0, 10, 0, 0, 10, 10, 0, 10, 10, 0, 0, 10, 0, 0, 10, 0, 0, 0, 0];
    const moved = [0, 0, 0, 10, 0, 0, 10, 0, 0, 10, 12, 0, 10, 12, 0, 0, 12, 0, 0, 12, 0, 0, 0, 0];
    const cases = [
      { kind: "diff", edges: square, paired: square },
      { kind: "diff", edges: moved, paired: square },
      { kind: "overlay", edges: square, paired: moved },
      { kind: "overlay", edges: [], paired: [] },
    ];
    for (const job of cases) expect(decodeChains(wasm.runEncoded(job))).toEqual(runChainJob(job));
  });

  it("leaves removed parts to the JavaScript path", async () => {
    const wasm = await loadChainModule(wasmBytes());
    const loop = [0, 0, 0, 20, 0, 0, 20, 0, 0, 20, 20, 0, 20, 20, 0, 0, 20, 0, 0, 20, 0, 0, 0, 0];
    const job = { kind: "removed", edges: loop };
    expect(decodeChains(wasm.runEncoded(job))).toEqual(runChainJob(job));
  });

  it("resolves to null rather than throwing when the bytes are not a module", async () => {
    expect(await loadChainModule(new Uint8Array([1, 2, 3]))).toBeNull();
  });
});

describe("Rust weld", () => {
  it("returns weldEdgeChains' chains exactly at the scene's tolerances", async () => {
    const { weldEdgeChains, diffAccentChains } = await import("./fielddeckLogic.js");
    const wasm = await loadChainModule(wasmBytes());
    const [diff] = capturedJobs();
    for (const tolerance of [0.01, 0.0001]) expect(wasm.weld(diff.edges, tolerance)).toEqual(weldEdgeChains(diff.edges, tolerance));
    const extents = [80, 50, 6];
    expect(diffAccentChains(diff.edges, extents, { weld: wasm.weld })).toEqual(diffAccentChains(diff.edges, extents));
    expect(wasm.weld([], 0.01)).toEqual([]);
  });
});

describe("Rust EdgesGeometry", () => {
  it("returns three's EdgesGeometry positions bit for bit, indexed and not, across angles", async () => {
    const THREE = await import("three");
    const wasm = await loadChainModule(wasmBytes());
    const shapes = [
      new THREE.BoxGeometry(10, 4, 2, 2, 1, 1),
      new THREE.CylinderGeometry(3, 3, 8, 24, 2),
      new THREE.TorusGeometry(5, 1.2, 12, 32),
      new THREE.IcosahedronGeometry(4, 1),
    ];
    shapes.forEach((shape) => shape.rotateX(0.3).rotateY(-1.1).translate(12.5, -3.25, 0.125));
    let compared = 0;
    for (const shape of shapes) {
      for (const geometry of [shape, shape.index ? shape.toNonIndexed() : shape]) {
        for (const angle of [1, 32, 40, 60]) {
          const expected = new THREE.EdgesGeometry(geometry, angle).getAttribute("position").array;
          const got = wasm.edges(geometry, angle);
          expect(got).toBeInstanceOf(Float32Array);
          expect(got.length).toBe(expected.length);
          expect(got.every((value, i) => Object.is(value, expected[i]))).toBe(true);
          compared += 1;
        }
      }
    }
    expect(compared).toBe(32);
  });

  it("declines layouts it does not cover, so three draws them", async () => {
    const THREE = await import("three");
    const wasm = await loadChainModule(wasmBytes());
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Int16Array(9), 3, true));
    expect(wasm.edges(geometry, 1)).toBeNull();
  });
});

// Reproducers from the Gemini 4 Neon review of the port (21 November 2026): each one diverged from
// the JavaScript before the fix. The module must now agree with the JavaScript on all of them.
describe("JavaScript number semantics at the edges", () => {
  const N = NaN;
  const jobs = [
    { name: "NaN x in the other revision", kind: "diff", edges: [0, 0, 0, 0.00005, 0, 0, 0.00005, 0, 0, 10, 0, 0], paired: [N, 0, 0, 0, 0, 0] },
    { name: "NaN z poisons coverage", kind: "diff", edges: [0, 0, 0, 10, 0, 0], paired: [0, 0, 0, 10, 0, N, 0, 0, 0, 10, 0, 0] },
    // (1e155 coordinates would reach simplify too, but the JavaScript then walks ~1e154 bins.)
    { name: "NaN point inside a simplified run", kind: "overlay", edges: [0, 0, 0, 5, N, 0, 5, N, 0, 10, 0, 0, 10, 0, 0, 20, 1, 0], paired: [] },
    { name: "coordinates past 2^63 cells", kind: "diff", edges: [1e16, 0, 0, 1e16 + 10, 0, 0], paired: [] },
    { name: "partial segment", kind: "diff", edges: [0, 0, 0, 10, 0], paired: [] },
    { name: "partial paired segment", kind: "diff", edges: [0, 0, 0, 10, 0, 0], paired: [0, 0, 0, 10] },
  ];
  for (const job of jobs) {
    it(`chain job: ${job.name}`, async () => {
      const wasm = await loadChainModule(wasmBytes());
      // Compared through the worker's transfer encoding, which is what the JavaScript path sends.
      expect(decodeChains(wasm.runEncoded(job))).toEqual(decodeChains(encodeChains(runChainJob(job))));
    });
  }

  it("weld at the change-accent tolerance with huge, NaN and partial input", async () => {
    const { weldEdgeChains } = await import("./fielddeckLogic.js");
    const wasm = await loadChainModule(wasmBytes());
    for (const positions of [[1e16, 0, 0, 1e16 + 10, 0, 0], [N, 0, 0, 1, 0, 0], [0, 0, 0, 10, 0]]) {
      expect(wasm.weld(positions, 0.0001)).toEqual(weldEdgeChains(positions, 0.0001));
    }
  });

  it("EdgesGeometry: empty index, huge and NaN coordinates, partial triangles, bad indices", async () => {
    const THREE = await import("three");
    const wasm = await loadChainModule(wasmBytes());
    const geometry = (positions, index) => {
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      if (index) g.setIndex(index);
      return g;
    };
    const same = (g) => {
      const expected = new THREE.EdgesGeometry(g, 1).getAttribute("position").array;
      const got = wasm.edges(g, 1) ?? expected; // null means three's own path draws it
      expect(got.length).toBe(expected.length);
      expect(Array.from(got).every((value, i) => Object.is(value, expected[i]))).toBe(true);
    };
    same(geometry([0, 0, 0, 1, 0, 0, 0, 1, 0], []));
    same(geometry([1e16, 0, 0, 2e16, 0, 0, 1e16, 1e16, 0]));
    same(geometry([N, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0]));
    same(geometry([0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 1, 0]));
    same(geometry([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 7]));
    expect(wasm.edges(geometry([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 7]), 1)).toBeNull();
  });
});
