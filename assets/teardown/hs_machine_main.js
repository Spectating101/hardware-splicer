/* HS product-to-Teardown adapter. Source-generated data, no supplied kinematics.
 * The actual visualization runtime is upstream Teardown (MIT) + Three.js.
 * This is an interactive ANALYTIC GEOMETRY EXPLAINER, not physics simulation.
 */
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import glb64 from './machine.glb';
import {runSim} from 'teardown-kit/runtime.js';

const MODEL = __HS_TEARDOWN_MODEL_JSON__;
const state = {selected: null, explode: 0, isolate: false, section: false,
               view: 'iso', touched: false, yaw: 0.62, pitch: 0.38};
const clamp = (x,a,b) => Math.max(a, Math.min(b,x));
const parts = MODEL.parts;
const maximum = Math.max(...parts.map(p => Math.max(...p.extents_mm)));
const UNIT = 5.5 / maximum;
const labels = new Map();
const buttons = new Map();
const palette = [0x38bdf8,0xfbbf24,0x60a5fa,0xa78bfa,0x4ade80,0xfb7185];
const extentWidth = (p) => p.extents_mm[0] * UNIT;
const sumWidth = parts.reduce((s,p)=>s+extentWidth(p)+0.65,0);
let cursor = -sumWidth / 2;
const bases = [];
for (const p of parts) {
  const w = extentWidth(p);
  bases.push(new THREE.Vector3(cursor+w/2, p.extents_mm[2]*UNIT/2, 0));
  cursor += w+0.65;
}

