import { useCallback, useEffect, useRef, useState } from "react";
import { fetchJob, fetchJobResult, submitComposeJob, submitSpliceJob } from "../api.js";

const POLL_MS = 2000;
/** Client-side honesty cap — backend also has HARDWARE_SPLICER_JOB_TIMEOUT_S (default 180). */
const CLIENT_JOB_TIMEOUT_S = 210;

const STAGE_LABELS = {
  queued: "Waiting in queue…",
  running: "Compiling splice plan and KiCad carrier…",
  succeeded: "Build complete",
  failed: "Build failed",
  cancelled: "Cancelled",
};

const COMPOSE_STAGE_LABELS = {
  queued: "Waiting in queue…",
  running: "AI compose → KiCad compile…",
  succeeded: "Design complete",
  failed: "Compose failed",
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
  const timedOutRef = useRef(false);

  const [jobKind, setJobKind] = useState("splice");

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
    timedOutRef.current = false;
    setElapsedSec(0);
    elapsedRef.current = setInterval(() => {
      if (startedAtRef.current) {
        const sec = Math.floor((Date.now() - startedAtRef.current) / 1000);
        setElapsedSec(sec);
        if (sec >= CLIENT_JOB_TIMEOUT_S && !timedOutRef.current) {
          timedOutRef.current = true;
          setError(
            `Build timed out after ${CLIENT_JOB_TIMEOUT_S}s. The job may still be running on the server — check Recent jobs or retry with offline mode.`,
          );
          setActive(false);
          clearTimer();
        }
      }
    }, 1000);
  };

  const pollJob = useCallback(async (jobId) => {
    if (timedOutRef.current) return true;
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
      setJobKind("splice");
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

  const startCompose = useCallback(
    async (payload, options = {}) => {
      clearTimer();
      setJobKind("compose");
      setActive(true);
      setError(null);
      setResult(null);
      setJob(null);
      startElapsed();
      try {
        const submitted = await submitComposeJob(payload, options);
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
    timedOutRef.current = false;
    setJob(null);
    setResult(null);
    setError(null);
    setActive(false);
    setElapsedSec(0);
    setJobKind("splice");
    startedAtRef.current = null;
  }, []);

  useEffect(() => () => clearTimer(), []);

  const labels = jobKind === "compose" ? COMPOSE_STAGE_LABELS : STAGE_LABELS;
  const stageLabel = job?.status ? labels[job.status] || job.status : "";

  return {
    job,
    result,
    error,
    active,
    elapsedSec,
    stageLabel,
    jobKind,
    startBuild,
    startCompose,
    reset,
    clearError: () => setError(null),
  };
}
