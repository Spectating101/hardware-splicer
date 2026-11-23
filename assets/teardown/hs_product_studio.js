/* HS native-CAD digital product studio.
 * Presentation ONLY: area lights, floor, image-based environment and AO.
 * Geometry provenance lives in the upstream STEP -> GLB adapter.
 * Studio meshes are not engineering parts, and never change the BOM.
 */
import * as THREE from 'three';
import {EffectComposer} from 'three/addons/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/addons/postprocessing/RenderPass.js';
import {GTAOPass} from 'three/addons/postprocessing/GTAOPass.js';
import {OutputPass} from 'three/addons/postprocessing/OutputPass.js';
import {Pass} from 'three/addons/postprocessing/Pass.js';

function softBox(env,w,h,x,y,z,intensity,color='#ffffff'){
  const light=new THREE.Mesh(new THREE.PlaneGeometry(w,h),
    new THREE.MeshBasicMaterial({color:new THREE.Color(color).multiplyScalar(intensity),side:THREE.DoubleSide}));
  light.position.set(x,y,z);light.lookAt(0,0,0);env.add(light);
}
function backgroundGradient(){
  const canvas=document.createElement('canvas');
  canvas.width=4;canvas.height=512;
  const ctx=canvas.getContext('2d');
  const g=ctx.createLinearGradient(0,0,0,512);
  g.addColorStop(0,'#26374a');
  g.addColorStop(.56,'#2e4052');
  g.addColorStop(1,'#405366');
  ctx.fillStyle=g;ctx.fillRect(0,0,4,512);
  const t=new THREE.CanvasTexture(canvas);
  t.colorSpace=THREE.SRGBColorSpace;
  return t;
}
export function createProductStudio({renderer,scene,camera,bounds}) {
  renderer.toneMapping=THREE.NeutralToneMapping;
  renderer.toneMappingExposure=1.03;
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.shadowMap.enabled=true;
  renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  renderer.localClippingEnabled=true;

  const center=bounds.getCenter(new THREE.Vector3());
  const span=bounds.getSize(new THREE.Vector3());
  const radius=Math.max(...span.toArray())*.5;
  const floorY=bounds.min.y-Math.max(.18,radius*.09);
  scene.background=backgroundGradient();
  const env=new THREE.Scene();
  env.background=new THREE.Color('#c2cbd4');
  const size=Math.max(10,radius*8);
  softBox(env,size*.9,size*.85,-size*.43,size*.48,size*.32,2.65,'#f4faff');
  softBox(env,size*.45,size*.8,size*.48,size*.25,-size*.22,2.3,'#e5f3ff');
  softBox(env,size*.85,size*.24,0,size*.3,size*.52,1.6,'#fff0d7');
  softBox(env,size*.35,size*.55,-size*.2,size*.28,-size*.5,.9,'#d1f6ff');
  const pmrem=new THREE.PMREMGenerator(renderer);
  scene.environment=pmrem.fromScene(env,.03).texture;
  scene.environmentIntensity=.75;
  pmrem.dispose();

  const key=new THREE.DirectionalLight('#fff9f1',3.2);
  key.position.copy(center).add(new THREE.Vector3(-radius*2.4,radius*3.6,radius*2.2));
  key.target.position.copy(center);
  key.castShadow=true;
  const ext=Math.max(5,radius*2.1);
  Object.assign(key.shadow.camera,{left:-ext,right:ext,top:ext,bottom:-ext,near:.1,far:radius*14+20});
  key.shadow.mapSize.set(2048,2048);
  key.shadow.bias=-.00025;
  key.shadow.normalBias=.012;
  key.shadow.radius=4;
  scene.add(key,key.target);
  scene.add(new THREE.HemisphereLight('#f6fbff','#788ca0',1.25));

  const fill=new THREE.DirectionalLight('#b6d9f9',.85);
  fill.position.copy(center).add(new THREE.Vector3(radius*3,radius*.7,-radius*1.5));
  scene.add(fill);
  const rim=new THREE.DirectionalLight('#f4ebe0',1.1);
  rim.position.copy(center).add(new THREE.Vector3(radius*.2,radius*1.8,-radius*3));
  scene.add(rim);

  const shadow=new THREE.Mesh(new THREE.PlaneGeometry(50,50),
    new THREE.ShadowMaterial({color:'#101d29',opacity:.43,polygonOffset:true,
      polygonOffsetFactor:-4,polygonOffsetUnits:-8}));
  shadow.rotation.x=-Math.PI/2;
  shadow.position.y=floorY+.002;
  shadow.receiveShadow=true;scene.add(shadow);

  const floor=new THREE.Mesh(new THREE.PlaneGeometry(50,50),
    new THREE.MeshStandardMaterial({color:'#3e5266',roughness:.89,metalness:.09}));
  floor.rotation.x=-Math.PI/2;floor.position.y=floorY;floor.receiveShadow=true;scene.add(floor);

  // The translucent shadow and floor are excluded from AO just like upstream Teardown's V8 stage.
  class Toggle extends Pass {
    constructor(fn){super();this.needsSwap=false;this.fn=fn;}
    render(){this.fn();}
  }
  const composer=new EffectComposer(renderer,new THREE.WebGLRenderTarget(4,4,{
    type:THREE.HalfFloatType,samples:4
  }));
  composer.addPass(new RenderPass(scene,camera));
  const gtao=new GTAOPass(scene,camera,4,4);
  gtao.output=GTAOPass.OUTPUT.Default;
  gtao.blendIntensity=.62;
  gtao.updateGtaoMaterial({radius:.06,distanceExponent:1.4,thickness:.7,
    scale:1.0,samples:8,distanceFallOff:1.0,screenSpaceRadius:false});
  gtao.updatePdMaterial({lumaPhi:10,depthPhi:2,normalPhi:3,radius:5,rings:2,samples:8});
  composer.addPass(new Toggle(()=>{floor.visible=false;shadow.visible=false;}));
  composer.addPass(gtao);
  composer.addPass(new Toggle(()=>{floor.visible=true;shadow.visible=true;}));
  composer.addPass(new OutputPass());
  let adaptiveFallback=false;
  return {
    resize(w,h,ratio=1){composer.setPixelRatio(ratio);composer.setSize(w,h);},
    render(){
      const start=performance.now();
      composer.render();
      // GTAO is GPU-heavy; in software/low-performance browsers downgrade
      // to actual shadow maps + PBR IBL instead of leaving the UI frozen.
      if(gtao.enabled && performance.now()-start>160){
        gtao.enabled=false;
        adaptiveFallback=true;
      }
    },
    summary(){return {material:'source-bound STEP PBR',stage:'softbox PMREM + shadows + GTAO',
      gtaoEnabled:gtao.enabled,adaptiveFallback,floorY};}
  };
}
