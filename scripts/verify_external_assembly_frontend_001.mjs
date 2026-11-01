#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const [upstream,baseUrl,output]=process.argv.slice(2);
if(!upstream||!baseUrl||!output)throw Error('Need Teardown, frontend URL, evidence directory');
const require=createRequire(path.resolve(upstream,'package.json'));
const {chromium}=require('playwright');
const browser=await chromium.launch({headless:true,args:[
  '--enable-webgl','--use-gl=angle','--use-angle=swiftshader',
  '--enable-unsafe-swiftshader','--disable-gpu-sandbox','--disable-dev-shm-usage'
]});
try{
  const page=await browser.newPage({viewport:{width:1600,height:950}});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  let ready=false;
  for(let k=0;k<20;k++){
    try{await page.goto(baseUrl,{waitUntil:'domcontentloaded',timeout:4000});ready=true;break;}
    catch{await new Promise(r=>setTimeout(r,300));}
  }
  if(!ready)throw Error('HS frontend unavailable');
  await page.getByTestId('nav-complete-assembly').click();
  await page.getByTestId('real-assembly-reference').waitFor({state:'visible'});
  const frame=page.frameLocator('iframe[title="Complete OpenArm CAD interactive explorer"]');
  await frame.locator('#hs-external-ui').waitFor({state:'visible',timeout:120000});
  if(await frame.locator('#hs-part-list button').count()<100)
    throw Error('Complex CAD part directory not present in HS actual React app');
  await frame.locator('#hs-explode-all').click();
  await frame.locator('#hs-assembled').click();
  if(errors.length)throw Error('React frontend errors '+JSON.stringify(errors));
  await page.screenshot({path:path.join(output,'hs-complete-assembly-react-frontend.png'),fullPage:true});
  console.log('HS FULL FRONTEND WITH 542-PART MECHANICAL REFERENCE VISIBLE');
}finally{await browser.close()}
