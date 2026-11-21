import { encodeChains, runChainJob } from "./fielddeckChains.js";
import { loadChainModule } from "./fielddeckChainsWasm.js";

// The Rust module when it loads, the JavaScript otherwise; both return the same chains.
const module = loadChainModule();

self.onmessage = async ({ data }) => {
  try {
    const wasm = await module;
    const results = data.jobs.map((job) => (wasm ? wasm.runEncoded(job) : encodeChains(runChainJob(job))));
    self.postMessage({ id: data.id, results }, results.flatMap(({ points, sizes }) => [points.buffer, sizes.buffer]));
  } catch (error) {
    self.postMessage({ id: data.id, error: error?.message ?? String(error) });
  }
};
