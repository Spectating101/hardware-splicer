#!/usr/bin/env node
// Real browser visual evidence: source OpenArm + Teardown rendering + task progression.
// Run under Chromium with software WebGL and Teardown capture mode.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const [teardownRoot,url,outArg]=process.argv.slice(2);
if(!teardownRoot||!url||!outArg)throw Error('expected Teardown deps root, served URL, output directory');
const require=createRequire(path.resolve(teardownRoot,'package.json'));
const {chromium}=require('playwright');
const output=path.resolve(outArg);fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,args:[
 '--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader',
 '--disable-gpu-sandbox','--disable-dev-shm-usage'
]});
try{
 const page=await browser.newPage({viewport:{width:1600,height:960}});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.__CAPTURE=true;});
 const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:85000});
 if(!response.ok())throw Error('Teardown HTML not served');
 await page.waitForFunction(()=>window.SIM?.ready&&window.HS_SORTCELL?.ready,
   {timeout:140000,polling:1000});
 const frames=[];
 for(const [phase,t] of [['assembled',0],['inspection',4.25],['grasp',7.5],['transfer',10.5],['deposited',13.25]]){
   const details=await page.evaluate(time=>{
     window.SIM.render(time);
     const s=window.HS_SORTCELL.snapshot();
     const c=document.getElementById('gl');
     if(!c||c.width<1100||c.height<650)throw Error('Missing actual source-rendered WebGL scene');
     const thumb=document.createElement('canvas');
     thumb.width=320;thumb.height=200;
     const cx=thumb.getContext('2d',{willReadFrequently:true});
     cx.drawImage(c,0,0,thumb.width,thumb.height);
     const p=cx.getImageData(0,0,thumb.width,thumb.height).data;
     let bright=0,contrast=0;
     for(let k=0;k<p.length;k+=4){
       const max=Math.max(p[k],p[k+1],p[k+2]),min=Math.min(p[k],p[k+1],p[k+2]);
       if(max>115)bright++;
       if(max-min>27&&max>115)contrast++;
     }
     return {...s,bright,contrast,png:c.toDataURL('image/png').split(',')[1]};
   },t);
   const png=Buffer.from(details.png,'base64');
   const name='sortcell-'+phase+'.png';
   fs.writeFileSync(path.join(output,name),png);
   const {png:_,...rest}=details;
   if(rest.sourcePartCount!==542||rest.physicalMotionVerified!==false ||
      rest.computerVisionExecuted!==false)throw Error('Unsupported source/model claims: '+JSON.stringify(rest));
   if(rest.bright<3500||rest.contrast<900)throw Error('Blank or insufficient mechanical geometry: '+JSON.stringify(rest));
   frames.push({name,t,...rest,sha256:crypto.createHash('sha256').update(png).digest('hex')});
   console.log('TEARDOWN ROBOT WORKCELL VISUAL '+JSON.stringify({name,bright:rest.bright,contrast:rest.contrast,phase:rest.phase,partCount:rest.sourcePartCount}));
 }
 // The three categories must route to three different physical tray coordinates.
 const destinations=[];
 for(const [category,target] of [['0',.45],['1',.97],['2',1.49]]){
   await page.locator('#sw-category-select').selectOption(category);
   const lane=await page.evaluate(()=>{
     window.SIM.render(13.5);
     return window.HS_SORTCELL.snapshot();
   });
   if(Math.abs(lane.workpiece_xyz[0]-target)>.015)
     throw Error('Sorting category not routed to its own tray: '+JSON.stringify({category,lane}));
   destinations.push({category:lane.classification,workpiece_xyz:lane.workpiece_xyz});
 }
 await page.locator('#sw-category-select').selectOption('1');
 // Full presentation screenshot in addition to the raw proof of WebGL pixels.
 // Keep canvas acceptance as the hard requirement if SwiftShader compositor is slow.
 await page.evaluate(()=>window.SIM.render(0));
 try{
   await page.screenshot({path:path.join(output,'sortcell-entire-teardown-ui.png'),fullPage:false,timeout:35000});
   console.log('FULL TEARDOWN INTERFACE screenshot captured');
 }catch(e){console.log('Full UI compositor unsupported; actual canvas captures remain valid: '+e.message);}
 const different=frames.some(x=>JSON.stringify(x.workpiece_xyz)!==JSON.stringify(frames[0].workpiece_xyz));
 if(!different||new Set(frames.map(x=>x.phase)).size<5)
  throw Error('No distinct sorting phases or genuine moving 3D workpieces');
 await page.locator('#sw-robot').click();
 await page.locator('#sw-explode').evaluate(el=>{el.value='60';el.dispatchEvent(new Event('input',{bubbles:true}));});
 await page.evaluate(()=>window.SIM.render(2));
 const exploded=await page.evaluate(()=>window.HS_SORTCELL.snapshot());
 if(exploded.selected!=='ROBOT'||exploded.explode!==.6)throw Error('Source component exploration not operable');
 await page.locator('#sw-reset').click();
 await page.locator('#sw-next').click();
 await page.evaluate(()=>window.SIM.render(0));
 const navigated=await page.evaluate(()=>window.HS_SORTCELL.snapshot());
 if(navigated.stage!==1||navigated.explode!==0)throw Error('Task timeline and reset not working');
 if(errors.length)throw Error('Page errors: '+JSON.stringify(errors));
 const proof={
   schema_version:'hardware_splicer.sortcell_browser_proof.v1',
   original_source_meshes:542,upstream_teardown_engine_executed:true,
   real_3d_frames_rendered:true,actual_workpieces_move:true,
   original_part_explosion_operable:true,
   task_phase_navigation_operable:true,
   source_geometry_authored_by_hs:false,
   robot_motion_physically_verified:false,
   camera_classification_real:false,
   workcell_fabricated:false,verified_sorting_destinations:destinations,frames
 };
 fs.writeFileSync(path.join(output,'SORTCELL_BROWSER_PROOF.json'),JSON.stringify(proof,null,2));
 console.log('SORTCELL / S1 ACCEPTANCE '+JSON.stringify({passed:true,frames:frames.length,original_source_meshes:542}));
}finally{await browser.close()}
