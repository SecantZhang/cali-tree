const {chromium}=require('../../../web/node_modules/playwright');
const fs=require('fs');
const path='/Users/zzhang/.codex/visualizations/2026/10/06/01a11245-a1f4-7cb0-be00-f8687489a6d0';
const saved=JSON.parse(fs.readFileSync(path+'/calitree-sol-leaf-walkthrough-data.json','utf8')).cases[0];
let browser;
(async()=>{
  browser=await chromium.launch({headless:true,channel:'chrome'});
  const context=await browser.newContext({viewport:{width:1000,height:1200}});
  const blocked=[];
  await context.route('**/*',route=>/^(file:|data:|blob:|about:)/.test(route.request().url())?route.continue():(blocked.push(route.request().url()),route.abort()));
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file://'+path+'/calitree-jacket-optimization.html');
  const f=page.frameLocator('iframe');
  await f.locator('#clw-stage option').first().waitFor({state:'attached'});
  if(await f.locator('#clw-model').inputValue()!=='luna-proposer')throw Error('Wrong initial proposer');
  if(!/Satisfied \(yes\)/.test(await f.locator('#clw-decision').textContent()))throw Error('Reference missing');
  let stages=0,repairs=0,measurements=0,checks=0;
  const choose=async(id,v)=>{await f.locator('#'+id).selectOption(String(v));};
  const valid=async()=>{if(await f.locator('#clw-error').isVisible())throw Error(await f.locator('#clw-error').textContent());};
  for(const model of ['luna-proposer','sol-proposer']){
    await choose('clw-model',model);
    const n=await f.locator('#clw-stage option').count();
    if(n!==20)throw Error('Missing saved rounds');
    for(let i=0;i<n;i++){
      await choose('clw-stage',i);await valid();stages++;
      const rp=await f.locator('#clw-repair option').count();
      for(let j=0;j<Math.max(1,rp);j++){
        if(rp){await choose('clw-repair',j);repairs++;}
        const choices=await f.locator('#clw-measure option').evaluateAll(ns=>ns.map(n=>n.value));
        for(const choice of choices){
          await choose('clw-measure',choice);measurements++;await valid();
          if(choice!=='proposal'&&!(await f.locator('#clw-decision').textContent()).includes('Compared with reference'))throw Error('Missing prediction table');
        }
      }
    }
    await choose('clw-measure','selected');
    const nn=await f.locator('#clw-flow button').count();
    for(let j=0;j<nn;j++){await f.locator('#clw-flow button').nth(j).click();checks++;await valid();}
    for(let d=0;d<5;d++){
      await choose('clw-draw',d);
      const text=await f.locator('#clw-decision').textContent();
      const trace=saved.runs[model].final.selected.traces[d];
      const expected=!trace.resolved?'Unresolved → does not match':trace.label===saved.reference?'Matches target':'Mismatch';
      if(!text.includes(expected))throw Error('Missing final draw decision '+model+' '+d);
    }
  }
  await choose('clw-model','luna-proposer');await choose('clw-stage',1);
  if(!(await f.locator('#clw-decision').textContent()).includes('Unsatisfied (no)'))throw Error('Seed label missing');
  const layouts=[];
  for(const width of [1000,736,360,320])for(const scheme of ['light','dark']){
    await page.setViewportSize({width,height:1200});await page.emulateMedia({colorScheme:scheme});
    await choose('clw-stage',19);await f.locator('#clw-flow button').last().click();
    const inner=page.frames().find(fr=>fr.parentFrame());
    const sizes=await inner.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
    if(sizes.scroll>sizes.client+1)throw Error('Horizontal overflow '+JSON.stringify({width,scheme,...sizes}));
    layouts.push({width,scheme,...sizes});
  }
  await page.setViewportSize({width:1000,height:2600});await page.emulateMedia({colorScheme:'light'});
  await choose('clw-stage',1);await f.locator('#clw-flow button').last().click();
  await page.screenshot({path:'/private/tmp/calitree-jacket-export.png',fullPage:true});
  if(errors.length)throw Error(JSON.stringify(errors));
  const result={stages,repairs,measurements,checks,layouts,errors,blockedNetworkRequests:blocked,standaloneOffline:true};
  fs.writeFileSync(path+'/calitree-jacket-optimization-qa.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));await browser.close();
})().catch(async e=>{console.error(e);if(browser)await browser.close();process.exitCode=1;});
