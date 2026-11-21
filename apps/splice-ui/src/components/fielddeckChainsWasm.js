// The Rust port of the chain jobs (wasm/fielddeck-chains), compiled to WebAssembly. It returns
// the same chains as runChainJob, point for point (fielddeckChainsWasm.test.js checks that), about
// 15–30× faster. "removed" jobs, and any browser where the module will not load, keep the
// JavaScript path: the drawing is identical either way.
import { decodeChains, encodeChains, runChainJob } from "./fielddeckChains.js";

const KINDS = { diff: 1, overlay: 2 };
export const WASM_URL = new URL("./wasm/fielddeck_chains.wasm", import.meta.url);

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

function chainRunner(x) {
  const put = (values) => {
    const n = values?.length ?? 0;
    const ptr = x.fd_alloc(n);
    if (n) new Float64Array(x.memory.buffer, ptr, n).set(values);
    return [ptr, n];
  };
  /** One job → { points: Float64Array, sizes: Int32Array }, the encodeChains layout. */
  function runEncoded(job) {
    const kind = KINDS[job.kind];
    if (!kind) return encodeChains(runChainJob(job));
    const [edges, edgeCount] = put(job.edges);
    const [paired, pairedCount] = put(job.paired);
    try {
      const result = x.fd_run(kind, edges, edgeCount, paired, pairedCount);
      if (!result) throw new Error(`chain module refused ${job.kind}`);
      // Memory may have grown during the run: readResult takes fresh views after the call.
      return readResult(result);
    } finally {
      x.fd_free(edges, edgeCount);
      x.fd_free(paired, pairedCount);
    }
  }
  function readResult(result) {
    const header = new Uint32Array(x.memory.buffer, result, 4);
    const points = new Float64Array(x.memory.buffer, header[0], header[1]).slice();
    const sizes = new Int32Array(x.memory.buffer, header[2], header[3]).slice();
    x.fd_free_result(result);
    return { points, sizes };
  }
  /** weldEdgeChains(positions, tolerance), same chains. */
  function weld(positions, tolerance = 0.01) {
    const [ptr, count] = put(positions);
    try {
      return decodeChains(readResult(x.fd_weld(ptr, count, tolerance)));
    } finally {
      x.fd_free(ptr, count);
    }
  }
  const putBytes = (typed) => {
    const ptr = x.fd_alloc_bytes(typed.byteLength);
    if (typed.byteLength) new Uint8Array(x.memory.buffer, ptr, typed.byteLength).set(new Uint8Array(typed.buffer, typed.byteOffset, typed.byteLength));
    return [ptr, typed.byteLength];
  };
  /**
   * The positions `new THREE.EdgesGeometry(geometry, thresholdAngle)` would hold, as a
   * Float32Array, or null for a layout the port does not cover (interleaved, normalised or
   * non-float32 positions), which the caller then draws with three's own EdgesGeometry.
   */
  function edges(geometry, thresholdAngle = 1) {
    const position = geometry.getAttribute("position");
    const index = geometry.getIndex();
    if (!position || position.isInterleavedBufferAttribute || position.normalized || position.itemSize !== 3
      || !(position.array instanceof Float32Array) || position.array.length !== position.count * 3) return null;
    const ids = index ? (index.array instanceof Uint32Array ? index.array : Uint32Array.from(index.array)) : null;
    if (ids && ids.length !== index.count) return null;
    const [positions, positionBytes] = putBytes(position.array);
    const [indices, indexBytes] = ids ? putBytes(ids) : [0, 0];
    try {
      // The cosine stays in JavaScript, so it is V8's, exactly as three computes it.
      const result = x.fd_edges(positions, position.array.length, indices, ids ? ids.length : 0,
        Math.cos((Math.PI / 180) * thresholdAngle));
      if (!result) return null;
      const header = new Uint32Array(x.memory.buffer, result, 2);
      const points = new Float32Array(x.memory.buffer, header[0], header[1]).slice();
      x.fd_free_edges(result);
      return points;
    } finally {
      x.fd_free_bytes(positions, positionBytes);
      if (ids) x.fd_free_bytes(indices, indexBytes);
    }
  }
  return { runEncoded, weld, edges };
}
