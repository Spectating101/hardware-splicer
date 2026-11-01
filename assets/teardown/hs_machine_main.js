/* HS product-to-Teardown adapter. Source-generated data, no supplied kinematics.
 * The actual visualization runtime is upstream Teardown (MIT) + Three.js.
 * This is an interactive ANALYTIC GEOMETRY EXPLAINER, not physics simulation.
 */
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {createProductStudio} from './hs_product_studio.js';
import glb64 from './machine.glb';
import {runSim} from 'teardown-kit/runtime.js';

const MODEL = __HS_TEARDOWN_MODEL_JSON__;

const parts = MODEL.parts;
const palette = [0xbccbd5,0x586579,0x62a4c4,0xd2d9dd,0x9fadb5,0x4b667d];
const title = MODEL.product_id.replace(/_nonpotable.*$/,'').replace(/_001$/,'')
  .split('_').filter(Boolean).map(x=>x.toUpperCase()).join(' / ');
const state = {
  selected:null, explode:0, displayedExplode:0, isolate:false, section:false,
  view:'iso', yaw:0.60, pitch:0.28, zoom:1, stage:0, tour:false,
  demoStart:0, touched:false, frame:0
};
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const duration = 30;
const partButtons=new Map();
const stageButtons=[];
let infoEl, stepText, stepCounter, stageProgress, explodeSlider, statePill;
let meshes=[], originals=[], modelCenter=new THREE.Vector3(),
  modelRadius=4, camera, renderer, scene, ground, focusTarget=new THREE.Vector3();