function makeControl(tag,text,cls='') {
  const n = document.createElement(tag);
  n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function setupChrome(app) {
  const style = document.createElement('style');
  style.textContent =
    '#app{position:relative} .hs-overlay{position:absolute;inset:0;z-index:20;pointer-events:none;color:#e4edf6;font:14px system-ui,Arial,sans-serif}' +
    '.hs-overlay *{box-sizing:border-box}.hs-panel{position:absolute;top:18px;left:18px;width:min(340px,42vw);background:rgba(8,14,24,.88);border:1px solid #35506c;border-radius:14px;padding:17px;pointer-events:auto;backdrop-filter:blur(9px)}' +
    '.hs-panel h1{font-size:18px;margin:0 0 8px}.hs-panel p{font-size:12px;line-height:1.45;color:#bfd1e2;margin:7px 0}' +
    '.hs-actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:9px}.hs-actions button,.hs-parts button{background:#20364e;color:#eaf5ff;border:1px solid #486785;padding:8px 10px;border-radius:8px;cursor:pointer;font:inherit}' +
    '.hs-actions button[aria-pressed=true],.hs-parts button[aria-pressed=true]{background:#1879a5;border-color:#66c8ec}' +
    '.hs-parts{display:flex;flex-direction:column;gap:6px;margin-top:10px}.hs-parts button{text-align:left;font-size:12px}' +
    '.hs-bottom{position:absolute;left:18px;bottom:16px;right:18px;max-width:660px;background:rgba(8,14,24,.88);border:1px solid #35506c;border-radius:12px;padding:12px 16px;pointer-events:auto}' +
    '.hs-bottom label{display:flex;align-items:center;gap:12px}.hs-bottom input{flex:1;min-width:50px;accent-color:#39c5ef}' +
    '.hs-warning{color:#ffcf77!important;font-weight:650}.hs-panel small{font-size:11px;color:#9ab4cb;display:block;overflow-wrap:anywhere}' +
    '@media(max-width:650px){.hs-panel{top:8px;left:8px;width:min(275px,82vw);max-height:60vh;overflow:auto;padding:10px}.hs-panel h1{font-size:15px}.hs-bottom{left:8px;right:8px;bottom:8px}}';
  document.head.appendChild(style);
  const ui = makeControl('div','');
  ui.className='hs-overlay';
  const panel = makeControl('section','');
  panel.className='hs-panel';
  const title = makeControl('h1','HS / Machine Teardown');
  panel.appendChild(title);
  panel.appendChild(makeControl('p',MODEL.product_id+' · '+parts.length+' source-bound analytic parts'));
  panel.appendChild(makeControl('p','VISUAL EXPLANATION ONLY — no verified joints, motion, load paths, treatment or physical fit.','hs-warning'));
  const info = makeControl('p','Click a part or use the buttons to inspect its verified dimensions.');
  info.id='hs-info'; panel.appendChild(info);
  const list=makeControl('div','');list.className='hs-parts';
  for(const part of parts) {
    const b=makeControl('button',part.id.replaceAll('_',' ')+' · '+part.extents_mm.join(' × ')+' mm');
    b.id='hs-part-'+part.id;
    b.setAttribute('aria-pressed','false');
    b.addEventListener('click',()=>select(part.id));
    buttons.set(part.id,b);list.appendChild(b);
  }
  panel.appendChild(list);
  const actions=makeControl('div','');actions.className='hs-actions';
  const mk=(label,onclick,id)=>{const b=makeControl('button',label);b.id=id;b.addEventListener('click',onclick);actions.appendChild(b);return b;};
  const cut=mk('Section view',()=>{state.section=!state.section;state.touched=true;cut.setAttribute('aria-pressed',String(state.section));},'hs-section');
  const isolate=mk('Isolate part',()=>{state.isolate=!state.isolate;state.touched=true;isolate.setAttribute('aria-pressed',String(state.isolate));},'hs-isolate');
  mk('Top view',()=>{state.view='top';state.touched=true;},'hs-top');
  mk('3/4 view',()=>{state.view='iso';state.touched=true;},'hs-iso');
  mk('Reset',()=>{state.selected=null;state.explode=0;state.isolate=false;state.section=false;state.touched=true;cut.setAttribute('aria-pressed','false');isolate.setAttribute('aria-pressed','false');updateInfo();document.querySelector('#hs-explode').value='0';},'hs-reset');
  panel.appendChild(actions);
  const small=makeControl('small','Source SHA-256: '+MODEL.source_spec_sha256);
  panel.appendChild(small);
  ui.appendChild(panel);
  const bottom=makeControl('section','');bottom.className='hs-bottom';
  const label=makeControl('label','');
  const lbl=makeControl('span','Explode');
  const slider=document.createElement('input');
  slider.type='range';slider.id='hs-explode';slider.min='0';slider.max='100';slider.value='0';slider.setAttribute('aria-label','Explode assembly');
  slider.addEventListener('input',()=>{state.explode=Number(slider.value)/100;state.touched=true;});
  label.append(lbl,slider);bottom.appendChild(label);
  ui.appendChild(bottom);app.appendChild(ui);
  updateInfo();
}
function updateInfo(){
  for(const [id,b] of buttons)b.setAttribute('aria-pressed',String(state.selected===id));
  const p=parts.find(x=>x.id===state.selected);
  const el=document.getElementById('hs-info');
  if(el)el.textContent=p
    ? p.id+' | '+p.shape+' | '+p.extents_mm.join(' × ')+' mm | native STEP '+p.authored_step_sha256.slice(0,12)+'…'
    : 'Click a part or use the buttons to inspect its verified dimensions.';
}
function select(id){state.selected=state.selected===id?null:id;state.touched=true;updateInfo();}
runSim({
  duration:30, fps:30, theme:'dark', accent:'#38bdf8',
  hud:{enabled:false, title:'HARDWARE SPLICER',subtitle:'CONCEPTUAL TEARDOWN'},
  director:{enabled:false}
},async ({canvas})=>{
  const renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true,
    powerPreference:'default'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
  renderer.setClearColor(0x09121f);
  renderer.localClippingEnabled=true;
  const scene=new THREE.Scene();
  scene.background=new THREE.Color(0x09121f);
  const camera=new THREE.PerspectiveCamera(38,1,.01,1000);
  scene.add(new THREE.HemisphereLight(0xeaf8ff,0x122238,2.0));
  const light=new THREE.DirectionalLight(0xffffff,2.4);
  light.position.set(8,14,10);scene.add(light);
  const floor=new THREE.GridHelper(30,24,0x375b77,0x1d3349);
  floor.position.y=-0.12;scene.add(floor);
  const clips=new THREE.Plane(new THREE.Vector3(0,-1,0),0);
  const meshes=[];
  // Native CADCLAW assembly solids are tessellated and bundled as a real glTF.
  // No generic bounding-box cylinders/cubes substitute for the actual STEP mesh.
  const raw=Uint8Array.from(atob(glb64),c=>c.charCodeAt(0));
  const gltf=await new GLTFLoader().parseAsync(raw.buffer,'');
  const nodes=new Map();
  gltf.scene.traverse(node=>{if(node.isMesh){nodes.set(node.name,node);}});
  if(nodes.size!==parts.length || parts.some(p=>!nodes.has(p.id)))
    throw Error('Native STEP mesh identities differ from source-bound HS parts');
  parts.forEach((part,i)=>{
    const mesh=nodes.get(part.id);
    mesh.material=new THREE.MeshStandardMaterial({color:palette[i%palette.length],
      metalness:0.35,roughness:0.5,side:THREE.DoubleSide,transparent:true,clippingPlanes:[]});
    mesh.userData.partId=part.id;
    scene.add(mesh);meshes.push(mesh);
  });
  const savedPositions=meshes.map(m=>m.position.clone());
  const ray=new THREE.Raycaster();
  const pointer=new THREE.Vector2();
  let down=null;
  canvas.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY,yaw:state.yaw,pitch:state.pitch};});
  canvas.addEventListener('pointermove',e=>{
    if(!down||!(e.buttons&1))return;
    state.yaw=down.yaw+(e.clientX-down.x)*.006;
    state.pitch=clamp(down.pitch+(e.clientY-down.y)*.006,-1.4,1.4);
    state.view='free';state.touched=true;
  });
  canvas.addEventListener('pointerup',e=>{
    if(!down)return;
    const moved=Math.hypot(e.clientX-down.x,e.clientY-down.y);
    down=null;
    if(moved>5)return;
    const bounds=canvas.getBoundingClientRect();
    pointer.x=((e.clientX-bounds.left)/bounds.width)*2-1;
    pointer.y=-((e.clientY-bounds.top)/bounds.height)*2+1;
    ray.setFromCamera(pointer,camera);
    const hit=ray.intersectObjects(meshes)[0];
    if(hit)select(hit.object.userData.partId);
  });
  setupChrome(document.getElementById('app'));
  const radius=Math.max(13,sumWidth*1.23);
  const render=(t)=>{
    const explode=state.touched?state.explode:(0.34+0.34*Math.cos(t*Math.PI/15));
    for(let i=0;i<meshes.length;i++){
      const origin=savedPositions[i];
      const outward=(i-(meshes.length-1)/2);
      const active=state.selected===parts[i].id;
      const delta=explode*outward*1.0;
      meshes[i].position.copy(origin);
      meshes[i].position.x+=delta;
      meshes[i].position.y+=explode*(i%2)*0.6;
      meshes[i].material.opacity=(state.isolate&&state.selected&&!active)?0.11:1.0;
      meshes[i].material.depthWrite=meshes[i].material.opacity>0.5;
      meshes[i].material.emissive.setHex(active?0x174763:0x000000);
      meshes[i].material.clippingPlanes=state.section?[clips]:[];
    }
    clips.constant=0.4;
    const yaw=state.view==='top'?0:state.view==='iso'?0.62:state.yaw;
    const pitch=state.view==='top'?1.47:state.view==='iso'?0.38:state.pitch;
    camera.position.set(radius*Math.sin(yaw)*Math.cos(pitch),
      Math.max(2,radius*Math.sin(pitch)),radius*Math.cos(yaw)*Math.cos(pitch));
    camera.lookAt(0,Math.max(...bases.map(b=>b.y))*.40,0);
    renderer.render(scene,camera);
    return {};
  };
  const resize=()=>{
    const w=canvas.clientWidth||innerWidth,h=canvas.clientHeight||innerHeight;
    renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
  };
  window.HS_TEARDOWN={
    ready:true,
    product_id:MODEL.product_id,
    source_spec_sha256:MODEL.source_spec_sha256,
    geometry_basis:'actual tessellated CADCLAW native assembly STEP with verified solid mapping',
    physical_kinematics_verified:false,
    snapshot:()=>({selected:state.selected,explode:state.explode,
      isolate:state.isolate,section:state.section,parts:meshes.length,
      first_mesh_x:Number(meshes[0].position.x.toFixed(5))})
  };
  return {render,resize};
});
