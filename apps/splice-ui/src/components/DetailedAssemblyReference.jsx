import { useEffect, useState } from "react";
import "./DetailedAssemblyReference.css";

const path = (name) => import.meta.env.BASE_URL + "reference-assemblies/" + name;

export default function DetailedAssemblyReference() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const ctrl = new AbortController();
    fetch(path("openarm/manifest.json"), {signal:ctrl.signal,cache:"no-store"})
      .then(async (r) => {
        if (!r.ok) throw Error("No qualified complex assembly export");
        const j=await r.json();
        if(j.schema_version!=="hardware_splicer.external_assembly_browser_proof.v1"||
          j.actual_glb_nodes_mapped<500||j.full_model_visible!==true||
          j.geometry_authored_by_hs!==false||
          j.physical_motion_verified!==false)
          throw Error("External asset has no real complex-assembly browser proof");
        setData(j);
      }).catch(e=>{if(e.name!=="AbortError")setError(true)});
    return ()=>ctrl.abort();
  }, []);
  return <section className="hs-real-assembly" data-testid="real-assembly-reference">
    <header>
      <div>
        <p className="eyebrow">Hardware Splicer · Complex assembly capability</p>
        <h1>Real geometry. Hundreds of components.</h1>
        <p>A demanding external CAD assembly used to evaluate HS's reusable product inspection interface.
          The original OpenArm hardware and CAD belong to their respective creators.</p>
      </div>
      {data&&<a href={path("openarm/machine.html")} target="_blank" rel="noopener noreferrer">
        Open immersive full screen
      </a>}
    </header>
    {data ? <>
      <iframe title="Complete OpenArm CAD interactive explorer"
        src={path("openarm/machine.html")} sandbox="allow-scripts"
        referrerPolicy="no-referrer"/>
      <footer>
        <span><b>{data.actual_glb_nodes_mapped} source-matched components</b> · original CAD-derived GLB</span>
        <span>External benchmark · Not designed or fabricated by HS · No validated motion</span>
      </footer>
    </> : <div className="hs-real-unavailable" role="status">
      <h2>{error?"Detailed reference viewer not packaged in this build":"Verifying CAD asset…"}</h2>
      <p>Complete source geometry is published only after the native browser has rendered and inspected
        the original high-component-count assembly. No substitute primitive geometry is displayed.</p>
    </div>}
  </section>
}
