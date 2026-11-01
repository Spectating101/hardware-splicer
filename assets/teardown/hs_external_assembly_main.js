/* Reusable Teardown stage for sourced, highly detailed external CAD assemblies.
   Geometry, part labels and disassembly offsets are retained from the source.
   This viewer is not a functional physics or mechanical-validation engine. */
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import glb64 from './machine.glb';
import {runSim} from 'teardown-kit/runtime.js';

const MODEL=__HS_EXTERNAL_MODEL_JSON__;
const state={explode:0,displayExplode:0,selected:null,isolate:false,xray:false,fasteners:true,
  yaw:.63,pitch:.20,zoom:1,frames:0};
const parts=MODEL.parts;
const byId=new Map(parts.map(p=>[p.id,p]));
const css=
  '#app{position:fixed!important;inset:0!important;width:100vw;height:100vh;overflow:hidden;background:#0d1725}'+
  '#gl{position:absolute;inset:0;width:100%;height:100%;display:block}'+
  '.hs-ui{position:absolute;inset:0;pointer-events:none;z-index:20;color:#e6f4ff;font:13px system-ui,sans-serif}'+
  '.hs-ui *{box-sizing:border-box}.hs-ui button,.hs-ui input{pointer-events:auto;font:inherit}'+
  '.hs-brand{position:absolute;left:27px;top:23px}.hs-brand small{color:#74d9ee;font-size:10px;letter-spacing:.23em;font-weight:800}'+
  '.hs-brand h1{font-size:clamp(24px,3vw,43px);margin:10px 0 8px;font-weight:800;line-height:1.1;letter-spacing:-.06em}'+
  '.hs-brand p{margin:0;color:#adc6d7;max-width:540px}'+
  '.hs-provenance{position:absolute;top:24px;right:25px;max-width:270px;text-align:right;padding:11px 13px;'+
  'border-radius:11px;border:1px solid #41617b;background:rgba(9,23,39,.88);color:#bdcfe0;font-size:11px;line-height:1.6}'+
  '.hs-provenance b{display:block;color:#e6be77;letter-spacing:.1em}'+
  '.hs-left{position:absolute;left:23px;top:148px;bottom:117px;width:285px;display:flex;flex-direction:column;'+
  'background:rgba(10,27,44,.94);border:1px solid #42627e;border-radius:15px;overflow:hidden;pointer-events:auto}'+
  '.hs-left h2{font-size:10px;letter-spacing:.2em;color:#88b1cb;padding:16px 15px 4px;margin:0}'+
  '.hs-left input{background:#19374c;border:1px solid #45657c;color:#e7f4ff;border-radius:8px;'+
  'margin:10px 12px;padding:10px;width:calc(100% - 24px)}'+
  '.hs-part-list{overflow:auto;flex:1;display:flex;flex-direction:column;gap:2px;padding:0 10px 8px}'+
  '.hs-part-list button{background:transparent;border:1px solid transparent;color:#b6cbdb;text-align:left;'+
  'padding:7px 10px;border-radius:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}'+
  '.hs-part-list button:hover,.hs-part-list button[aria-pressed=true]{background:#235672;border-color:#55b2d0;color:#fff}'+
  '.hs-selected{border-top:1px solid #395c73;padding:13px 15px;background:#142d43;min-height:86px}'+
  '.hs-selected b{display:block;font-size:12px}.hs-selected span{font-size:11px;line-height:1.5;color:#9cbdcf;display:block;margin-top:7px}'+
  '.hs-stats{position:absolute;right:25px;top:148px;max-width:220px;background:rgba(9,25,40,.88);'+
  'border:1px solid #39576e;border-radius:14px;padding:19px}.hs-stats strong{font-size:42px;letter-spacing:-.07em}'+
  '.hs-stats small{color:#a1bfd3;font-size:11px;display:block;margin-top:8px;line-height:1.6}'+
  '.hs-controls{position:absolute;left:23px;right:23px;bottom:17px;pointer-events:auto;'+
  'display:flex;gap:9px;align-items:center;flex-wrap:wrap;padding:15px;border:1px solid #446985;'+
  'border-radius:15px;background:rgba(9,26,44,.95);box-shadow:0 10px 40px #04080c99}'+
  '.hs-controls label{font-size:11px;color:#9dc2d3;letter-spacing:.1em;font-weight:750}'+
  '.hs-controls input{accent-color:#65d6ed;flex:1;min-width:150px}'+
  '.hs-controls button{background:#21465e;border:1px solid #52748a;color:#e5f3fa;padding:10px 13px;'+
  'border-radius:8px;cursor:pointer;font-size:12px}'+
  '.hs-controls button[aria-pressed=true],.hs-controls button:hover{background:#277c95}'+
  '.hs-controls button.primary{color:#082032;background:#78d5ed;border-color:transparent;font-weight:800}'+
  '@media(max-width:780px){.hs-stats,.hs-provenance{display:none}.hs-left{width:220px}}'+
  '@media(max-width:540px){.hs-brand{left:10px;top:10px}.hs-brand h1{font-size:21px}'+
  '.hs-brand p{font-size:10px;max-width:250px}.hs-left{left:7px;top:100px;bottom:145px;width:180px}'+
  '.hs-controls{left:7px;right:7px;bottom:7px;padding:8px;gap:5px}.hs-controls button{padding:6px;font-size:10px}}';
