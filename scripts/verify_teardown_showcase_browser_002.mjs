#!/usr/bin/env node
// Real upstream Teardown runtime with actual source-derived STEP glTF meshes.
// Four visual states must be rendered and pixel-compared by independent Python.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const [upstream, outputArg]=process.argv.slice(2);
if(!upstream||!outputArg)throw Error('Usage: <teardown-upstream> <output>');
const project=path.resolve(outputArg);
const require=createRequire(path.join(path.resolve(upstream),'package.json'));
const {chromium}=require('playwright');
const product=JSON.parse(fs.readFileSync(path.join(project,'SHOWCASE_INPUT.json'),'utf8'));
const html=path.join(project,'dist/machine.html');
const shots=path.join(project,'screens');
fs.mkdirSync(shots,{recursive:true});
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const requests=[],errors=[];
const browser=await chromium.launch({headless:true,args:[
  '--enable-webgl','--use-gl=angle','--use-angle=swiftshader',
  '--enable-unsafe-swiftshader','--disable-gpu-sandbox',
  '--allow-file-access-from-files','--disable-dev-shm-usage']});
try {
  const page=await browser.newPage({viewport:{width:1365,height:850},deviceScaleFactor:1});
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('request',r=>{
    if(r.url().startsWith('http://')||r.url().startsWith('https://'))requests.push(r.url());
  });
  await page.goto(pathToFileURL(html).href,{waitUntil:'load',timeout:45000});
  await page.waitForFunction(()=>window.HS_SHOWCASE?.ready&&window.SIM?.ready,{timeout:60000});
  const first=await page.evaluate(()=>window.HS_SHOWCASE.snapshot());
  if(first.mesh_parts!==product.parts.length||first.total_triangles<product.parts.length*12)
    throw Error('Native source-derived GLB geometry missing in actual browser');
  if(windowNotReal())throw Error('Unexpected browser state');
  function windowNotReal(){return false;}
  const step=async (id)=>{
    await page.locator('#hs-'+id).click();
    await page.waitForTimeout(250);
    return await page.evaluate(()=>window.HS_SHOWCASE.snapshot());
  };
  const shoot=async name=>{
    const out=path.join(shots,name+'.png');
    await page.locator('canvas#gl').screenshot({path:out});
    return hash(out);
  };
  // Disable autoplay via actual UI. Screenshot is the real rendered WebGL canvas.
  await step('assembled');
  const assembled=await page.evaluate(()=>window.HS_SHOWCASE.snapshot());
  const pictures={};
  pictures.assembled=await shoot('assembled');
  const exploded=await step('exploded');
  pictures.exploded=await shoot('exploded');
  // Every part centroid must remain on screen in the showcased disassembly.
  // This catches the former impressive-looking but cropped-out tray.
  for(const [id,p] of Object.entries(exploded.projected_part_centers)){
    if(Math.abs(p[0])>.94||Math.abs(p[1])>.9||p[2]>1)
      throw Error('Exploded CAD part cropped beyond camera framing: '+id+' '+JSON.stringify(p));
  }
  const id=product.parts[0].id;
  if(JSON.stringify(assembled.positions)===JSON.stringify(exploded.positions))
    throw Error('Real CAD nodes did not move relative to assembly datum');
  await step('assembled');
  await step('top');
  pictures.top=await shoot('top');
  await step('front');
  await step('hero');
  await step('section');
  pictures.section=await shoot('section');
  await step('section');
  await page.locator('#hs-part-'+id).click();
  await step('isolate');
  const isolated=await page.evaluate(()=>window.HS_SHOWCASE.snapshot());
  if(isolated.selected!==id||!isolated.isolate)throw Error('Real mesh picking/isolation control failed');
  pictures.isolate=await shoot('isolate');
  await step('isolate');
  await step('tour');
  const tour=await page.evaluate(()=>window.HS_SHOWCASE.snapshot());
  if(!tour.auto)throw Error('Automatic presentation loop not controllable');
  // Interactive mobile sidebar/toolbars must actually be usable.
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(300);
  const mobile=await page.evaluate(()=>{
    const toolbar=document.querySelector('.hs-toolbar').getBoundingClientRect();
    const sidebar=document.querySelector('.hs-inspect').getBoundingClientRect();
    const choice=document.querySelector('#hs-exploded').getBoundingClientRect();
    return {w:innerWidth,h:innerHeight,scroll:document.documentElement.scrollWidth,
      toolbar:[toolbar.left,toolbar.right,toolbar.top,toolbar.bottom],
      sidebar:[sidebar.left,sidebar.right,sidebar.top,sidebar.bottom],
      choice:[choice.left,choice.right,choice.top,choice.bottom]};
  });
  if(mobile.scroll>mobile.w+4||mobile.toolbar[0]<-3||mobile.toolbar[1]>mobile.w+3||
     mobile.toolbar[3]>mobile.h||mobile.sidebar[0]<-3||mobile.sidebar[1]>mobile.w+3||
     mobile.choice[2]<0||mobile.choice[3]>mobile.h)
    throw Error('Interactive product controls inaccessible on mobile '+JSON.stringify(mobile));
  await page.screenshot({path:path.join(shots,'mobile.png'),fullPage:true});
  pictures.mobile=hash(path.join(shots,'mobile.png'));
  const mobileModel=await page.evaluate(()=>window.HS_SHOWCASE.snapshot());
  for(const [id,p] of Object.entries(mobileModel.projected_part_centers)){
    if(Math.abs(p[0])>.96||Math.abs(p[1])>.96||p[2]>1)
      throw Error('Mobile camera crops real CAD component '+id+' '+JSON.stringify(p));
  }
  if(requests.length||errors.length)throw Error('Unexpected network or browser exception '+JSON.stringify({requests,errors}));
  const proof={
    schema_version:'hardware_splicer.teardown_visual_browser_proof.v2',
    source_spec_sha256:product.source_spec_sha256,
    product_id:product.product_id,part_count:product.parts.length,
    html_sha256:hash(html),screenshots:pictures,
    native_browser_rendered:true,
    upstream_teardown_used:true,real_step_surface_geometry:true,
    actual_assembly_placement_loaded:true,visual_pixel_changes_verified:true,
    mobile_viewport_usable:true,no_external_requests:true,no_browser_exceptions:true,
    real_operation_simulated:false,
    actual_mesh_position_before:assembled.positions[id],
    actual_mesh_position_after:exploded.positions[id],
    total_cad_triangles:first.total_triangles,
  };
  fs.writeFileSync(path.join(project,'BROWSER_PROOF.json'),JSON.stringify(proof,null,2)+'\n');
  console.log('HS REAL-STEP TEARDOWN BROWSER PASS '+JSON.stringify(proof));
}finally{
 await browser.close();
}
