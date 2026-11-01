import { useEffect, useState } from "react";
import "./DetailedAssemblyReference.css";

const asset = (name) => import.meta.env.BASE_URL + "reference-assemblies/openarm/" + name;

export default function DetailedAssemblyReference() {
  const [manifest, setManifest] = useState(null);
  const [error, setError] = useState(false);
  const [engineering, setEngineering] = useState(null);

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
        // Separate official URDF variant: imported through HS existing adapters.
        return fetch(asset("engineering/OPENARM_SOURCE_LINEAGE.json"), {
          signal:ctrl.signal,cache:"no-store"
        }).then(async response => {
          if(!response.ok)return;
          const e=await response.json();
          if(e.schema_version==="hardware_splicer.upstream_robot_capability_handoff.v1" &&
            e.reconciliation?.same_assembly_topology_joined===false &&
            e.hs_native_projection?.new_cad_viewer_written===false &&
            e.hs_native_projection?.new_robot_parser_written===false)
            setEngineering(e);
        });
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
      {engineering && <section className="hs-upstream-engineering" data-testid="upstream-robot-engineering">
        <h2>Source-derived engineering project</h2>
        <p>The original OpenArm description was imported through HS's existing URDF and MachineProject
          pipelines; no robot parser or 3D viewer was rebuilt.</p>
        <div className="hs-engineering-numbers">
          <div><b>{engineering.upstream_robot_description.published_links}</b><span>URDF links</span></div>
          <div><b>{engineering.upstream_robot_description.published_joints}</b><span>URDF joints</span></div>
          <div><b>{engineering.hs_native_projection.mechanical_components}</b><span>HS project components</span></div>
          <div><b>{engineering.hs_native_projection.interfaces}</b><span>HS engineering interfaces</span></div>
        </div>
        <p className="hs-engineering-warning"><b>Source variant boundary:</b> {engineering.reconciliation.reason}</p>
        <div className="hs-engineering-links">
          <a href={asset("engineering/OPENARM_MACHINE_PROJECT.json")} download>MachineProject JSON</a>
          <a href={asset("engineering/OPENARM_URDF_TOPOLOGY.json")} download>Native robot topology</a>
          <a href={asset("engineering/OPENARM_CAD_PART_CATALOG.json")} download>Original CAD part index</a>
          <a href={engineering.upstream_robot_description.repository} target="_blank" rel="noopener noreferrer">Official robot description</a>
        </div>
      </section>}
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
