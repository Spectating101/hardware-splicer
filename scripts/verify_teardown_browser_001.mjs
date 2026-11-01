#!/usr/bin/env node
// Actual upstream Teardown + Chromium browser acceptance, not simulated DOM.
// node verify_teardown_browser_001.mjs <upstream> <html> <hs-output>
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const [upstream, htmlArg, outputArg] = process.argv.slice(2);
if (!upstream || !htmlArg || !outputArg) throw Error('Expected upstream, HTML and output paths');
const base=path.resolve(upstream);
const require=createRequire(path.join(base,'package.json'));
const {chromium}=require('playwright');
const output=path.resolve(outputArg);
const html=path.resolve(htmlArg);
const spec=JSON.parse(fs.readFileSync(path.join(output,'TEARDOWN_INPUT.json'),'utf8'));
const errors=[];
const requests=[];
const browser=await chromium.launch({headless:true,args:[
  '--enable-webgl','--use-gl=angle','--use-angle=swiftshader',
  '--enable-unsafe-swiftshader','--disable-gpu-sandbox',
  '--allow-file-access-from-files','--disable-dev-shm-usage'
]});
try {
  const page=await browser.newPage({viewport:{width:1280,height:800},deviceScaleFactor:1});
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('request',r=>{
    if(r.url().startsWith('https://')||r.url().startsWith('http://'))requests.push(r.url());
  });
  await page.goto(pathToFileURL(html).href,{waitUntil:'load',timeout:45000});
  await page.waitForFunction(()=>window.HS_TEARDOWN?.ready===true && window.SIM?.ready===true,
    {timeout:45000});
  const initial=await page.evaluate(()=>window.HS_TEARDOWN.snapshot());
  if(initial.studio?.stage!=='softbox PMREM + shadows + GTAO' ||
     initial.studio?.material!=='source-bound STEP PBR')
    throw Error('Native CAD viewer did not install actual product studio shading pipeline');
  if(initial.stage!==0 || initial.explode!==0 || initial.parts!==spec.parts.length)
    throw Error('Product must open assembled-first, with all source-bound CAD parts');
  // Inspect actual WebGL canvas image pixels, not JS state, HTML file size or
  // screenshots polluted by colored CSS overlays. This caught the previously
  // invisible CAD scene despite an entirely green CI run.
  const visual=await page.evaluate(()=>{
    const canvas=document.querySelector('canvas#gl');
    const box=canvas.getBoundingClientRect();
    const n=document.createElement('canvas');
    n.width=canvas.width;n.height=canvas.height;
    const context=n.getContext('2d',{willReadFrequently:true});
    context.drawImage(canvas,0,0);
    const data=context.getImageData(0,0,n.width,n.height).data;
    let objectColored=0, sampleCount=0;
    for(let y=Math.floor(n.height*.15);y<Math.floor(n.height*.84);y+=3){
      for(let x=Math.floor(n.width*.33);x<Math.floor(n.width*.84);x+=3){
        const p=(y*n.width+x)*4;
        const r=data[p],g=data[p+1],b=data[p+2];
        // actual colored, illuminated CAD parts; the dark grid cannot pass.
        if(Math.max(r,g,b)>130 && Math.max(r,g,b)-Math.min(r,g,b)>22)
          objectColored++;
        sampleCount++;
      }
    }
    return {canvasWidth:box.width,canvasHeight:box.height,objectColored,
      sampleCount,buttonBottom:document.querySelector('#hs-explode').getBoundingClientRect().bottom,
      appHeight:document.querySelector('#app').getBoundingClientRect().height};
  });
  if(visual.canvasWidth<900||visual.canvasHeight<600||visual.appHeight<600
     ||visual.buttonBottom>810||visual.objectColored<400)
    throw Error('Visual acceptance: actual CAD geometry missing or viewport collapsed: '+JSON.stringify(visual));
  console.log('HS VISUAL PIXEL ACCEPTANCE '+JSON.stringify(visual));
  if(initial.parts!==spec.parts.length)throw Error('Browser part inventory differs from HS input');
  await page.screenshot({path:path.join(output,'assembled.png'),fullPage:true});
  const id=spec.parts[0].id;
  await page.locator('#hs-part-'+id).click();
  const selected=await page.evaluate(()=>window.HS_TEARDOWN.snapshot());
  if(selected.selected!==id)throw Error('Part selection not functional');
  await page.locator('#hs-explode').evaluate(el=>{
    el.value='100';el.dispatchEvent(new Event('input',{bubbles:true}));
  });
  await page.waitForTimeout(150);
  const exploded=await page.evaluate(()=>window.HS_TEARDOWN.snapshot());
  if(exploded.explode!==1||Math.abs(initial.first_mesh_x-exploded.first_mesh_x)<0.01)
    throw Error('Geometry explosion not moving real meshes');
  await page.locator('#hs-section').click();
  await page.locator('#hs-isolate').click();
  const final=await page.evaluate(()=>window.HS_TEARDOWN.snapshot());
  if(!final.section||!final.isolate)throw Error('Section/isolate controls not functional');
  const head=await page.evaluate(()=>({
    source:window.HS_TEARDOWN.source_spec_sha256,
    product:window.HS_TEARDOWN.product_id,
    physical:window.HS_TEARDOWN.physical_kinematics_verified,
    canvasWidth:document.querySelector('canvas#gl')?.width||0
  }));
  if(head.source!==spec.source_spec_sha256||head.product!==spec.product_id||
     head.physical!==false||head.canvasWidth<100)throw Error('Browser runtime/source mismatch');
  if(requests.length||errors.length)throw Error('Browser errors or external requests: '+JSON.stringify({errors,requests}));
  const png=path.join(output,'viewer.png');
  await page.screenshot({path:png,fullPage:true});
  if(fs.readFileSync(path.join(output,'assembled.png')).equals(fs.readFileSync(png)))
    throw Error('Assembled vs exploded browser screenshots are pixel identical');
  await page.locator('#hs-stage-2').click();
  const guided=await page.evaluate(()=>window.HS_TEARDOWN.snapshot());
  if(guided.stage!==2 || guided.explode<=0.4)
    throw Error('Guided inspection steps not updating exploded geometry');
  await page.locator('#hs-reset').click();
  const reset=await page.evaluate(()=>window.HS_TEARDOWN.snapshot());
  if(reset.stage!==0||reset.explode!==0||reset.section||reset.isolate)
    throw Error('Full assembled reset failed');
  const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
  const proof={
    schema_version:'hardware_splicer.teardown_browser_proof.v1',
    source_spec_sha256:spec.source_spec_sha256,product_id:spec.product_id,
    part_count:spec.parts.length,native_browser_rendered:true,
    interactive_explode:true,selected_part:true,section_view:true,isolate_part:true,
    no_network_requests:requests.length===0,no_browser_errors:errors.length===0,
    physical_simulation_verified:false,
    html_sha256:sha(html),screenshot_sha256:sha(png),
    assembled_screenshot_sha256:sha(path.join(output,'assembled.png')),
    visual_states_differ:true,assembled_first:true,
    guided_stages_operable:true,full_screen_cad_visible:true,
    visible_cad_colored_samples:visual.objectColored,
    css_canvas_height_px:visual.canvasHeight,
    inspected_initial_mesh_x:initial.first_mesh_x,
    exploded_first_mesh_x:exploded.first_mesh_x
  };
  fs.writeFileSync(path.join(output,'BROWSER_PROOF.json'),JSON.stringify(proof,null,2)+'\n');
  console.log('UPSTREAM TEARDOWN NATIVE BROWSER PASS '+JSON.stringify(proof));
} finally {
  await browser.close();
}
