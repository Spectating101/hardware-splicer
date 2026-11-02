import {useEffect, useState} from "react";
import "./SortingWorkcell.css";

const file=(name)=>import.meta.env.BASE_URL+"sortcell/"+name;
export default function SortingWorkcell(){
 const [ready,setReady]=useState(null);
 const [error,setError]=useState(false);
 useEffect(()=>{
  const controller=new AbortController();
  fetch(file("manifest.json"),{signal:controller.signal,cache:"no-store"})
   .then(async r=>{
    if(!r.ok)throw Error("workcell bundle not installed");
    const data=await r.json();
    if(data.schema_version!=="hardware_splicer.sortcell_source_receipt.v1"
      ||data.openarm_component_count!==542
      ||data.geometry_authored_by_hs!==false
      ||data.task_animation_physical_kinematics_verified!==false
      ||data.fabrication_authorized!==false)
      throw Error("no source-authenticated original OpenArm CAD");
    setReady(data);
   }).catch(e=>{if(e.name!=="AbortError")setError(true)});
  return ()=>controller.abort();
 },[]);
 return <section className="sw-shell" data-testid="sorting-workcell">
  <header className="sw-heading">
   <div><p className="eyebrow">Hardware Splicer · Product application</p>
    <h1>SORTCELL / S1</h1>
    <p>A Teardown-powered inspection and sorting workcell using 542 authentic OpenArm CAD components,
       not another primitive rendering exercise. Scrub the six-phase animation, inspect source components,
       and switch workcell areas.</p></div>
   {ready&&<a href={file("machine.html")} target="_blank" rel="noopener noreferrer">
    Open immersive workcell</a>}
  </header>
  {ready?<>
    <iframe title="SORTCELL S1 original OpenArm CAD Teardown workcell"
     src={file("machine.html")} sandbox="allow-scripts allow-same-origin"
     referrerPolicy="no-referrer" />
    <footer><b>Source geometry: original OpenArm CAD</b> · Visualization: Teardown
      <span>Scripted workflow only · No verified robotic IK, computer vision, safety or fabrication</span></footer>
   </>:<div className="sw-unavailable" role="status">
     <h2>{error?"Original workcell bundle unavailable":"Loading original-source workcell…"}</h2>
     <p>The preview only appears when the entire source-backed Teardown workcell has been built.
        No substitute fake robot is displayed.</p>
   </div>}
 </section>;
}