const steps = [
  {title:'Complete assembly', detail:'Reference arrangement from native CADCLAW STEP; no qualified mating interfaces.', emphasis:null, value:0},
  ...parts.map((p,i)=>({
    title:'Inspect '+p.id.replaceAll('_',' '),
    detail:'Source-bound analytic CAD surface · conceptual inspection sequence, not a service procedure.',
    emphasis:p.id, value:(i+1)/parts.length
  }))
];
const pretty=id=>id.replaceAll('_',' ').replace(/\b\w/g,x=>x.toUpperCase());
const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e;};
function addBtn(parent,label,fn,id,cls='') {
  const b=make('button',cls,label);
  if(id)b.id=id;
  b.type='button';
  b.addEventListener('click',fn);
  parent.appendChild(b);
  return b;
}
function setupChrome(app) {
  const style=make('style');
  style.textContent = `
  :root{--hs-ink:#eaf4ff;--hs-dim:#9aaec7;--hs-accent:#63d5ed}
  #app{position:fixed!important;inset:0!important;width:100vw;height:100vh;overflow:hidden;background:#081422}
  #gl{position:absolute;inset:0;width:100%;height:100%;display:block}
  .hs-ui{position:absolute;inset:0;z-index:20;pointer-events:none;color:var(--hs-ink);font:14px system-ui,-apple-system,sans-serif}
  .hs-ui *{box-sizing:border-box}
  .hs-ui button{font:inherit;color:inherit;cursor:pointer}
  .hs-top{position:absolute;left:30px;right:30px;top:22px;display:flex;justify-content:space-between;align-items:start;gap:20px}
  .hs-brand{font-size:11px;letter-spacing:.26em;font-weight:800;color:#70e7fc;text-transform:uppercase}
  .hs-headline{font-size:clamp(22px,2.6vw,38px);font-weight:800;letter-spacing:-.06em;line-height:1.07;margin-top:9px}
  .hs-kicker{font-size:12px;color:#9bb4cc;margin-top:9px;letter-spacing:.06em}
  .hs-tag{font-size:11px;letter-spacing:.14em;text-transform:uppercase;display:flex;align-items:center;gap:8px;
    color:#ffcd78;background:rgba(11,19,33,.83);padding:11px 14px;border:1px solid rgba(255,199,104,.31);border-radius:999px}
  .hs-tag:before{content:"";width:8px;height:8px;border-radius:50%;background:#ffba4c;box-shadow:0 0 10px #ffba4c}
  .hs-card{position:absolute;left:26px;top:164px;width:min(322px,31vw);max-height:calc(100vh - 310px);overflow-y:auto;
    pointer-events:auto;background:linear-gradient(145deg,rgba(13,29,47,.92),rgba(8,18,33,.85));border:1px solid #33516c;
    border-radius:18px;box-shadow:0 18px 60px rgba(0,0,0,.27);padding:17px 18px}
  .hs-card h2{font-size:10px;letter-spacing:.19em;text-transform:uppercase;color:#8cb0cd;margin:0 0 10px}
  .hs-card h3{font-size:20px;line-height:1.16;letter-spacing:-.02em;margin:0 0 8px}
  .hs-card p{font-size:12px;line-height:1.55;color:#abc2d6;margin:0 0 13px}
  .hs-part-list{display:flex;flex-direction:column;gap:7px;margin:10px 0 13px}
  .hs-part-list button{width:100%;padding:9px 10px;background:#172b40;border:1px solid #324e67;border-radius:10px;
    display:flex;justify-content:space-between;align-items:center;text-align:left;gap:7px;font-size:12px}
  .hs-part-list button:hover,.hs-part-list button[aria-pressed=true]{background:#1a556d;border-color:#69daf5}
  .hs-part-list small{font-size:10px;color:#94b6cd;white-space:nowrap}
  .hs-part-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
  .hs-inspect{background:#102438;border:1px solid #34556e;border-radius:10px;padding:11px 12px}
  .hs-inspect strong{display:block;font-size:12px;margin-bottom:4px}
  .hs-inspect span{display:block;font-size:11px;line-height:1.5;color:#9eb9cf;overflow-wrap:anywhere}
  .hs-facts{position:absolute;right:28px;top:164px;width:min(248px,23vw);padding:17px;
    background:rgba(10,24,41,.89);border:1px solid #33516c;border-radius:18px;pointer-events:none}
  .hs-facts h2{font-size:10px;letter-spacing:.18em;color:#80b0cb;text-transform:uppercase;margin:0 0 14px}
  .hs-stat{margin:0 0 13px;padding-bottom:11px;border-bottom:1px solid rgba(116,151,177,.19)}
  .hs-stat b{font-size:25px;letter-spacing:-.04em;display:block}
  .hs-stat small{font-size:11px;color:#96b4cb;line-height:1.35}
  .hs-facts p{font-size:11px;line-height:1.55;color:#a6bed4;margin:0}
  .hs-bottom{position:absolute;left:26px;right:26px;bottom:18px;
    background:linear-gradient(90deg,rgba(9,24,41,.96),rgba(12,28,45,.92));border:1px solid #355775;
    border-radius:18px;padding:15px 18px;pointer-events:auto;display:grid;
    grid-template-columns: minmax(155px,1fr) minmax(240px,1.55fr) auto;gap:18px;align-items:center;
    box-shadow:0 12px 45px rgba(0,0,0,.36)}
  .hs-step small{display:block;color:#8ab0cc;font-size:10px;letter-spacing:.15em;text-transform:uppercase}
  .hs-step strong{font-size:16px;display:block;margin:4px 0}
  .hs-step span{font-size:11px;color:#a7bed4}
  .hs-progress{display:flex;gap:5px;margin-bottom:9px}
  .hs-progress button{height:5px;flex:1;background:#34485b;border:0;border-radius:8px;padding:0}
  .hs-progress button[aria-pressed=true]{background:#68d5f0}
  .hs-range{display:flex;align-items:center;gap:12px}
  .hs-range label{color:#a1bad0;font-size:11px;white-space:nowrap}
  .hs-range input{width:100%;accent-color:#63d5ef}
  .hs-actions{display:flex;gap:7px;align-items:center;justify-content:end;flex-wrap:wrap}
  .hs-actions button{border:1px solid #466f8c;background:#20384e;border-radius:9px;padding:10px 12px;font-size:12px}
  .hs-actions button:hover,.hs-actions button[aria-pressed=true]{border-color:#60d1ed;background:#176077}
  .hs-actions .hs-primary{background:#2bc0db;color:#091522;border-color:transparent;font-weight:750}
  .hs-actions .hs-primary:hover{background:#60e2f3}
  .hs-tools{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
  .hs-tools button{border:1px solid #365971;border-radius:8px;background:#1b3247;padding:7px 9px;font-size:11px}
  .hs-tools button[aria-pressed=true]{background:#18607c;border-color:#6ddcf2}
  .hs-footnote{position:absolute;right:31px;bottom:116px;color:#89a5bd;font-size:10px;letter-spacing:.03em;
    max-width:330px;text-align:right;text-shadow:0 2px 8px #081422}
  @media(max-width:920px){
    .hs-facts{display:none}.hs-card{width:290px;max-height:calc(100vh - 320px)}
    .hs-bottom{grid-template-columns:1fr auto}.hs-progress-area{grid-column:1/-1;grid-row:2}.hs-footnote{display:none}
  }
  @media(max-width:640px){
    .hs-top{top:12px;left:14px;right:14px}.hs-headline{font-size:23px}.hs-kicker{font-size:10px}
    .hs-tag{font-size:9px;padding:7px 9px}.hs-card{left:12px;top:116px;width:224px;max-height:calc(100vh - 300px);padding:10px}
    .hs-card h3{font-size:16px}.hs-part-list button{padding:6px;font-size:10px}.hs-inspect{padding:8px}
    .hs-bottom{left:9px;right:9px;bottom:9px;padding:10px;gap:9px;border-radius:10px}
    .hs-step strong{font-size:13px}.hs-step span{display:none}.hs-actions button{padding:7px 8px;font-size:10px}
  }
  `;
  document.head.appendChild(style);
  const ui=make('div','hs-ui');
  ui.id='hs-ui';
  const top=make('header','hs-top');
  const intro=make('div');
  intro.append(make('div','hs-brand','HARDWARE SPLICER · ENGINEERING EXPLORER'),
               make('div','hs-headline',title),
               make('div','hs-kicker','REAL NATIVE CAD GEOMETRY · INTERACTIVE PRODUCT EXPLORATION'));
  top.appendChild(intro);
  statePill=make('div','hs-tag','CONCEPT · PHYSICAL GATES OPEN');
  top.appendChild(statePill);ui.appendChild(top);
  const card=make('aside','hs-card');
  card.append(make('h2','','01 / The anatomy'),make('h3','','Inspect every component'),
              make('p','','Select a native CAD solid to inspect its role, recorded dimensions and provenance.'));
  const list=make('div','hs-part-list');
  parts.forEach((p,i)=>{
    const button=addBtn(list,'',()=>{state.tour=false;state.selected=p.id;state.stage=i+1;state.explode=Math.max(state.explode,0.38);state.touched=true;updateInfo();},'hs-part-'+p.id);
    button.setAttribute('aria-pressed','false');
    const main=make('span');
    const dot=make('i','hs-part-dot');dot.style.background='#'+palette[i%palette.length].toString(16).padStart(6,'0');
    main.append(dot,document.createTextNode(pretty(p.id)));
    const dim=make('small','',p.extents_mm.map(x=>Math.round(x)).join(' × ')+' mm');
    button.append(main,dim);partButtons.set(p.id,button);
  });
  card.appendChild(list);
  const inspected=make('div','hs-inspect');
  inspected.append(make('strong','','Source-bound geometry'));
  infoEl=make('span','','Select a part to inspect its source-bound dimensions.');
  inspected.append(infoEl);card.appendChild(inspected);
  const tools=make('div','hs-tools');
  const cut=addBtn(tools,'Section',()=>{state.section=!state.section;state.touched=true;updateInfo();},'hs-section');
  const isolated=addBtn(tools,'Isolate',()=>{state.isolate=!state.isolate;state.touched=true;updateInfo();},'hs-isolate');
  addBtn(tools,'Top',()=>{state.view='top';state.touched=true;updateInfo();},'hs-top');
  addBtn(tools,'3/4',()=>{state.view='iso';state.touched=true;updateInfo();},'hs-iso');
  tools._cut=cut;tools._isolated=isolated;card.appendChild(tools);
  ui.appendChild(card);
  const facts=make('aside','hs-facts');
  facts.append(make('h2','','02 / Engineering evidence'));
  for(const [value,label] of [
    [String(parts.length).padStart(2,'0'),'Identified CAD-derived solids'],
    ['STEP → GLB','Native geometric provenance'],
    ['0','Physical validation certificates'],
  ]){
    const s=make('div','hs-stat');s.append(make('b','',value),make('small','',label));facts.appendChild(s);
  }
  facts.append(make('p','','Geometry and interactive inspection are verified digitally. Kinematics, functional performance, physical fit and safe manufacture remain unverified.'));
  ui.appendChild(facts);
  const bottom=make('footer','hs-bottom');
  const step=make('div','hs-step');
  stepCounter=make('small','','01 / 05 · GUIDED EXPLORATION');
  stepText=make('strong','','Complete assembly');
  const description=make('span','','CAD reference pose, not certified installation');
  description.id='hs-step-description';
  step.append(stepCounter,stepText,description);bottom.appendChild(step);
  const progress=make('div','hs-progress-area');
  stageProgress=make('div','hs-progress');
  steps.forEach((s,i)=>{const b=addBtn(stageProgress,'',()=>goStage(i),'hs-stage-'+i);b.setAttribute('aria-label','Show '+s.title);stageButtons.push(b);});
  progress.appendChild(stageProgress);
  const sliderBox=make('div','hs-range');
  const label=make('label','','EXPLODE');label.htmlFor='hs-explode';
  explodeSlider=document.createElement('input');
  explodeSlider.type='range';explodeSlider.min=0;explodeSlider.max=100;explodeSlider.step=1;explodeSlider.value=0;
  explodeSlider.id='hs-explode';explodeSlider.setAttribute('aria-label','Explode assembly');
  explodeSlider.addEventListener('input',()=>{
    state.explode=Number(explodeSlider.value)/100;state.tour=false;state.touched=true;updateInfo();
  });
  sliderBox.append(label,explodeSlider);progress.appendChild(sliderBox);bottom.appendChild(progress);
  const actions=make('div','hs-actions');
  addBtn(actions,'‹',()=>goStage(state.stage-1),'hs-previous');
  addBtn(actions,'Next ›',()=>goStage(state.stage+1),'hs-next','hs-primary');
  addBtn(actions,'Guided tour',()=>{
    state.tour=!state.tour;state.demoStart=performance.now();if(state.tour)goStage(0,true);updateInfo();
  },'hs-tour');
  addBtn(actions,'Reset',()=>reset(),'hs-reset');
  bottom.appendChild(actions);
  ui.appendChild(bottom);
  ui.append(make('div','hs-footnote','Drag to orbit · Scroll to zoom · 1–5 steps · Arrow keys navigate · Offline package'));
  app.appendChild(ui);
  updateInfo();
}
function goStage(i,fromTour=false) {
  state.stage=clamp(i,0,steps.length-1);
  const s=steps[state.stage];
  state.selected=s.emphasis;
  state.explode=s.value;
  if(!fromTour)state.tour=false;
  state.touched=true;
  updateInfo();
}
function reset(){
  state.selected=null;state.explode=0;state.isolate=false;state.section=false;state.view='iso';state.zoom=1;
  state.yaw=0.60;state.pitch=0.28;state.tour=false;state.stage=0;state.touched=false;
  updateInfo();
}
function updateInfo(){
  for(const [id,b] of partButtons)b.setAttribute('aria-pressed',String(id===state.selected));
  stageButtons.forEach((b,i)=>b.setAttribute('aria-pressed',String(state.stage===i)));
  const p=parts.find(x=>x.id===state.selected);
  if(infoEl)infoEl.textContent=p ?
    p.id+' · '+p.shape+' · '+p.extents_mm.join(' × ')+' mm · STEP '+p.authored_step_sha256.slice(0,16)+'…' :
    'CAD assembly from the pinned native source. Choose a component for its exact dimensions and source revision.';
  if(stepText)stepText.textContent=steps[state.stage].title;
  if(stepCounter)stepCounter.textContent=String(state.stage+1).padStart(2,'0')+
    ' / '+String(steps.length).padStart(2,'0')+' · GUIDED EXPLORATION';
  const description=document.getElementById('hs-step-description');
  if(description)description.textContent=steps[state.stage].detail;
  if(explodeSlider)explodeSlider.value=String(Math.round(state.explode*100));
  const btn=document.getElementById('hs-tour');
  if(btn)btn.setAttribute('aria-pressed',String(state.tour));
  for(const [id,on] of [['hs-section',state.section],['hs-isolate',state.isolate]]){
    const b=document.getElementById(id);if(b)b.setAttribute('aria-pressed',String(on));
  }
}
runSim({
  duration,fps:30,theme:'dark',accent:'#64d8ed',
  hud:{enabled:false,title:'HARDWARE SPLICER',subtitle:'CAD EXPLORER'},
  director:{enabled:false},
},async ({canvas})=>{
  renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true,
    powerPreference:'default'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
  renderer.setClearColor(0xc8d1d9);
  renderer.localClippingEnabled=true;
  scene=new THREE.Scene();
  scene.background=new THREE.Color(0xc8d1d9);
  camera=new THREE.PerspectiveCamera(37,1,.05,500);
  // The exact same upstream Teardown softbox/PMREM/GTAO studio vocabulary
  // is assembled after the native STEP GLB is loaded and measured.
  const raw=Uint8Array.from(atob(glb64),c=>c.charCodeAt(0));
  const gltf=await new GLTFLoader().parseAsync(raw.buffer,'');
  const nodes=new Map();
  gltf.scene.traverse(n=>{if(n.isMesh)nodes.set(n.name,n);});
  if(nodes.size!==parts.length||parts.some(p=>!nodes.has(p.id)))
    throw Error('Actual CAD mesh names did not match source part identities');
  const bounds=new THREE.Box3();
  parts.forEach((p,i)=>{
    const mesh=nodes.get(p.id);
    mesh.material=new THREE.MeshStandardMaterial({
      color:palette[i%palette.length],metalness:i===1?.58:.22,roughness:i===1?.48:.53,
      envMapIntensity:.85,side:THREE.DoubleSide,transparent:true,opacity:1,clippingPlanes:[]
    });
    mesh.castShadow=true;mesh.receiveShadow=true;
    scene.add(mesh);meshes.push(mesh);
    mesh.updateMatrixWorld(true);
    bounds.expandByObject(mesh);
  });
  bounds.getCenter(modelCenter);
  const sphere=new THREE.Sphere();
  bounds.getBoundingSphere(sphere);
  modelRadius=sphere.radius;
  originals=meshes.map(m=>m.position.clone());
  // Build the studio after reading native BRep-derived mesh bounds;
  // no material stage meshes are counted as machine engineering components.
  const studio=createProductStudio({renderer,scene,camera,bounds});
  const cutPlane=new THREE.Plane(new THREE.Vector3(0,-1,0),0);
  const ray=new THREE.Raycaster();
  const pointer=new THREE.Vector2();
  let down=null;
  canvas.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY,yaw:state.yaw,pitch:state.pitch};});
  canvas.addEventListener('pointermove',e=>{
    if(!down||!(e.buttons&1))return;
    const dist=Math.hypot(e.clientX-down.x,e.clientY-down.y);
    if(dist>4){
      state.yaw=down.yaw+(e.clientX-down.x)*.006;
      state.pitch=clamp(down.pitch-(e.clientY-down.y)*.006,-1.20,1.35);
      state.view='free';state.tour=false;state.touched=true;
    }
  });
  canvas.addEventListener('pointerup',e=>{
    if(!down)return;
    const moved=Math.hypot(e.clientX-down.x,e.clientY-down.y);down=null;
    if(moved>5)return;
    const b=canvas.getBoundingClientRect();
    pointer.x=((e.clientX-b.left)/b.width)*2-1;
    pointer.y=-((e.clientY-b.top)/b.height)*2+1;
    ray.setFromCamera(pointer,camera);
    const hit=ray.intersectObjects(meshes)[0];
    if(hit){
      const id=hit.object.userData.partId;
      state.selected=id;state.stage=parts.findIndex(x=>x.id===id)+1;
      state.explode=Math.max(state.explode,.3);state.tour=false;state.touched=true;updateInfo();
    }
  });
  canvas.addEventListener('wheel',e=>{e.preventDefault();
    state.zoom=clamp(state.zoom*Math.exp(e.deltaY*.0007),.65,2.15);
    state.tour=false;state.touched=true;
  },{passive:false});
  addEventListener('keydown',e=>{
    if(e.target instanceof HTMLInputElement)return;
    if(e.key==='ArrowRight'){goStage(state.stage+1);e.preventDefault();}
    if(e.key==='ArrowLeft'){goStage(state.stage-1);e.preventDefault();}
    if(e.key==='Escape'){reset();e.preventDefault();}
  });
  setupChrome(document.getElementById('app'));
  const referenceDistance=Math.max(11,modelRadius / Math.sin(camera.fov*Math.PI/360)*1.30);
  let orbitYaw=state.yaw,orbitPitch=state.pitch,currentZoom=1;
  const render=t=>{
    state.frame++;
    if(state.tour){
      const elapsed=(performance.now()-state.demoStart)/1000;
      const next=Math.floor(elapsed/3.5)%steps.length;
      if(next!==state.stage)goStage(next,true);
    }
    state.displayedExplode+=(state.explode-state.displayedExplode)*.095;
    for(let i=0;i<meshes.length;i++){
      const mesh=meshes[i],p=parts[i];
      const direction=(i-(meshes.length-1)/2);
      mesh.position.copy(originals[i]);
      const exploded=state.displayedExplode;
      mesh.position.x+=exploded*direction*1.36;
      mesh.position.y+=exploded*(i%2)*.72;
      const active=state.selected===p.id;
      const dimmed=state.isolate&&state.selected&&!active;
      mesh.material.opacity=dimmed?.07:1;
      mesh.material.depthWrite=!dimmed;
      mesh.material.emissive.setHex(active?0x0e526d:0x000000);
      mesh.material.clippingPlanes=state.section?[cutPlane]:[];
    }
    cutPlane.constant=-modelCenter.y;
    if(state.view==='top'){orbitYaw=0;orbitPitch+=(1.42-orbitPitch)*.08;}
    else if(state.view==='iso'){orbitYaw+=(.60-orbitYaw)*.08;orbitPitch+=(.28-orbitPitch)*.08;}
    else{orbitYaw+=(state.yaw-orbitYaw)*.12;orbitPitch+=(state.pitch-orbitPitch)*.12;}
    currentZoom+=(state.zoom-currentZoom)*.08;
    const distance=referenceDistance*currentZoom;
    camera.position.set(modelCenter.x+distance*Math.sin(orbitYaw)*Math.cos(orbitPitch),
      modelCenter.y+distance*Math.sin(orbitPitch),
      modelCenter.z+distance*Math.cos(orbitYaw)*Math.cos(orbitPitch));
    const selectedMesh=meshes.find(m=>m.userData.partId===state.selected);
    const desiredTarget=selectedMesh&&state.isolate?selectedMesh.position:modelCenter;
    focusTarget.lerp(desiredTarget,.08);
    camera.lookAt(focusTarget);
    studio.render();
    return {};
  };
  const resize=()=>{
    const w=canvas.clientWidth||innerWidth,h=canvas.clientHeight||innerHeight;
    renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
    studio.resize(w,h,renderer.getPixelRatio());
  };
  window.HS_TEARDOWN={
    ready:true,product_id:MODEL.product_id,source_spec_sha256:MODEL.source_spec_sha256,
    geometry_basis:'tessellated CADCLAW STEP',
    physical_kinematics_verified:false,
    snapshot:()=>({
      selected:state.selected,explode:state.explode,
      displayExplode:state.displayedExplode,isolate:state.isolate,
      section:state.section,parts:meshes.length,stage:state.stage,
      tour:state.tour,frames:state.frame,
      first_mesh_x:Number(meshes[0].position.x.toFixed(5)),
      bounds:[...bounds.min.toArray(),...bounds.max.toArray()],
      viewport:[canvas.clientWidth,canvas.clientHeight],
      studio:studio.summary()
    })
  };
  return {render,resize};
});
