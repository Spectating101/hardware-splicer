#!/usr/bin/env node
// Test the ORIGINAL source application's existing controls. No HS viewer logic.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import crypto from 'node:crypto';
const [browserRoot, siteUrl, artifactDir]=process.argv.slice(2);
if(!browserRoot||!siteUrl||!artifactDir)throw Error('playwright root, site URL and evidence dir required');
const req=createRequire(path.resolve(browserRoot,'package.json'));
const {chromium}=req('playwright');
fs.mkdirSync(artifactDir,{recursive:true});
const browser=await chromium.launch({headless:true,args:[
  '--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader',
  '--disable-gpu-sandbox','--disable-dev-shm-usage'
]});
const errors=[];
try {
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  page.on('pageerror',e=>errors.push(e.message));
  const resp=await page.goto(siteUrl,{waitUntil:'domcontentloaded',timeout:30000});
  if(!resp.ok())throw Error('HS app not served');
  await page.getByTestId('nav-complete-assembly').click();
  const engineering=page.getByTestId('upstream-robot-engineering');
  await engineering.waitFor({state:'visible',timeout:30000});
  if(!(await engineering.innerText()).includes('URDF links') ||
     !(await engineering.innerText()).includes('HS engineering interfaces'))
    throw Error('HS real upstream engineering project is not attached to original CAD viewer');
  const lineage=await page.evaluate(async()=>{
    const r=await fetch('/reference-assemblies/openarm/engineering/OPENARM_SOURCE_LINEAGE.json');
    if(!r.ok)throw Error('engineering source lineage missing');
    return r.json();
  });
  if(lineage.hs_native_projection.mechanical_components<20 ||
     lineage.reconciliation.same_assembly_topology_joined!==false)
    throw Error('No native multi-component HS engineering projection or variant mismatch disclosure');
  const view=page.frameLocator('iframe[title="Original OpenArm mechanical CAD viewer"]');
  const badge=view.locator('#parts-count-badge');
  const waitLoaded=async expected=>{
    await view.locator('#loading-overlay.hidden').waitFor({state:'attached',timeout:150000});
    await view.locator('#parts-list .part-row').first().waitFor({state:'attached',timeout:20000});
    const n=await view.locator('#parts-list .part-row').count();
    if(n!==expected)throw Error('Original upstream browser rendered '+n+' parts instead of '+expected);
    const text=await badge.textContent();
    if(!text.includes(String(expected)))throw Error('Original upstream badge wrong: '+text);
  };
  await waitLoaded(542);
  const frame=page.frames().find(f=>f.url().includes('/reference-assemblies/openarm/index.html'));
  if(!frame)throw Error('Original iframe missing');
  const capture=async file=>{
    const png=await frame.evaluate(()=>{
      const c=document.querySelector('#canvas3d canvas');
      if(!(c instanceof HTMLCanvasElement)||c.width<600||c.height<400)
        throw Error('upstream canvas has no native graphics');
      return c.toDataURL('image/png').split(',')[1];
    });
    fs.writeFileSync(path.join(artifactDir,file),Buffer.from(png,'base64'));
  };
  await capture('openarm-original-follower.png');
  await view.locator('#select-explode-scope').selectOption('LEFT');
  await view.locator('#explode-slider').evaluate(el=>{
    el.value='55';el.dispatchEvent(new Event('input',{bubbles:true}));
  });
  await capture('openarm-original-left-arm-exploded.png');
  await view.locator('#btn-leader').click();
  await waitLoaded(516);
  await capture('openarm-original-leader.png');
  if(errors.length)throw Error('Source viewer JS exceptions: '+JSON.stringify(errors));
  const evidence={
    schema_version:'hardware_splicer.original_upstream_viewer_browser.v1',
    source_ref:'0c0852bd76ee7026f97875d6eac789d189a0012a',
    source_viewer_original:true,upstream_viewer_rendered:true,
    both_source_models_load:true,verified_part_counts:[542,516],
    original_urdf_engineering_project_connected:true,
    projected_engineering_components:lineage.hs_native_projection.mechanical_components,
    topology_links:lineage.upstream_robot_description.published_links,
    topology_joints:lineage.upstream_robot_description.published_joints,
    hs_reimplemented_controls:false,physical_motion_verified:false,
    screenshots:['openarm-original-follower.png','openarm-original-left-arm-exploded.png',
      'openarm-original-leader.png'].map(name=>({
      name,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(artifactDir,name))).digest('hex')
    }))
  };
  fs.writeFileSync(path.join(artifactDir,'UPSTREAM_BROWSER_PROOF.json'),JSON.stringify(evidence,null,2));
  console.log('ORIGINAL UPSTREAM VIEWER IN HS REACT VERIFIED '+JSON.stringify(evidence));
}finally{await browser.close()}
