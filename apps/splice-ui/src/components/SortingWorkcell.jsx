import {useEffect, useState} from "react";
import "./SortingWorkcell.css";

const file=(name)=>import.meta.env.BASE_URL+"sortcell/"+name;
export default function SortingWorkcell(){
 const [ready,setReady]=useState(null);
 const [error,setError]=useState(false);
 const [motion,setMotion]=useState(null);
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
    return fetch(file("robot_joint_trajectory.json"),{signal:controller.signal,cache:"no-store"})
      .then(async response=>{
        if(!response.ok)return;
        const motion=await response.json();
        if(motion.schema_version==="hardware_splicer.sortcell_openarm_pybullet_kinematics.v1" &&
           motion.engine==="pybullet" &&
           motion.motion?.numerical_kinematics_solved===true &&
           motion.motion?.robot_commands_authorized===false &&
           motion.task?.world_space_fixture_registration_verified===false)
           setMotion(motion);
      });
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
    {motion&&<section className="sw-motion-evidence" data-testid="sortcell-native-motion">
      <div>
        <p className="eyebrow">Next layer · Native robot kinematics</p>
        <h2>PyBullet / Official OpenArm URDF</h2>
        <p>Real numerical forward/inverse kinematics executed on the manufacturer's published joint
        definitions. This is a separate <b>source URDF v1.0</b> motion track; the viewer uses
        independently published v1.1 CAD and is <b>not mechanically registered to it yet</b>.</p>
      </div>
      <div className="sw-motion-stats">
        <span><b>{motion.native_robot.movable_joint_count}</b> source movable joints</span>
        <span><b>{motion.task.trajectory_samples}</b> computed joint samples</span>
        <span><b>{Math.round(Math.max(...motion.task.reference_waypoints.map(p=>p.error_m))*1000*100)/100} mm</b> max IK error</span>
        <a href={file("robot_joint_trajectory.json")} download>Download real source joint trajectory</a>
      </div>
      <p className="sw-motion-warning">The source joint path is not yet mapped to the physical sorting
      fixtures or validated against matching CAD collision meshes. The illustrated workcell arm
      remains a visual storyboard, not an executed PyBullet trajectory.</p>
    </section>}
    <footer><b>Source geometry: original OpenArm CAD</b> · Visualization: Teardown
      <span>Scripted workflow only · No verified robotic IK, computer vision, safety or fabrication</span></footer>
   </>:<div className="sw-unavailable" role="status">
     <h2>{error?"Original workcell bundle unavailable":"Loading original-source workcell…"}</h2>
     <p>The preview only appears when the entire source-backed Teardown workcell has been built.
        No substitute fake robot is displayed.</p>
   </div>}
 </section>;
}
