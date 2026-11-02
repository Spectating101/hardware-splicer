/* SORTCELL S1 | OpenArm original 542-part CAD + upstream Teardown.
 * The programmed pick-sort sequence is a visualization, NOT verified
 * inverse kinematics, machine vision, collision safety, or fabrication.
 */
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {createProductStudio} from './hs_product_studio.js';
import {runSim} from 'teardown-kit/runtime.js';
import sourceGlb from './robot.glb';
import source from './robot_metadata.json';

const SCHEMA='hardware_splicer.teardown_sortcell_s1.v1';
const PARTS=source.parts;
const color=[0x4addf2,0xffbd72,0xef8693];
const categories=['PRECISION','ELECTRONICS','REJECT'];
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const lerp=(a,b,t)=>a+(b-a)*t;
const smooth=t=>{t=clamp(t,0,1);return t*t*(3-2*t);};
const state={selected:'ALL',explode:0,paused:false,seek:null,yaw:.58,pitch:.32,zoom:1,frames:0};
const stages=[
 {at:0,name:'01 / FEED',text:'Source-neutral workpiece enters a belt conveyor.'},
 {at:3,name:'02 / INSPECT',text:'Simulated camera classification; not a real vision model.'},
 {at:6,name:'03 / GRASP',text:'Illustrative robot joint-zone pose; NOT verified inverse kinematics.'},
 {at:9,name:'04 / TRANSFER',text:'Virtual workpiece follows a planned destination trajectory.'},
 {at:12,name:'05 / SORT',text:'Planned object deposited into a labeled tray.'},
 {at:15,name:'06 / RESET',text:'Return workcell to its source pose.'},
];
const duration=18;
const mat=(c,m=.53,r=.40,opacity=1)=>new THREE.MeshStandardMaterial({color:c,metalness:m,roughness:r,transparent:opacity<1,opacity});
const steel=mat(0x9bb1bf),base=mat(0x2c495e),carbon=mat(0x1a2935,.2,.85),pale=mat(0xc4d1d8),accent=mat(0x54bccc,.45,.30),blue=mat(0x2b4152);
let scene,renderer,camera,studio,sourceRoot,sourceScene,packageCube,inspectionBeam,inspectionLight,beltBars=[],stageMeshes=[];
let group={},meshByNode=new Map(),meshPositions=new Map(),current=0,result={},ui;
const part=(geo,material,x,y,z,parent=scene)=>{
 const m=new THREE.Mesh(geo,material);m.position.set(x,y,z);
 m.castShadow=true;m.receiveShadow=true;parent.add(m);stageMeshes.push(m);return m;
};
const box=(w,h,d,m,x,y,z,parent=scene)=>part(new THREE.BoxGeometry(w,h,d),m,x,y,z,parent);
const cyl=(r,h,m,x,y,z,parent=scene)=>part(new THREE.CylinderGeometry(r,r,h,18),m,x,y,z,parent);
const rod=(a,b,r,m)=>{
 const dir=new THREE.Vector3().subVectors(b,a),obj=cyl(r,dir.length(),m,(a.x+b.x)/2,(a.y+b.y)/2,(a.z+b.z)/2);
 obj.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),dir.normalize());return obj;
};
function buildWorkcell(){
 box(3.42,.065,1.74,base,-.13,.36,.13);
 box(3.46,.016,1.77,steel,-.13,.405,.13);
 for(const x of [-1.77,1.51])for(const z of [-.57,.84]){
  box(.07,.76,.07,steel,x,.015,z);box(.14,.025,.14,blue,x,-.36,z);
 }
 box(2.47,.12,.53,blue,-.55,.49,.06);
 box(2.30,.012,.41,carbon,-.55,.557,.06);
 for(const z of [-.17,.28]){
  box(2.49,.048,.026,steel,-.55,.586,z);
  for(let i=0;i<6;i++)box(.022,.015,.07,pale,-1.63+i*.38,.620,z);
 }
 for(const x of [-1.73,.63]){const roller=cyl(.075,.47,steel,x,.49,.06);roller.rotation.x=Math.PI/2;}
 for(let i=0;i<22;i++){
  const bar=box(.016,.004,.385,base,-1.65+i*.102,.568,.06);bar.userData.belt=i*.102;beltBars.push(bar);
 }
 for(const z of [-.24,.36])rod(new THREE.Vector3(-.38,.67,z),new THREE.Vector3(-.38,1.34,z),.027,pale);
 rod(new THREE.Vector3(-.38,1.34,-.24),new THREE.Vector3(-.38,1.34,.36),.027,pale);
 box(.16,.13,.13,blue,-.38,1.34,.06);
 cyl(.05,.06,steel,-.38,1.245,.06);
 cyl(.035,.063,mat(0x51bbf0,.18,.2),-.38,1.20,.06);
 inspectionBeam=cyl(.19,.5,new THREE.MeshBasicMaterial({color:0x8ce8f7,transparent:true,opacity:.06,depthWrite:false,side:THREE.DoubleSide}),-.38,.90,.06);
 inspectionLight=new THREE.PointLight(0x84dff0,1,2.3);inspectionLight.position.set(-.38,1.2,.06);scene.add(inspectionLight);
 box(.43,.32,.38,base,1.16,.57,-.52);
 box(.41,.025,.35,steel,1.16,.74,-.52);
 cyl(.038,.033,mat(0xed6760,.1,.3),1.04,.79,-.55);
 cyl(.018,.028,mat(0x68e6c4,.1,.3),1.19,.79,-.55);
 // Three physical destination trays, side walls and lighted routing markers.
 for(let i=0;i<3;i++){
  const x=.45+i*.52,bin=mat(color[i],.4,.4);
  box(.46,.025,.50,blue,x,.465,.75);
  for(const dx of [-.23,.23])box(.018,.13,.50,bin,x+dx,.54,.75);
  for(const dz of [-.24,.24])box(.46,.13,.019,bin,x,.54,.75+dz);
  box(.16,.024,.022,bin,x,.65,.98);
  cyl(.017,.01,mat(color[i],.15,.3),x,.65,.74);
 }
 // 16 actual fixture markers and robot adapter base provide depth cues.
 for(let i=0;i<16;i++)
  cyl(.013,.014,pale,-1.68+(i%8)*.43,.423,i<8?-.61:.87);
 cyl(.29,.11,base,.88,.47,-.59);
 cyl(.22,.052,steel,.88,.545,-.59);
 box(.48,.028,.48,base,.88,.585,-.59);
 // Warning stripes around conveyor inspection location.
 for(const z of [-.16,.29])for(let i=0;i<4;i++)
  box(.038,.006,.014,mat(0xf2bb66,.3,.4),-.66+i*.15,.62,z);
}
function installUI(){
 const css=document.createElement('style');
 css.textContent=[
 '#app{position:fixed;inset:0;width:100%;height:100%;overflow:hidden;background:#263a4c}',
 '#gl{position:absolute;inset:0;width:100%;height:100%;display:block}',
 '.sw{position:absolute;inset:0;pointer-events:none;color:#edf7ff;font-family:Inter,system-ui,sans-serif}',
 '.sw *{box-sizing:border-box}.sw button,.sw input{pointer-events:auto}',
 '.sw button{font:inherit;cursor:pointer;color:#eaf4fa}',
 '.sw-top{position:absolute;left:26px;top:23px;max-width:515px;text-shadow:0 2px 10px #0d2338}',
 '.sw-eyebrow{font-size:11px;letter-spacing:.22em;color:#72e6f3;font-weight:800}',
 '.sw-title{font-size:38px;letter-spacing:-.055em;font-weight:800;margin:6px 0 5px}',
 '.sw-subtitle{font-size:12px;line-height:1.5;color:#bed4e6}',
 '.sw-panel{position:absolute;top:25px;right:25px;width:204px;border:1px solid #7295aa88;border-radius:14px;',
 'padding:16px;background:#0c2434ed;box-shadow:0 20px 50px #0616285e}',
 '.sw-stat{border-bottom:1px solid #5e849b66;padding:8px 0 11px}',
 '.sw-stat b{font-size:26px;display:block}.sw-stat span{font-size:10px;color:#a8bdcc}',
 '.sw-side{position:absolute;left:25px;top:170px;width:204px;padding:16px;pointer-events:auto;',
 'background:#0b2639e7;border:1px solid #7293a677;border-radius:14px}',
 '.sw-side h2,.sw-panel h2{font-size:10px;letter-spacing:.16em;color:#9ab8cb;margin:0 0 12px}',
 '.sw-side button{display:block;width:100%;text-align:left;border-radius:8px;padding:9px 12px;',
 'background:#1a4156;border:1px solid #456d83;margin-bottom:7px;font-size:12px}',
 '.sw-side button[data-active=true]{background:#1b7385;border-color:#86e8ee}',
 '.sw-side label{font-size:10px;color:#b4ccd9;display:block;margin-top:14px}',
 '.sw-side input{width:100%;accent-color:#65dce9}',
 '.sw-bottom{position:absolute;bottom:19px;left:25px;right:25px;display:flex;gap:18px;align-items:center;',
 'background:#102e42f0;border:1px solid #7b9aab88;border-radius:14px;padding:17px 19px;pointer-events:auto}',
 '.sw-stage{width:200px}.sw-stage b{font-size:17px;display:block}',
 '.sw-stage span{font-size:10px;color:#acc6d7;line-height:1.3;display:block;margin-top:5px}',
 '.sw-progress{flex:1}.sw-progress small{font-size:10px;letter-spacing:.2em;color:#8bcfe0}',
 '.sw-progress input{display:block;width:100%;accent-color:#65e0f2;margin-top:12px}',
 '.sw-bottom button{border:1px solid #648ca4;background:#254e62;border-radius:9px;padding:10px 13px;white-space:nowrap}',
 '.sw-bottom button.sw-primary{background:#64dbe9;color:#09202d;border-color:#a1f4ff;font-weight:800}',
 '.sw-footnote{position:absolute;right:27px;bottom:113px;color:#c5d6e2;font-size:10px;text-shadow:0 2px 5px #092235}',
 '@media(max-width:850px){.sw-title{font-size:25px}.sw-panel{display:none}.sw-side{width:162px;top:140px}',
 '.sw-stage{width:130px}.sw-bottom{padding:10px;gap:8px}.sw-footnote{display:none}}'
 ].join('');
 document.head.appendChild(css);
 const root=document.createElement('div');root.className='sw';root.id='sw-ui';document.getElementById('app').appendChild(root);
 root.innerHTML=[
 '<header class="sw-top"><div class="sw-eyebrow">HARDWARE SPLICER / TEARDOWN ENGINE</div>',
 '<div class="sw-title">SORTCELL / S1</div>',
 '<div class="sw-subtitle">Real 542-part OpenArm CAD · inspection conveyor · three destination stations.<br>Functional sorting storyboard, source-backed engineering reference.</div></header>',
 '<aside class="sw-panel"><h2>ASSEMBLY INVENTORY</h2>',
 '<div class="sw-stat"><b>542</b><span>OpenArm source mesh identities</span></div>',
 '<div class="sw-stat"><b>03</b><span>Classification destinations</span></div>',
 '<div class="sw-stat"><b id="sw-state">FEED</b><span>Active operator phase</span></div>',
 '<p style="font-size:10px;line-height:1.5;color:#a1becd">Kinematic motion and vision remain illustrative. This is not a physically tested robot.</p></aside>',
 '<aside class="sw-side"><h2>INSPECT THE WORKCELL</h2>',
 '<button id="sw-all" data-active="true">Whole workcell</button>',
 '<button id="sw-robot" data-active="false">OpenArm source CAD</button>',
 '<button id="sw-belt" data-active="false">Conveyor / sensor</button>',
 '<button id="sw-sort" data-active="false">Sorter / trays</button>',
 '<label for="sw-explode">Explode original CAD</label><input id="sw-explode" type="range" min="0" max="100" value="0">',
 '<button id="sw-reset" style="margin-top:14px">Reset viewpoint</button></aside>',
 '<footer class="sw-bottom"><div class="sw-stage"><b id="sw-task">01 / FEED</b>',
 '<span id="sw-description">Moving product toward the scanner.</span></div>',
 '<div class="sw-progress"><small id="sw-category">PRECISION / DIGITAL WALKTHROUGH</small>',
 '<input id="sw-timeline" type="range" min="0" max="179" value="0"></div>',
 '<button class="sw-primary" id="sw-pause">Pause</button><button id="sw-next">Next phase</button></footer>',
 '<div class="sw-footnote">UPSTREAM GEOMETRY / SCRIPTED TASK / NO PHYSICAL MOTION OR VISION VALIDATION</div>'
 ].join('');
 for(const [id,mode] of [['sw-all','ALL'],['sw-robot','ROBOT'],['sw-belt','BELT'],['sw-sort','SORT']])
  root.querySelector('#'+id).addEventListener('click',()=>{
   state.selected=mode;
   for(const key of ['sw-all','sw-robot','sw-belt','sw-sort'])
    root.querySelector('#'+key).dataset.active=String(key===id);
  });
 root.querySelector('#sw-explode').addEventListener('input',e=>state.explode=Number(e.target.value)/100);
 root.querySelector('#sw-timeline').addEventListener('input',e=>{
  state.seek=Number(e.target.value)/10;state.paused=true;
  root.querySelector('#sw-pause').textContent='Play';
 });
 root.querySelector('#sw-pause').addEventListener('click',e=>{
  state.paused=!state.paused;
  state.seek=state.paused?current:null;
  e.target.textContent=state.paused?'Play':'Pause';
 });
 root.querySelector('#sw-next').addEventListener('click',()=>{
  const idx=stages.reduce((a,row,i)=>current>=row.at?i:a,0);
  state.seek=stages[(idx+1)%stages.length].at;state.paused=true;
  root.querySelector('#sw-pause').textContent='Play';
 });
 root.querySelector('#sw-reset').addEventListener('click',()=>{
  state.selected='ALL';state.explode=0;state.yaw=.58;state.pitch=.32;state.zoom=1;
  root.querySelector('#sw-explode').value='0';
  root.querySelector('#sw-all').click();
 });
 return {
  phase:root.querySelector('#sw-state'),task:root.querySelector('#sw-task'),
  description:root.querySelector('#sw-description'),timeline:root.querySelector('#sw-timeline'),
  category:root.querySelector('#sw-category')
 };
}
async function importOriginalRobot(){
 let buffer;
 if(sourceGlb.startsWith('url:')){
  const response=await fetch('./'+sourceGlb.slice(4));
  if(!response.ok)throw Error('Cannot fetch original OpenArm GLB');
  buffer=await response.arrayBuffer();
 }else{
  buffer=Uint8Array.from(atob(sourceGlb),c=>c.charCodeAt(0)).buffer;
 }
 const model=await new GLTFLoader().parseAsync(buffer,'');
 model.scene.traverse(n=>{if(n.isMesh)meshByNode.set(n.name,n)});
 if(meshByNode.size!==542||PARTS.some(p=>!meshByNode.has(p.node)))
  throw Error('Expected all 542 original named OpenArm components, found '+meshByNode.size);
 sourceRoot=new THREE.Group();scene.add(sourceRoot);
 sourceRoot.position.set(.88,.603,-.59);sourceRoot.rotation.x=-Math.PI/2;
 sourceRoot.scale.setScalar(.93);
 sourceRoot.add(model.scene);sourceScene=model.scene;
 const pivot=(name,position,parent)=>{
  const g=new THREE.Group();g.name=name;g.position.set(...position);parent.add(g);group[name]=g;return g;
 };
 for(const side of ['LEFT','RIGHT']){
  const sg=side==='LEFT'?-1:1;
  const shoulder=pivot(side+'_SHOULDER',[0,sg*.15,.697],sourceScene);
  const elbow=pivot(side+'_ELBOW',[0,0,-.15],shoulder);
  const wrist=pivot(side+'_WRIST',[0,0,-.14],elbow);
  pivot(side+'_GRIPPER',[0,0,-.09],wrist);
 }
 sourceRoot.updateMatrixWorld(true);
 for(const p of PARTS){
  const mesh=meshByNode.get(p.node),target=group[p.side+'_'+p.joint_zone];
  if(target)target.attach(mesh);
  meshPositions.set(p.node,mesh.position.clone());
  const cat=p.category;
  mesh.material=cat==='Covers & Casings'?base:
    cat==='Motors & Actuators'?accent:
    cat==='Fasteners & Hardware'?pale:steel;
  mesh.castShadow=true;mesh.receiveShadow=true;
 }
}
function animate(t){
 current=t;
 const stage=stages.reduce((a,row,i)=>t>=row.at?i:a,0);
 const phase=stages[stage];const categoryIndex=1;
 const where=[.45,.97,1.49][categoryIndex];
 const pickupX=-.10;
 let x=lerp(-1.45,pickupX,smooth(t/6)),y=.62,z=.06;
 if(t>=6){const u=smooth((t-6)/3);x=lerp(pickupX,.3,u);y=lerp(.62,.9,u);z=lerp(.06,.29,u);}
 if(t>=9){const u=smooth((t-9)/3);x=lerp(.3,where,u);y=.90+.08*Math.sin(u*Math.PI)-.31*u;z=lerp(.29,.74,u);}
 if(t>=12){x=where;y=.56;z=.75;}
 packageCube.position.set(x,y,z);packageCube.rotation.set(0,t>=6&&t<12?.10*Math.sin(t):0,0);
 const rise=smooth((t-4.5)/3)-smooth((t-12.7)/3);
 for(const side of ['LEFT','RIGHT']){
  const sign=side==='LEFT'?-1:1;
  group[side+'_SHOULDER'].rotation.z=sign*rise*.17;
  group[side+'_ELBOW'].rotation.y=rise*.23;
  group[side+'_WRIST'].rotation.y=-rise*.19;
  group[side+'_GRIPPER'].rotation.x=sign*rise*.11;
 }
 for(const p of PARTS){
  const mesh=meshByNode.get(p.node),original=meshPositions.get(p.node);
  mesh.visible=state.selected!=='BELT';
  mesh.position.copy(original);
  if(state.explode>0){const v=p.explodeVec||[0,0,0];
   mesh.position.x+=v[0]*state.explode*.32;
   mesh.position.y+=v[1]*state.explode*.32;
   mesh.position.z+=v[2]*state.explode*.32;
  }
 }
 for(const m of stageMeshes)m.visible=state.selected!=='ROBOT';
 const sensor=t>=2.7&&t<6.1;
 inspectionBeam.material.opacity=sensor?.18:.04;inspectionLight.intensity=sensor?2.3:.7;
 for(const m of beltBars){
  const at=m.userData.belt||0;
  m.position.x=-1.64+((at+t*.32)%2.2);
 }
 ui.phase.textContent=phase.name.slice(5);
 ui.task.textContent=phase.name;ui.description.textContent=phase.text;
 ui.category.textContent=categories[categoryIndex]+' / SCRIPTED CLASSIFICATION';
 if(!state.paused)ui.timeline.value=String(Math.round(t*10));
 state.frames++;
 result={schema_version:SCHEMA,phase:phase.name,stage,classification:categories[categoryIndex],
  workpiece_xyz:[x,y,z],sourceMeshes:meshByNode.size,frames:state.frames,
  physicalMotionVerified:false,computerVisionExecuted:false};
}
runSim({
 duration,fps:30,theme:'dark',accent:'#65e0ee',
 hud:{enabled:false,title:'SORTCELL / S1',subtitle:'ORIGINAL CAD × TEARDOWN'},
 director:{enabled:false}
},async({canvas})=>{
 renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true,powerPreference:'default'});
 renderer.setPixelRatio(1);
 scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(38,1,.05,60);
 buildWorkcell();
 await importOriginalRobot();
 packageCube=box(.115,.115,.115,mat(color[1],.24,.4),-1.45,.62,.06);
 const bounds=new THREE.Box3().setFromCenterAndSize(new THREE.Vector3(-.12,.43,.10),new THREE.Vector3(4.3,2.2,2.75));
 studio=createProductStudio({renderer,scene,camera,bounds});
 ui=installUI();
 let drag;
 canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,yaw:state.yaw,pitch:state.pitch};});
 canvas.addEventListener('pointermove',e=>{
  if(!drag||!(e.buttons&1))return;
  state.yaw=drag.yaw+(e.clientX-drag.x)*.005;
  state.pitch=clamp(drag.pitch-(e.clientY-drag.y)*.004,0,1.2);
 });
 canvas.addEventListener('pointerup',()=>drag=null);
 canvas.addEventListener('pointerleave',()=>drag=null);
 canvas.addEventListener('wheel',e=>{state.zoom=clamp(state.zoom*(e.deltaY>0?1.08:.93),.55,2.4);e.preventDefault();},{passive:false});
 const render=t=>{
  const time=state.seek===null?t:state.seek;animate(time);
  const focus=state.selected==='ROBOT'?new THREE.Vector3(.85,.76,-.55):new THREE.Vector3(-.12,.54,.06);
  const radius=4.65*state.zoom;
  camera.position.set(focus.x+radius*Math.sin(state.yaw)*Math.cos(state.pitch),
    focus.y+radius*Math.sin(state.pitch),focus.z+radius*Math.cos(state.yaw)*Math.cos(state.pitch));
  camera.lookAt(focus);studio.render();return result;
 };
 const resize=()=>{
  const w=canvas.clientWidth||innerWidth,h=canvas.clientHeight||innerHeight;
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();studio.resize(w,h,1);
 };
 window.HS_SORTCELL={ready:true,sourcePartCount:542,
  upstreamRobot:'Utsav92/openarm-3d-cad-assembly@0c0852bd76ee7026f97875d6eac789d189a0012a',
  upstreamRuntime:'elvarofficial/teardown@a91262ac1109051e014662d42ecb0b7bc1f113b1',
  physicalMotionVerified:false,
  snapshot:()=>({...result,sourcePartCount:meshByNode.size,explode:state.explode,
    selected:state.selected,studio:studio.summary(),viewport:[canvas.width,canvas.height]})};
 return {render,resize};
});
