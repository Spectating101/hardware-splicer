#!/usr/bin/env node
// Separate integration check of the existing HS React route and real source Teardown instance.
import {createRequire} from 'node:module';
import path from 'node:path';
const [root,url]=process.argv.slice(2);
if(!root||!url)throw Error('expected original Teardown deps root and React preview URL');
const require=createRequire(path.resolve(root,'package.json'));
const {chromium}=require('playwright');
const browser=await chromium.launch({headless:true,args:[
 '--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader',
 '--disable-gpu-sandbox','--disable-dev-shm-usage'
]});
try{
 const page=await browser.newPage({viewport:{width:1500,height:900}});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.__CAPTURE=true;});
 await page.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
 await page.getByTestId('nav-sortcell').click();
 await page.getByTestId('sorting-workcell').waitFor({state:'visible',timeout:25000});
 const frame=page.frameLocator('iframe[title="SORTCELL S1 original OpenArm CAD Teardown workcell"]');
 await frame.locator('#sw-ui').waitFor({state:'visible',timeout:150000});
 const iframe=page.frames().find(x=>x.url().includes('/sortcell/machine.html'));
 if(!iframe)throw Error('No actual native Teardown instance embedded in HS');
 const data=await iframe.evaluate(()=>window.HS_SORTCELL.snapshot());
 if(data.sourcePartCount!==542||data.physicalMotionVerified!==false)
  throw Error('Not original source robot CAD in HS app: '+JSON.stringify(data));
 await frame.locator('#sw-robot').click();
 await frame.locator('#sw-explode').evaluate(el=>{el.value='45';el.dispatchEvent(new Event('input',{bubbles:true}));});
 await iframe.evaluate(()=>window.SIM.render(6));
 const expl=await iframe.evaluate(()=>window.HS_SORTCELL.snapshot());
 if(expl.selected!=='ROBOT'||expl.explode!==.45)
  throw Error('Actual HS embedded Teardown controls not operable');
 if(errors.length)throw Error('Browser JS exceptions: '+JSON.stringify(errors));
 console.log('SORTCELL / S1 embedded in main HS React OK 542 real named source parts, working interactive inspection');
}finally{await browser.close()}
