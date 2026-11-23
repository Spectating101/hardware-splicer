// The stage's heaviest geometry step, as a pure function a Web Worker can run: welding a part's
// feature edges into chains and culling the chains that coincide with the other revision. The
// same function runs on the main thread when no worker is available, so the drawing is identical
// either way. Inputs and outputs travel as transferable Float64Arrays, never as three objects.
import { cullCoincidentChains, cullIsolatedChains, ghostOutlineLoops, weldEdgeChains } from "./fielddeckLogic.js";

// Plain arrays in, as on the main thread: the logic indexes, slices and maps them like arrays.
const plain = (values) => (Array.isArray(values) ? values : Array.from(values ?? []));

/**
 * One job:
 *   { kind: "diff", edges, paired }     changed part, new revision: what differs from the old one
 *   { kind: "overlay", edges, paired }  changed part, old revision: old geometry not in the new one
 *   { kind: "removed", edges }          removed part: its outer loops
 * @returns {number[][][]} chains of [x, y, z] points
 */
export function runChainJob(job) {
  const edges = plain(job.edges);
  if (job.kind === "diff") return cullIsolatedChains(cullCoincidentChains(weldEdgeChains(edges), plain(job.paired)));
  if (job.kind === "overlay") {
    return cullIsolatedChains(cullCoincidentChains(weldEdgeChains(edges), plain(job.paired), { simplify: true }));
  }
  if (job.kind === "removed") return ghostOutlineLoops(edges);
  throw new Error(`Unknown chain job ${job.kind}`);
}

/** Chains → { points: Float64Array (x, y, z …), sizes: Int32Array (points per chain) }. */
export function encodeChains(chains) {
  const sizes = new Int32Array(chains.length);
  let count = 0;
  chains.forEach((points, i) => { sizes[i] = points.length; count += points.length; });
  const points = new Float64Array(count * 3);
  let offset = 0;
  for (const chain of chains) {
    for (const point of chain) { points[offset++] = point[0]; points[offset++] = point[1]; points[offset++] = point[2]; }
  }
  return { points, sizes };
}

export function decodeChains({ points, sizes }) {
  const chains = [];
  let offset = 0;
  for (const size of sizes) {
    const chain = [];
    for (let i = 0; i < size; i++, offset += 3) chain.push([points[offset], points[offset + 1], points[offset + 2]]);
    chains.push(chain);
  }
  return chains;
}

const toTransfer = (values) => (values instanceof Float64Array ? values : Float64Array.from(values ?? []));

// A small pool: the jobs are independent, so the parts are culled in parallel.
const POOL_SIZE = Math.max(1, Math.min(4, (globalThis.navigator?.hardwareConcurrency ?? 2) - 1));
let pool = null;
let workerFailed = false;
let nextId = 1;
const pending = new Map();

function failPool() {
  // A worker that cannot start leaves the jobs to the main thread; the drawing is the same.
  workerFailed = true;
  pool?.forEach((worker) => worker.terminate());
  pool = null;
  for (const [id, job] of pending) { pending.delete(id); job.fallback(); }
}

function chainWorkers() {
  if (pool || workerFailed || typeof Worker === "undefined") return pool;
  try {
    pool = Array.from({ length: POOL_SIZE }, () => {
      const worker = new Worker(new URL("./fielddeckChains.worker.js", import.meta.url), { type: "module" });
      worker.onmessage = ({ data }) => {
        const job = pending.get(data.id);
        if (!job) return;
        pending.delete(data.id);
        if (data.error) job.reject(new Error(data.error));
        else job.resolve(data.results.map(decodeChains));
      };
      worker.onerror = (event) => { event.preventDefault?.(); failPool(); };
      return worker;
    });
  } catch {
    failPool();
  }
  return pool;
}

function post(worker, jobs) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject, fallback: () => { try { resolve(jobs.map(runChainJob)); } catch (error) { reject(error); } } });
    const payload = jobs.map((job) => ({ kind: job.kind, edges: toTransfer(job.edges), paired: job.paired ? toTransfer(job.paired) : null }));
    // Each job's arrays are its own copies, so they can be transferred rather than cloned.
    const transfer = payload.flatMap(({ edges, paired }) => [edges.buffer, paired?.buffer]).filter(Boolean);
    worker.postMessage({ id, jobs: payload }, [...new Set(transfer)]);
  });
}

/** Runs the jobs in worker threads when available; otherwise on this thread, in order. Results keep job order. */
export async function runChainJobs(jobs) {
  const workers = chainWorkers();
  if (!workers || !jobs.length) return jobs.map(runChainJob);
  // Largest first onto the least-loaded worker, so one big part does not serialise the rest.
  const size = (job) => (job.edges?.length ?? 0) + (job.paired?.length ?? 0);
  const order = jobs.map((job, index) => index).sort((a, b) => size(jobs[b]) - size(jobs[a]));
  const lanes = workers.map(() => ({ load: 0, indices: [] }));
  for (const index of order) {
    const lane = lanes.reduce((best, candidate) => (candidate.load < best.load ? candidate : best));
    lane.indices.push(index);
    lane.load += size(jobs[index]);
  }
  const results = new Array(jobs.length);
  await Promise.all(lanes.map(async (lane, i) => {
    if (!lane.indices.length) return;
    const out = await post(workers[i], lane.indices.map((index) => jobs[index]));
    lane.indices.forEach((index, k) => { results[index] = out[k]; });
  }));
  return results;
}
