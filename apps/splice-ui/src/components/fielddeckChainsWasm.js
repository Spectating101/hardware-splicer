// The Rust port of the chain jobs (wasm/fielddeck-chains), compiled to WebAssembly. It returns
// the same chains as runChainJob, point for point (fielddeckChainsWasm.test.js checks that), about
// 15–30× faster. "removed" jobs, inputs whose length is not whole segments or triangles, and any
// browser where the module will not load keep the JavaScript path: the drawing is identical.
import { decodeChains, encodeChains, runChainJob } from "./fielddeckChains.js";
import { weldEdgeChains } from "./fielddeckLogic.js";

const KINDS = { diff: 1, overlay: 2 };
export const WASM_URL = new URL("./wasm/fielddeck_chains.wasm", import.meta.url);
const INTEGER_ARRAYS = [Uint8Array, Uint16Array, Uint32Array];

async function instantiate(bytes) {
  if (bytes) return WebAssembly.instantiate(bytes);
  const response = await fetch(WASM_URL);
  if (!response.ok) throw new Error(`chain module ${response.status}`);
  if (WebAssembly.instantiateStreaming && response.headers.get("content-type")?.startsWith("application/wasm")) {
    return WebAssembly.instantiateStreaming(response);
  }
  return WebAssembly.instantiate(await response.arrayBuffer());
}

/**
 * Loads the module; resolves to a runner, or null when WebAssembly is unavailable.
 * @param {ArrayBuffer|Uint8Array} [bytes] module bytes, for environments without fetch (tests)
 */
export async function loadChainModule(bytes) {
  if (typeof WebAssembly === "undefined") return null;
  try {
    const { instance } = await instantiate(bytes);
    return chainRunner(instance.exports);
  } catch {
    return null;
  }
}

const length = (values) => values?.length ?? 0;
const wholeSegments = (values) => length(values) % 6 === 0;

function chainRunner(x) {
  // wasm32 pointers arrive as signed i32; >>> 0 keeps addresses above 2 GiB valid.
  const ptr = (value) => value >>> 0;
  const memory = () => x.memory.buffer;
  // Every allocation is recorded as soon as it exists and freed in `finally`, whatever throws.
  function withAllocations(run) {
    const frees = [];
    try {
      return run({
        f64(values) {
          const n = length(values);
          const at = ptr(x.fd_alloc(n));
          frees.push(() => x.fd_free(at, n));
          if (n) new Float64Array(memory(), at, n).set(values);
          return [at, n];
        },
        bytes(typed) {
          const n = typed.byteLength;
          const at = ptr(x.fd_alloc_bytes(n));
          frees.push(() => x.fd_free_bytes(at, n));
          if (n) new Uint8Array(memory(), at, n).set(new Uint8Array(typed.buffer, typed.byteOffset, n));
          return at;
        },
        result(at, free) {
          frees.push(() => free(at));
          return at;
        },
      });
    } finally {
      for (const free of frees.reverse()) free();
    }
  }
  // Memory may have grown during a call: views are taken after it, and copied out.
  function readChains(result) {
    const header = new Uint32Array(memory(), result, 4);
    return {
      points: new Float64Array(memory(), header[0], header[1]).slice(),
      sizes: new Int32Array(memory(), header[2], header[3]).slice(),
    };
  }

  /** One job → { points: Float64Array, sizes: Int32Array }, the encodeChains layout. */
  function runEncoded(job) {
    const kind = KINDS[job.kind];
    if (!kind || !wholeSegments(job.edges) || !wholeSegments(job.paired)) return encodeChains(runChainJob(job));
    return withAllocations((alloc) => {
      const [edges, edgeCount] = alloc.f64(job.edges);
      const [paired, pairedCount] = alloc.f64(job.paired);
      const result = ptr(x.fd_run(kind, edges, edgeCount, paired, pairedCount));
      if (!result) throw new Error(`chain module refused ${job.kind}`);
      return readChains(alloc.result(result, x.fd_free_result));
    });
  }

  /** weldEdgeChains(positions, tolerance), same chains. */
  function weld(positions, tolerance = 0.01) {
    if (!wholeSegments(positions)) return weldEdgeChains(positions, tolerance);
    return withAllocations((alloc) => {
      const [at, count] = alloc.f64(positions);
      return decodeChains(readChains(alloc.result(ptr(x.fd_weld(at, count, tolerance)), x.fd_free_result)));
    });
  }

  /**
   * The positions `new THREE.EdgesGeometry(geometry, thresholdAngle)` would hold, as a
   * Float32Array, or null for a layout the port does not cover (interleaved, normalised or
   * non-float32 positions; an interleaved, non-integer or out-of-range index; a partial
   * triangle), which the caller then draws with three's own EdgesGeometry.
   */
  function edges(geometry, thresholdAngle = 1) {
    const position = geometry.getAttribute("position");
    const index = geometry.getIndex();
    if (!position || position.isInterleavedBufferAttribute || position.normalized || position.itemSize !== 3
      || !(position.array instanceof Float32Array) || position.array.length !== position.count * 3) return null;
    if (index && (index.isInterleavedBufferAttribute || index.itemSize !== 1 || index.array.length !== index.count
      || !INTEGER_ARRAYS.some((type) => index.array instanceof type))) return null;
    if ((index ? index.count : position.count) % 3 !== 0) return null;
    // An empty index is still an index: three draws no triangles from it.
    if (index && index.count === 0) return new Float32Array(0);
    const ids = index ? (index.array instanceof Uint32Array ? index.array : Uint32Array.from(index.array)) : null;
    return withAllocations((alloc) => {
      const positions = alloc.bytes(position.array);
      const indices = ids ? alloc.bytes(ids) : 0;
      // The cosine stays in JavaScript, so it is V8's, exactly as three computes it.
      const result = ptr(x.fd_edges(positions, position.array.length, indices, ids ? ids.length : 0, ids ? 1 : 0,
        Math.cos((Math.PI / 180) * thresholdAngle)));
      if (!result) return null; // an index outside the positions: three's own path decides
      alloc.result(result, x.fd_free_edges);
      const header = new Uint32Array(memory(), result, 2);
      return new Float32Array(memory(), header[0], header[1]).slice();
    });
  }

  return { runEncoded, weld, edges };
}
