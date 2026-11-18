import { useState } from "react";

export default function DigitalBriefForm({ onSubmit, disabled, revision = false }) {
  const [brief, setBrief] = useState("");
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    if (!brief.trim() || running || disabled) return;
    setRunning(true);
    setMessage("");
    setError("");
    try {
      const result = await onSubmit(brief.trim());
      if (result?.ok === false) throw new Error(result.job?.error?.message || "The study could not finish.");
      setMessage(result?.interpretation?.explanation || "");
      if (result?.study) setBrief("");
    } catch (cause) {
      setError(cause.message);
    } finally {
      setRunning(false);
    }
  }
  return <form onSubmit={submit} className="digital-brief">
    <label> {revision ? "Describe your next change" : "Describe what you want to build"}
      <textarea rows={3} maxLength={4000} value={brief} disabled={disabled || running}
        placeholder={revision ? "Which parts should change or stay the same?" : "Turn my Ender-3 into a pen plotter for an 11 mm marker."}
        onChange={(event) => setBrief(event.target.value)} />
    </label>
    <button type="submit" className="primary" disabled={disabled || running || !brief.trim()}>
      {running ? "Working on your brief…" : revision ? "Apply described change" : "Build from description"}
    </button>
    {message && <p role="status">{message}</p>}
    {error && <p role="alert" className="digital-error">{error}</p>}
  </form>;
}