const make=(tag,cl,txt)=>{const n=document.createElement(tag);if(cl)n.className=cl;if(txt)n.textContent=txt;return n;};
const namedButtons=new Map();
let selectedTitle,selectedDetail,partList,search,slider;
let mappings=[],center=new THREE.Vector3(),radius=2,focus=new THREE.Vector3(),renderer,camera,scene,frames=0;
function updateInspector(){
  const p=byId.get(state.selected);
  selectedTitle.textContent=p?p.name:'Complete reference assembly';
  selectedDetail.textContent=p?(p.category+' · '+p.subassembly+' · '+p.extents_mm.join(' × ')+' mm'):
    'Click a real CAD component or search the source part directory.';
  for(const [id,b] of namedButtons)b.setAttribute('aria-pressed',String(id===state.selected));
}
function select(id){state.selected=(state.selected===id?null:id);updateInspector();}
function initUi(){
  document.head.appendChild(make('style','',''+css));
  const root=make('div','hs-ui');
  root.id='hs-external-ui';
  const header=make('header','hs-brand');
  header.append(make('small','','HARDWARE SPLICER · COMPLEX ASSEMBLY EXPLORER'),
    make('h1','',MODEL.title),
    make('p','','A complete sourced mechanical assembly — inspect every component, not basic placeholders.'));
  root.append(header);
  const source=make('div','hs-provenance');
  source.append(make('b','','EXTERNAL REFERENCE / NOT DESIGNED BY HS'),
    make('span','',MODEL.hardware_license+' hardware · conceptual exploded geometry'));
  root.append(source);
  const left=make('aside','hs-left');
  left.append(make('h2','','SOURCE CAD PART DIRECTORY'));
  search=make('input');search.id='hs-search';search.placeholder='Search 542 components…';
  search.setAttribute('aria-label','Search real CAD components');
  left.append(search);partList=make('div','hs-part-list');partList.id='hs-parts';
  left.append(partList);
  const inspected=make('div','hs-selected');
  selectedTitle=make('b','','Complete reference assembly');
  selectedDetail=make('span','','Select a component to inspect.');
  inspected.append(selectedTitle,selectedDetail);
  left.append(inspected);root.append(left);
  const stats=make('aside','hs-stats');
  stats.append(make('strong','',String(parts.length)),make('small','','SOURCE CAD PARTS'),
    make('small','','Imported from upstream. Geometry and exploder metadata retained; no HS physical operation claims.'));
  root.append(stats);
  const controls=make('div','hs-controls');
  controls.append(make('label','','EXPLODE'));
  slider=make('input');slider.type='range';slider.id='hs-explode';slider.min='0';slider.max='100';slider.value='0';
  slider.setAttribute('aria-label','Explode authentic mechanical assembly');
  slider.addEventListener('input',()=>state.explode=+slider.value/100);
  controls.append(slider);
  const button=(id,txt,fn,cl)=>{const b=make('button',cl,txt);b.id=id;b.onclick=fn;controls.append(b);return b;};
  button('hs-assembled','Assembled',()=>{state.explode=0;slider.value='0';});
  button('hs-explode-all','Fully exploded',()=>{state.explode=1;slider.value='100';},'primary');
  const xray=button('hs-xray','X-ray covers',()=>{state.xray=!state.xray;xray.setAttribute('aria-pressed',String(state.xray));});
  const isolate=button('hs-isolate','Isolate',()=>{state.isolate=!state.isolate;isolate.setAttribute('aria-pressed',String(state.isolate));});
  const fast=button('hs-fasteners','Fasteners',()=>{state.fasteners=!state.fasteners;fast.setAttribute('aria-pressed',String(!state.fasteners));});
  button('hs-reset','Reset',()=>{state.explode=0;state.displayExplode=0;state.selected=null;state.isolate=false;
    state.xray=false;state.fasteners=true;state.zoom=1;slider.value='0';updateInspector();
    xray.setAttribute('aria-pressed','false');isolate.setAttribute('aria-pressed','false');
    fast.setAttribute('aria-pressed','false');});
  root.append(controls);
  document.getElementById('app').append(root);
  function fill(){
    const q=search.value.trim().toLowerCase();
    namedButtons.clear();partList.replaceChildren();
    const candidates=parts.filter(p=>!q||[p.name,p.category,p.subassembly,p.joint,p.id]
      .some(s=>String(s||'').toLowerCase().includes(q)));
    for(const p of candidates.slice(0,200)){
      const b=make('button','',p.name);b.title=p.name+' · '+p.category;b.type='button';
      b.setAttribute('aria-pressed',String(p.id===state.selected));b.onclick=()=>select(p.id);
      partList.append(b);namedButtons.set(p.id,b);
    }
    if(!candidates.length)partList.append(make('div','','No matching source parts'));
  }
  search.addEventListener('input',fill);fill();
}
runSim({duration:60,fps:30,theme:'dark',accent:'#67d4ec',hud:{enabled:false},
  director:{enabled:false}},async ({canvas})=>{
  renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));
  renderer.toneMapping=THREE.NeutralToneMapping;renderer.toneMappingExposure=1.12;
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  scene=new THREE.Scene();
  scene.background=new THREE.Color('#1a2b3d');
  camera=new THREE.PerspectiveCamera(36,1,.001,5000);
  scene.add(new THREE.HemisphereLight('#eaf6ff','#596f84',2.0));
  const key=new THREE.DirectionalLight('#f8efe4',3.3);key.position.set(-8,15,16);scene.add(key);
  const fill=new THREE.DirectionalLight('#c6eaff',2.0);fill.position.set(10,3,-8);scene.add(fill);
  const rim=new THREE.DirectionalLight('#ebf7ff',1.5);rim.position.set(0,12,-16);scene.add(rim);
  const raw=Uint8Array.from(atob(glb64),c=>c.charCodeAt(0));
  const gltf=await new GLTFLoader().parseAsync(raw.buffer,'');
  scene.add(gltf.scene);
  gltf.scene.updateMatrixWorld(true,true);
  const objectByName=new Map();
  gltf.scene.traverse(n=>{if(n.name&&!objectByName.has(n.name))objectByName.set(n.name,n);});
  const seen=new Set();
  for(const part of parts){
    const obj=objectByName.get(part.id);
    if(!obj||seen.has(obj.uuid))continue;
    seen.add(obj.uuid);
    const descendants=[];
    obj.traverse(mesh=>{
      if(!mesh.isMesh)return;
      descendants.push(mesh);
      mesh.material=new THREE.MeshStandardMaterial({
        color:part.side==='LEFT'?'#a5d3ee':part.side==='RIGHT'?'#e2c7a9':'#aabec9',
        metalness:.58,roughness:.38,side:THREE.DoubleSide,
        transparent:true,opacity:1
      });
    });
    if(!descendants.length)continue;
    mappings.push({part,obj,origin:obj.position.clone(),
      offset:new THREE.Vector3(...part.explode_vector),descendants});
  }
  if(mappings.length<350)throw Error('Cannot map complete upstream GLB part identities: '+mappings.length+'/'+parts.length);
  const bounds=new THREE.Box3().setFromObject(gltf.scene);
  if(bounds.isEmpty())throw Error('Source glTF model has no geometry');
  bounds.getCenter(center);radius=bounds.getBoundingSphere(new THREE.Sphere()).radius;
  focus.copy(center);
  const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();
  let down=null;
  canvas.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY,state.yaw,state.pitch]});
  canvas.addEventListener('pointermove',e=>{if(!down||!(e.buttons&1))return;
    state.yaw=down[2]+(e.clientX-down[0])*.005;
    state.pitch=Math.max(-1.3,Math.min(1.3,down[3]-(e.clientY-down[1])*.005));
  });
  canvas.addEventListener('pointerup',e=>{if(!down)return;const d=Math.hypot(e.clientX-down[0],e.clientY-down[1]);down=null;
    if(d>5)return;
    const box=canvas.getBoundingClientRect();
    pointer.set((e.clientX-box.left)/box.width*2-1,-(e.clientY-box.top)/box.height*2+1);
    ray.setFromCamera(pointer,camera);
    const hits=ray.intersectObjects(gltf.scene.children,true);
    for(const hit of hits){const m=mappings.find(r=>r.descendants.includes(hit.object));
      if(m){select(m.part.id);break;}}
  });
  canvas.addEventListener('wheel',e=>{e.preventDefault();
    state.zoom=Math.max(.6,Math.min(3.5,state.zoom*Math.exp(e.deltaY*.0007)));
  },{passive:false});
  initUi();
  const render=()=>{
    state.frames++;
    state.displayExplode+=(state.explode-state.displayExplode)*.16;
    for(const row of mappings){
      row.obj.position.copy(row.origin).addScaledVector(row.offset,state.displayExplode);
      const active=state.selected===row.part.id;
      const isCover=/cover|casing|shell/i.test(row.part.category+' '+row.part.name);
      const isFast=/fastener|screw|bolt|washer|nut/i.test(row.part.category+' '+row.part.name);
      row.obj.visible=state.fasteners||!isFast;
      const opacity=state.isolate&&state.selected&&!active ? 0.07 : state.xray&&isCover&&!active ? 0.26 : 1;
      for(const mesh of row.descendants){
        mesh.material.opacity=opacity;mesh.material.depthWrite=opacity>.4;
        mesh.material.emissive.setHex(active?0x1f516a:0x000000);
      }
    }
    // Frame the complete authored explosion envelope, not only the assembled pose.
    // This prevents hundreds of genuine parts from being clipped behind UI.
    const maxOffset=Math.max(...mappings.map(r=>r.offset.length()),0);
    const framedRadius=radius+maxOffset*state.displayExplode;
    const d=Math.max(framedRadius*3.4,1)*state.zoom;
    camera.position.set(center.x+d*Math.sin(state.yaw)*Math.cos(state.pitch),
      center.y+d*Math.sin(state.pitch),center.z+d*Math.cos(state.yaw)*Math.cos(state.pitch));
    const active=mappings.find(r=>r.part.id===state.selected);
    const target=active&&state.isolate?active.obj.getWorldPosition(new THREE.Vector3()):center;
    focus.lerp(target,.09);camera.lookAt(focus);
    renderer.render(scene,camera);frames++;
    return {};
  };
  const resize=()=>{const w=canvas.clientWidth||innerWidth,h=canvas.clientHeight||innerHeight;
    renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();};
  window.HS_EXTERNAL_ASSEMBLY={ready:true,
    snapshot:()=>({parts:parts.length,mapped:mappings.length,frames,explode:state.explode,
      displayExplode:state.displayExplode,selected:state.selected,sourceRef:MODEL.source_ref,
      geometryAuthoredByHS:false,physicalMotionVerified:false})
  };
  return {render,resize};
});
