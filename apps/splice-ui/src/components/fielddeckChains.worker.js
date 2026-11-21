import { encodeChains, runChainJob } from "./fielddeckChains.js";

self.onmessage = ({ data }) => {
  try {
    const results = data.jobs.map((job) => encodeChains(runChainJob(job)));
    self.postMessage({ id: data.id, results }, results.flatMap(({ points, sizes }) => [points.buffer, sizes.buffer]));
  } catch (error) {
    self.postMessage({ id: data.id, error: error?.message ?? String(error) });
  }
};
