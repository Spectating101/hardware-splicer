import { useEffect, useState } from "react";
import "./ProductShowcase.css";

const SHOWCASE_PATH = "showcase/";
const sourcePath = (file) => import.meta.env.BASE_URL + SHOWCASE_PATH + file;

export default function ProductShowcase() {
  const [manifest, setManifest] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const abort = new AbortController();
    fetch(sourcePath("manifest.json"), { signal: abort.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("No verified product viewer packaged");
        const data = await response.json();
        if (data.schema_version !== "hardware_splicer.showcase_bundle.v1" ||
          data.native_browser_executed !== true ||
          data.physical_release_authorized !== false ||
          typeof data.source_spec_sha256 !== "string" ||
          !/^[a-f0-9]{64}$/.test(data.source_spec_sha256))
          throw new Error("Showcase manifest does not meet the evidence gate");
        setManifest(data);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => abort.abort();
  }, []);

  return (
    <section className="hs-showcase" data-testid="product-showcase">
      <div className="hs-showcase-header">
        <div>
          <p className="eyebrow">Hardware-Splicer / interactive engineering</p>
          <h1>See the machine. Explore the evidence.</h1>
          <p className="muted">
            Native CAD geometry, guided conceptual disassembly and source-linked component inspection.
            No physical qualification or functional simulation is implied.
          </p>
        </div>
        {manifest && (
          <a className="hs-showcase-link" href={sourcePath("machine.html")}
             target="_blank" rel="noopener noreferrer">
            Open full-screen ↗
          </a>
        )}
      </div>
      {manifest ? (
        <>
          <iframe
            title="Hardware-Splicer native CAD interactive explorer"
            src={sourcePath("machine.html")}
            className="hs-showcase-frame"
            sandbox="allow-scripts"
            referrerPolicy="no-referrer"
          />
          <div className="hs-showcase-evidence">
            <strong>Verified digital geometry · concept model only</strong>
            <span>{manifest.product_id} · {manifest.parts} CAD solids · SHA {manifest.source_spec_sha256.slice(0,16)}…</span>
          </div>
        </>
      ) : (
        <div className="hs-showcase-unavailable" role="status">
          <strong>{error ? "Verified viewer is not in this build" : "Checking published engineering evidence…"}</strong>
          <p>
            This view is enabled only when the native CAD, Teardown/Chromium and digital evidence gates
            have produced the offline HTML in the same build. The normal HS interface remains available.
          </p>
        </div>
      )}
    </section>
  );
}
