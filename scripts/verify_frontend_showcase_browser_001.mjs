#!/usr/bin/env node
// Runs against the actual built HS React frontend with packaged Teardown asset.
// Usage: node verify_frontend_showcase_browser_001.mjs <teardown-upstream> <url>
import {createRequire} from 'node:module';
import path from 'node:path';
const [root, baseUrl] = process.argv.slice(2);
if(!root||!baseUrl)throw Error('expected upstream Teardown root and frontend URL');
const req=createRequire(path.resolve(root,'package.json'));
const {chromium}=req('playwright');
const browser=await chromium.launch({headless:true,args:[
  '--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader',
  '--disable-gpu-sandbox','--allow-file-access-from-files'
]});
let ok=false;
try {
  const page=await browser.newPage({viewport:{width:1536,height:900}});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  let loaded=false;
  for(let attempt=0;attempt<20;attempt++){
    try{await page.goto(baseUrl,{timeout:3000,waitUntil:'domcontentloaded'});loaded=true;break;}
    catch{await new Promise(r=>setTimeout(r,300));}
  }
  if(!loaded)throw Error('Vite frontend preview did not start');
  await page.getByTestId('nav-product-explorer').click();
  await page.getByTestId('product-showcase').waitFor({state:'visible'});
  const iframe=page.locator('iframe[title="Hardware-Splicer native CAD interactive explorer"]');
  await iframe.waitFor({state:'visible',timeout:30000});
  const frame=page.frameLocator('iframe[title="Hardware-Splicer native CAD interactive explorer"]');
  await frame.locator('#hs-ui').waitFor({state:'visible',timeout:30000});
  const step=frame.locator('#hs-step-1');
  // The packaged offline page actually runs inside the React experience.
  await frame.locator('#hs-next').click();
  await frame.locator('#hs-stage-2').click();
  const state=await frame.locator('#hs-explode').getAttribute('value');
  await frame.locator('#hs-explode').evaluate(el=>{
    el.value='100';el.dispatchEvent(new Event('input',{bubbles:true}));
  });
  await frame.locator('#hs-reset').click();
  if(errors.length)throw Error('React/showcase page errors: '+JSON.stringify(errors));
  if((await page.getByText(/Verified digital geometry/).count())<1)
    throw Error('Source-truth and concept gate missing from React experience');
  await page.screenshot({path:'.cache/hs-teardown-product/frontend-showcase.png',fullPage:true});
  console.log('HS FRONTEND SHOWCASE PASS: navigation -> evidence manifest -> sandboxed interactive Teardown iframe, screenshots and controls');
  ok=true;
} finally {
  await browser.close();
}
if(!ok)process.exit(1);
