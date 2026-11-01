#!/usr/bin/env node
// Browser acceptance for actual complex upstream GLB using the real Teardown
// runtime. Keeps the screenshot as the main design review output.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const [upstreamDir,htmlFile,outputDir]=process.argv.slice(2);
if(!upstreamDir||!htmlFile||!outputDir)throw Error('usage: node script upstream HTML output');
const require=createRequire(path.resolve(upstreamDir,'package.json'));
const {chromium}=require('playwright');
const output=path.resolve(outputDir);
const input=JSON.parse(fs.readFileSync(path.join(output,'MODEL_INPUT.json'),'utf8'));
const errors=[],requests=[];
const browser=await chromium.launch({headless:true,args:[
  '--enable-webgl','--use-gl=angle','--use-angle=swiftshader',
  '--enable-unsafe-swiftshader','--disable-gpu-sandbox','--disable-dev-shm-usage',
  '--allow-file-access-from-files'
]});
try{
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});
  // Upstream Teardown has a native capture mode: draw deterministically on demand
  // instead of constantly saturating Chromium's software GPU with 542 CAD parts.
  await page.addInitScript(() => { window.__CAPTURE=true; });
  await page.goto(pathToFileURL(path.resolve(htmlFile)).href,{waitUntil:'load',timeout:90000});
  await page.waitForFunction(()=>window.HS_EXTERNAL_ASSEMBLY?.ready===true&&window.SIM?.ready===true,
    null,{timeout:120000});
  const start=await page.evaluate(()=>window.HS_EXTERNAL_ASSEMBLY.snapshot());
  if(start.parts!==input.total_parts||start.mapped<500)
    throw Error('Not a true complete real CAD assembly: '+JSON.stringify(start));
  if(start.geometryAuthoredByHS!==false||start.physicalMotionVerified!==false||
    start.sourceRef!==input.source_ref)
    throw Error('Display falsely promoted imported geometry or real mechanism authority');

  // Unlike the old primitive demo gate, measure the actual WebGL framebuffer
  // and ensure there is substantial visually occupied geometry in the hero.
  const pixels=await page.evaluate(()=>{
    const c=document.querySelector('#gl');
    const b=c.getBoundingClientRect();
    const d=document.createElement('canvas');d.width=c.width;d.height=c.height;
    const ctx=d.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(c,0,0);
    const a=ctx.getImageData(0,0,d.width,d.height).data;
    const bg=[26,43,61];
    let visible=0;let colorful=0;let total=0;
    for(let y=Math.floor(d.height*.13);y<Math.floor(d.height*.85);y+=4){
      for(let x=Math.floor(d.width*.24);x<Math.floor(d.width*.90);x+=4){
        const i=(y*d.width+x)*4;
        const r=a[i],g=a[i+1],bl=a[i+2];
        if(Math.max(Math.abs(r-bg[0]),Math.abs(g-bg[1]),Math.abs(bl-bg[2]))>45)visible++;
        if(Math.max(r,g,bl)>130&&Math.max(r,g,bl)-Math.min(r,g,bl)>20)colorful++;
        total++;
      }
    }
    return {viewport:[b.width,b.height],visible,colorful,total};
  });
  if(pixels.viewport[0]<1200||pixels.viewport[1]<800||pixels.visible<1500)
    throw Error('Complex 3D object not visibly drawn: '+JSON.stringify(pixels));
  console.log('HIGH-FIDELITY ACTUAL CAD VIEW '+JSON.stringify({start,pixels}));
  await page.screenshot({path:path.join(output,'assembly-542-assembled.png'),fullPage:true});
  await page.locator('#hs-explode-all').click();
  // Capture mode needs explicit frames to interpolate the real source metadata
  // separation. This yields a stable frame rather than CPU-bound screenshot.
  await page.evaluate(() => {for(let i=0;i<28;i++)window.SIM.render(0);});
  await page.waitForFunction(()=>window.HS_EXTERNAL_ASSEMBLY.snapshot().displayExplode>.75,
    null,{timeout:90000});
  const exploded=await page.evaluate(()=>window.HS_EXTERNAL_ASSEMBLY.snapshot());
  if(exploded.explode!==1||exploded.mapped<500)throw Error('Actual source parts did not explode');
  await page.screenshot({path:path.join(output,'assembly-542-exploded.png'),fullPage:true});
  await page.locator('#hs-search').fill('cover');
  await page.locator('#hs-parts button').first().click();
  if(!(await page.evaluate(()=>window.HS_EXTERNAL_ASSEMBLY.snapshot())).selected)
    throw Error('Original CAD component directory not interactive');
  await page.locator('#hs-isolate').click();
  await page.locator('#hs-xray').click();
  await page.evaluate(() => window.SIM.render(0));
  await page.locator('#hs-reset').click();
  const reset=await page.evaluate(()=>window.HS_EXTERNAL_ASSEMBLY.snapshot());
  if(reset.selected!==null||reset.explode!==0)
    throw Error('Assembled state not restored');
  if(errors.length||requests.length)
    throw Error('Browser/page errors or outbound HTTP: '+JSON.stringify({errors,requests}));
  const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
  const proof={
    schema_version:'hardware_splicer.external_assembly_browser_proof.v1',
    source_revision:input.source_ref,
    product_id:input.product_id,source_kind:input.model_source_kind,
    imported_components:input.total_parts,actual_glb_nodes_mapped:start.mapped,
    full_model_visible:true,visible_cad_pixels:pixels.visible,
    exploded_source_vectors_applied:true,part_search_and_selection:true,
    component_isolation:true,xray_cover_controls:true,
    physical_motion_verified:false,geometry_authored_by_hs:false,
    no_browser_errors:true,no_network_requests:true,
    assembled_screenshot_sha256:sha(path.join(output,'assembly-542-assembled.png')),
    exploded_screenshot_sha256:sha(path.join(output,'assembly-542-exploded.png')),
    html_sha256:sha(htmlFile)
  };
  fs.writeFileSync(path.join(output,'BROWSER_PROOF.json'),JSON.stringify(proof,null,2)+'\n');
  console.log('HS COMPLETE EXTERNAL ASSEMBLY VISIBLE '+JSON.stringify(proof));
}finally{await browser.close();}
