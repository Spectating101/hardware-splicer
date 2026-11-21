// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { decodeChains, runChainJob } from "./fielddeckChains.js";
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
