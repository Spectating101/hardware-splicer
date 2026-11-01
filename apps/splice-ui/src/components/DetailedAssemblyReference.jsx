import { useEffect, useState } from "react";
import "./DetailedAssemblyReference.css";

const asset = (name) => import.meta.env.BASE_URL + "reference-assemblies/openarm/" + name;

export default function DetailedAssemblyReference() {
  const [manifest, setManifest] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(asset("manifest.json"), {signal:ctrl.signal, cache:"no-store"})
      .then(async r => {
        if(!r.ok) throw Error("Original upstream viewer assets unavailable");
        const j = await r.json();
        if(j.schema_version!=="hardware_splicer.upstream_viewer_adapter.v1"
          || j.viewer_origin!=="upstream_unmodified"
          || j.source_viewer_original!==true
          || j.follower_parts!==542 || j.leader_parts!==516
          || j.geometry_authored_by_hs!==false
          || j.physical_motion_verified!==false
          || !j.upstream_url?.startsWith("https://github.com/"))
          throw Error("Source provenance invalid");
        setManifest(j);
      })
      .catch(e => {if(e.name!=="AbortError") setError(true)});
    return ()=>ctrl.abort();
  }, []);

  return <section className="hs-real-assembly" data-testid="real-assembly-reference">
    <header>
      <div>
        <p className="eyebrow">Hardware Splicer · Existing engineering tools, directly integrated</p>
        <h1>OpenArm's original CAD explorer</h1>
        <p>This is the original third-party viewer, with its own assembly controls, both robot variants,
          source CAD, component catalog and explosion tools. HS embeds it unchanged rather than rebuilding it.</p>
      </div>
      {manifest && <a href={asset("index.html")} target="_blank" rel="noopener noreferrer">
        Open original viewer
      </a>}
    </header>
    {manifest ? <>
      <iframe title="Original OpenArm mechanical CAD viewer"
        src={asset("index.html")}
        // Upstream fetches local glTF assets: sandbox with an opaque origin would
        // block them. This trusted pinned source MUST be isolated on a distinct
        // origin before a production deployment with sensitive application state.
        sandbox="allow-scripts allow-same-origin"
        referrerPolicy="no-referrer" />
      <footer>
        <span><b>{manifest.follower_parts} follower components</b> · {manifest.leader_parts} leader components ·
          original upstream implementation</span>
        <span>
          <a href={manifest.upstream_url} target="_blank" rel="noopener noreferrer">Original source</a> ·
          {manifest.hardware_license} hardware · Not HS-authored or physically validated
        </span>
      </footer>
    </> : <div className="hs-real-unavailable" role="status">
      <h2>{error ? "Original CAD viewer not packaged in this build" : "Checking original source manifest…"}</h2>
      <p>This feature requires original pinned upstream viewer assets. HS does not replace
        a missing real assembly with a recreated primitive demonstration.</p>
    </div>}
  </section>
}
