/* HS Teardown 02: actual source-bound native STEP-mesh interactive showroom.
 * Uses the actual pinned upstream Teardown runtime. NO PHYSICAL SIMULATION.
 */
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {runSim} from 'teardown-kit/runtime.js';
import CAD_B64 from './machine.glb';

const DATA=__HS_SHOWCASE_MODEL_JSON__;
const parts=DATA.parts;
const byId=new Map(parts.map(p=>[p.id,p]));
const scale=7.7/Math.max(...DATA.assembly_bounds_mm);
const state={mode:'assembled',view:'hero',selected:null,isolate:false,
  section:false,auto:true,yaw:.76,pitch:.34,zoom:1,touched:false};
const nodes=new Map(),btns=new Map();
const palette=[0x5bd7fb,0xffbb75,0x8faeff,0x4ceac7,0xd3a6ff,0xff82a3];
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const pretty=s=>s.replace(/_/g,' ').replace(/\b\w/g,m=>m.toUpperCase());

function el(tag,cls,text,parent){
  const n=document.createElement(tag);
  if(cls)n.className=cls;
  if(text)n.textContent=text;
  if(parent)parent.appendChild(n);
  return n;
}
function updateUI(){
 document.querySelectorAll('[data-choice]').forEach(b=>{
  const val=b.dataset.choice;
  b.setAttribute('aria-pressed',String(val===state.mode||val===state.view||
    (val==='section'&&state.section)||(val==='isolate'&&state.isolate)||
    (val==='tour'&&state.auto)));
 });
 for(const [id,b] of btns)b.setAttribute('aria-pressed',String(state.selected===id));
 const info=document.querySelector('.hs-detail');
 if(!info)return;
 info.replaceChildren();
 const p=byId.get(state.selected);
 el('b','',p?pretty(p.id):'Choose a component',info);
 el('p','',p
   ? p.extents_mm.map(n=>Math.round(n)).join(' × ')+' mm · '+p.mesh_triangles+' source-derived triangles · '+(p.source_assembly_constraint?'CAD frame datum':'Unqualified design coordinate')
   : 'Select a part in the list or click its 3D surface. No physical joinery or operation is approved.',info);
}
function makeUI(){
 const app=document.getElementById('app'),shell=el('div','hs-shell','',app);
 const brand=el('div','hs-brand','',shell);
 el('div','hs-mark','H',brand);
 const word=el('div','','HARDWARE SPLICER',brand);
 el('small','',' / ENGINEERING EXPERIENCE',word);
 el('div','hs-status','● CONCEPT / PHYSICAL GATES OPEN',shell);
 const intro=el('section','hs-intro','',shell);
 el('div','hs-kicker','001  /  FUNCTION → MACHINE',intro);
 el('h1','',pretty(DATA.product_id.replace('_nonpotable_001','')),intro);
 el('p','','Explore native CAD-derived surfaces, genuine design placement and traceable engineering evidence. Inspect before anything is fabricated.',intro);
 el('div','hs-hairline','',intro);
 const metrics=el('div','hs-metrics','',intro);
 for(const [num,label] of [[String(parts.length),'NATIVE STEP SOLIDS'],
       [Math.round(DATA.assembly_bounds_mm[2])+'mm','DESIGN HEIGHT'],['0','PHYSICAL TESTS']]){
  const item=el('div','hs-metric','',metrics);
  el('strong','',num,item);el('span','',label,item);
 }
 const inspect=el('aside','hs-inspect','',shell);
 el('h2','','01 / INSPECT COMPONENTS',inspect);
 const list=el('div','hs-list','',inspect);
 parts.forEach((p,i)=>{
  const b=el('button','', '',list);
  b.id='hs-part-'+p.id;
  b.setAttribute('aria-pressed','false');
  const dot=el('i','hs-dot','',b);
  dot.style.background='#'+palette[i%palette.length].toString(16).padStart(6,'0');
  const txt=el('span','',pretty(p.id),b);
  el('small','',Math.round(p.extents_mm[0])+' × '+Math.round(p.extents_mm[2])+' mm',txt);
  b.addEventListener('click',()=>{
    state.selected=state.selected===p.id?null:p.id;
    state.auto=false;state.touched=true;updateUI();
  });
  btns.set(p.id,b);
 });
 el('div','hs-detail','',inspect);
 const toolbar=el('nav','hs-toolbar','',shell);
 const button=(label,choice,fn)=>{
  const b=el('button','',label,toolbar);b.dataset.choice=choice;
  b.id='hs-'+choice;
  b.addEventListener('click',()=>{
    fn();state.touched=true;updateUI();
  });
  return b;
 };
 button('ASSEMBLED','assembled',()=>{state.mode='assembled';state.auto=false;});
 button('EXPLODE','exploded',()=>{state.mode='exploded';state.auto=false;});
 el('i','hs-divider','',toolbar);
 button('SECTION','section',()=>{state.section=!state.section;state.auto=false;});
 button('ISOLATE','isolate',()=>{state.isolate=!state.isolate;state.auto=false;
   if(!state.selected)state.selected=parts[0].id;});
 el('i','hs-divider','',toolbar);
 button('FRONT','front',()=>{state.view='front';state.auto=false;});
 button('TOP','top',()=>{state.view='top';state.auto=false;});
 button('3D','hero',()=>{state.view='hero';state.auto=false;});
 button('▶ TOUR','tour',()=>{state.auto=!state.auto;});
 const progress=el('div','hs-progress','',shell);
 el('span','','DESIGN REVEAL  /  REAL STEP SURFACES',progress);
 const bar=el('div','hs-progress-bar','',progress);el('i','', '',bar);
 el('div','hs-foot','PROVENANCE-BOUND DIGITAL DESIGN · NOT PHYSICAL TESTING',shell);
 el('div','hs-help','DRAG TO ORBIT · SCROLL TO ZOOM · CLICK TO INSPECT',shell);
 updateUI();
}
async function openGeometry(){
 const buf=Uint8Array.from(atob(CAD_B64),v=>v.charCodeAt(0)).buffer;
 return new Promise((resolve,reject)=>new GLTFLoader().parse(buf,'',resolve,reject));
}
runSim({duration:24,fps:30,theme:'dark',accent:'#5edbff',
  hud:{enabled:false,title:'HS',subtitle:'CAD SHOWCASE'},director:{enabled:false}},
  async ({canvas})=>{
 const renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
 renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));
 renderer.setClearColor('#060c16');
 renderer.localClippingEnabled=true;
 renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.toneMapping=THREE.ACESFilmicToneMapping;
 renderer.toneMappingExposure=1.55;
 const scene=new THREE.Scene();scene.background=new THREE.Color('#060c16');
 scene.fog=new THREE.Fog('#060c16',16,39);
 const camera=new THREE.PerspectiveCamera(36,1,.05,80);
 scene.add(new THREE.AmbientLight(0xb9dbfa,1.45));
 const main=new THREE.DirectionalLight(0xe3f2ff,3.6);main.position.set(9,13,11);scene.add(main);
 const rim=new THREE.DirectionalLight(0x34bdfb,2.5);rim.position.set(-9,7,-7);scene.add(rim);
 const warm=new THREE.DirectionalLight(0xffc5a4,1.2);warm.position.set(-6,1,9);scene.add(warm);
 const grid=new THREE.GridHelper(24,48,0x2b5475,0x142c42);
 grid.position.y=-4.15;grid.material.transparent=true;grid.material.opacity=.26;scene.add(grid);
 const ring=new THREE.Mesh(new THREE.TorusGeometry(4.7,.014,8,120),
   new THREE.MeshBasicMaterial({color:0x3a94b7,transparent:true,opacity:.25}));
 ring.rotation.x=Math.PI/2;ring.position.y=-4.05;scene.add(ring);
 const gltf=await openGeometry();
 const root=gltf.scene;
 root.rotation.x=-Math.PI/2;root.scale.setScalar(scale);
 const [cx,cy,cz]=DATA.assembly_center_mm;
 root.position.set(1.1-cx*scale,-cz*scale,cy*scale);
 scene.add(root);
 for(let i=0;i<parts.length;i++){
  const part=parts[i],node=root.getObjectByName(part.id);
  if(!node)throw Error('Real GLB missing native part '+part.id);
  const meshes=[];
  node.traverse(o=>{
    if(!o.isMesh)return;
    const color=palette[i%palette.length];
    o.material=new THREE.MeshStandardMaterial({color,
      metalness:.40,roughness:.36,emissive:0x071626,emissiveIntensity:.25,
      transparent:true,opacity:1,side:THREE.DoubleSide});
    o.userData.partId=part.id;
    meshes.push(o);
  });
  if(!meshes.length)throw Error('Native CAD part has no renderable triangles '+part.id);
  nodes.set(part.id,{node,origin:node.position.clone(),meshes});
 }
 if(nodes.size!==parts.length)throw Error('Incomplete GLB native mesh inventory');
 const plane=new THREE.Plane(new THREE.Vector3(0,1,0),.23);
 const pointer=new THREE.Vector2(),ray=new THREE.Raycaster();
 let down=null,previousPositions={};
 canvas.addEventListener('pointerdown',e=>{
  down={x:e.clientX,y:e.clientY,yaw:state.yaw,pitch:state.pitch};
 });
 canvas.addEventListener('pointermove',e=>{
  if(!down||!(e.buttons&1))return;
  state.view='free';state.auto=false;state.touched=true;
  state.yaw=down.yaw+(e.clientX-down.x)*.005;
  state.pitch=clamp(down.pitch+(e.clientY-down.y)*.005,-1.35,1.35);
 });
 canvas.addEventListener('pointerup',e=>{
  if(!down)return;
  const moved=Math.hypot(e.clientX-down.x,e.clientY-down.y);down=null;
  if(moved>6)return;
  const b=canvas.getBoundingClientRect();
  pointer.set(((e.clientX-b.left)/b.width)*2-1,-((e.clientY-b.top)/b.height)*2+1);
  ray.setFromCamera(pointer,camera);
  const hit=ray.intersectObjects([...nodes.values()].flatMap(x=>x.meshes),false)[0];
  if(hit){
    const id=hit.object.userData.partId;
    state.selected=state.selected===id?null:id;
    state.auto=false;state.touched=true;updateUI();
  }
 });
 canvas.addEventListener('wheel',e=>{
  e.preventDefault();state.zoom=clamp(state.zoom+e.deltaY*.0009,.62,1.7);
  state.auto=false;state.touched=true;
 },{passive:false});
 makeUI();
 const center=new THREE.Vector3(...DATA.assembly_center_mm);
 function render(t){
  const phase=t%24;
  const explosion=state.auto?
   (phase<5?0:phase<9?(phase-5)/4:phase<16?1:phase<21?1-(phase-16)/5:0):
   (state.mode==='exploded'?1:0);
  previousPositions={};
  for(const p of parts){
   const entry=nodes.get(p.id);
   const pose=new THREE.Vector3(...p.translation_mm);
   pose.add(new THREE.Vector3(p.extents_mm[0]/2,p.extents_mm[1]/2,p.extents_mm[2]/2));
   const radial=pose.sub(center);
   if(radial.lengthSq()<.0001)radial.set(1,0,0);
   radial.normalize();
   entry.node.position.copy(entry.origin).addScaledVector(radial,explosion*135);
   previousPositions[p.id]=entry.node.position.toArray().map(x=>Number(x.toFixed(3)));
   const selected=state.selected===p.id;
   const fade=state.isolate&&state.selected&&!selected?.08:1;
   entry.meshes.forEach(o=>{
    o.material.opacity=fade;o.material.depthWrite=fade>.5;
    o.material.emissiveIntensity=selected?.9:.2;
    o.material.clippingPlanes=state.section?[plane]:[];
   });
  }
  let yaw=state.yaw,pitch=state.pitch;
  if(state.auto){yaw=.53+phase*.062;pitch=.31+Math.sin(phase*.19)*.09;}
  else if(state.view==='hero'){yaw=.71;pitch=.31;}
  else if(state.view==='front'){yaw=0;pitch=.06;}
  else if(state.view==='top'){yaw=.02;pitch=1.48;}
  const rad=(innerWidth<650?29:17+4.5*explosion)*state.zoom;
  camera.position.set(1.1+rad*Math.sin(yaw)*Math.cos(pitch),
    rad*Math.sin(pitch),rad*Math.cos(yaw)*Math.cos(pitch));
  camera.lookAt(1.1,innerWidth<650?-.65:.05,0);
  renderer.render(scene,camera);
  const i=document.querySelector('.hs-progress-bar i');
  if(i)i.style.width=String((phase/24)*100)+'%';
  return {};
 }
 function resize(){
  const w=canvas.clientWidth||innerWidth,h=canvas.clientHeight||innerHeight;
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
 }
 window.HS_SHOWCASE={
   ready:true,product_id:DATA.product_id,
   glb_sha256:DATA.glb_sha256,source_spec_sha256:DATA.source_spec_sha256,
   real_step_surface_geometry:true,physical_kinematics_verified:false,
   snapshot:()=>({mode:state.mode,view:state.view,selected:state.selected,
     isolate:state.isolate,section:state.section,auto:state.auto,
     mesh_parts:nodes.size,positions:previousPositions,
     total_triangles:parts.reduce((a,p)=>a+p.mesh_triangles,0),
     camera:camera.position.toArray().map(x=>Number(x.toFixed(3))),
     projected_part_centers:Object.fromEntries([...nodes.entries()].map(([id,entry])=>{
       entry.node.updateWorldMatrix(true,true);
       const center=new THREE.Box3().setFromObject(entry.node).getCenter(new THREE.Vector3());
       center.project(camera);
       return [id,[Number(center.x.toFixed(4)),Number(center.y.toFixed(4)),Number(center.z.toFixed(4))]];
     }))})
 };
 return {render,resize};
});
