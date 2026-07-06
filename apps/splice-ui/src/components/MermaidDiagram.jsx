import { useEffect, useRef, useState } from "react";

function useMermaidScript() {
  const [ready, setReady] = useState(() => typeof window !== "undefined" && Boolean(window.mermaid));
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (ready) return undefined;
    const existing = document.querySelector('script[data-mermaid="1"]');
    if (existing) {
      existing.addEventListener("load", () => setReady(true), { once: true });
      existing.addEventListener("error", () => setFailed(true), { once: true });
      return undefined;
    }
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
    script.dataset.mermaid = "1";
    script.onload = () => {
      if (window.mermaid) {
        window.mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "strict" });
      }
      setReady(true);
    };
    script.onerror = () => setFailed(true);
    document.head.appendChild(script);
    return () => {};
  }, [ready]);

  return { ready, failed };
}

export default function MermaidDiagram({ source, className = "" }) {
  const hostRef = useRef(null);
  const { ready, failed } = useMermaidScript();
  const [renderError, setRenderError] = useState("");

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !ready || !source || !window.mermaid) return undefined;
    let cancelled = false;
    const renderId = `mermaid-${Math.random().toString(36).slice(2)}`;
    setRenderError("");
    window.mermaid
      .render(renderId, source)
      .then(({ svg }) => {
        if (!cancelled) host.innerHTML = svg;
      })
      .catch((err) => {
        if (!cancelled) setRenderError(err.message || "Mermaid render failed");
      });
    return () => {
      cancelled = true;
    };
  }, [ready, source]);

  if (!source) return null;
  if (failed) return <p className="muted small">Topology diagram unavailable (Mermaid CDN blocked).</p>;
  if (!ready) return <p className="muted small">Loading topology diagram…</p>;
  if (renderError) return <p className="muted small">Could not render diagram: {renderError}</p>;

  return <div ref={hostRef} className={`mermaid-host ${className}`.trim()} />;
}
