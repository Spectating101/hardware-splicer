import { encodeChains, runChainJob } from "./fielddeckChains.js";
import { loadChainModule } from "./fielddeckChainsWasm.js";

// The Rust module when it loads, the JavaScript otherwise; both return the same chains.
let module = loadChainModule();

const viaJavaScript = (job) => encodeChains(runChainJob(job));

self.onmessage = async ({ data }) => {
  try {
    let wasm = await module;
    const results = data.jobs.map((job) => {
      if (!wasm) return viaJavaScript(job);
      try {
        return wasm.runEncoded(job);
      } catch {
        // A trap leaves the module's state unknown: this worker uses the JavaScript from now on.
        wasm = null;
        module = Promise.resolve(null);
        return viaJavaScript(job);
      }
    });
    self.postMessage({ id: data.id, results }, results.flatMap(({ points, sizes }) => [points.buffer, sizes.buffer]));
  } catch (error) {
    self.postMessage({ id: data.id, error: error?.message ?? String(error) });
  }
};
