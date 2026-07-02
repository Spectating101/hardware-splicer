import { useCallback, useEffect, useRef, useState } from "react";
import { fetchJob, fetchJobResult, submitSpliceJob } from "../api.js";

const POLL_MS = 2000;

const STAGE_LABELS = {
  queued: "Waiting in queue…",
  running: "Compiling splice plan and KiCad carrier…",
  succeeded: "Build complete",
  failed: "Build failed",
  cancelled: "Cancelled",
};

export function useSpliceJob() {
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [active, setActive] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const timerRef = useRef(null);
  const elapsedRef = useRef(null);
  const startedAtRef = useRef(null);

  const clearTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (elapsedRef.current) {
      clearInterval(elapsedRef.current);
      elapsedRef.current = null;
    }
  };

  const startElapsed = () => {
    startedAtRef.current = Date.now();
    setElapsedSec(0);
    elapsedRef.current = setInterval(() => {
      if (startedAtRef.current) {
        setElapsedSec(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }
    }, 1000);
  };

  const pollJob = useCallback(async (jobId) => {
    const snapshot = await fetchJob(jobId);
    setJob(snapshot);
    if (snapshot.status === "succeeded") {
      const payload = await fetchJobResult(jobId);
      if (payload.ok && payload.result) {
        setResult(payload.result);
      } else {
        setError("Build finished but result was not available.");
      }
      setActive(false);
      clearTimer();
      return true;
    }
    if (snapshot.status === "failed" || snapshot.status === "cancelled") {
      const message =
        snapshot.error?.message || snapshot.error || `Job ${snapshot.status}`;
      setError(String(message));
      setActive(false);
      clearTimer();
      return true;
    }
    return false;
  }, []);

  const startBuild = useCallback(
    async (intake, options = {}) => {
      clearTimer();
      setActive(true);
      setError(null);
      setResult(null);
      setJob(null);
      startElapsed();
      try {
        const submitted = await submitSpliceJob(intake, options);
        const jobId = submitted.job_id;
        setJob(submitted);
        const done = await pollJob(jobId);
        if (!done) {
          timerRef.current = setInterval(() => {
            pollJob(jobId).catch((err) => {
              setError(err.message);
              setActive(false);
              clearTimer();
            });
          }, POLL_MS);
        }
        return jobId;
      } catch (err) {
        setError(err.message);
        setActive(false);
        clearTimer();
        throw err;
      }
    },
    [pollJob],
  );

  const reset = useCallback(() => {
    clearTimer();
    setJob(null);
    setResult(null);
    setError(null);
    setActive(false);
    setElapsedSec(0);
    startedAtRef.current = null;
  }, []);

  useEffect(() => () => clearTimer(), []);

  const stageLabel = job?.status ? STAGE_LABELS[job.status] || job.status : "";

  return {
    job,
    result,
    error,
    active,
    elapsedSec,
    stageLabel,
    startBuild,
    reset,
    clearError: () => setError(null),
  };
}
