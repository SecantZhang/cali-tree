const {chromium}=require('../../../web/node_modules/playwright');
const fs=require('fs');
const root='/Users/zzhang/.codex/visualizations/2026/10/06/01a11245-a1f4-7cb0-be00-f8687489a6d0';
let browser;
(async()=>{
  browser=await chromium.launch({headless:true,channel:'chrome'});
  const context=await browser.newContext({viewport:{width:900,height:1500}}),network=[],errors=[];
  await context.route('**/*',r=>/^(file:|data:|blob:|about:)/.test(r.request().url())?r.continue():(network.push(r.request().url()),r.abort()));
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file://'+root+'/calitree-jacket-simple.html');const f=page.frameLocator('iframe');
  await f.locator('#js-step option').first().waitFor({state:'attached'});
  const expectedCounts={'luna-proposer':20,'sol-proposer':24};let steps=0,questions=0;
  const choose=async(id,val)=>f.locator('#'+id).selectOption(String(val));
  for(const arm of Object.keys(expectedCounts)){
    await choose('js-arm',arm);
    if(await f.locator('#js-step option').count()!==expectedCounts[arm])throw Error('Wrong step count');
    const seed=await f.locator('#js-questions .answer').allTextContents();
    if(JSON.stringify(seed)!==JSON.stringify(['Decision: NO','Decision: NO','Decision: UNSATISFIED']))throw Error('Wrong starting answers');
    for(let i=0;i<expectedCounts[arm];i++){
      await choose('js-step',i);steps++;
      if(await f.locator('#js-error').isVisible())throw Error(await f.locator('#js-error').textContent());
      const labels=await f.locator('#js-questions .answer').allTextContents();questions+=labels.length;
      const title=await f.locator('#js-title').textContent();
      if(title.includes('proposed questions')||title.includes('Review the starting')||title.includes('freeze')){
        if(labels.some(v=>v!=='Decision: NOT RUN'))throw Error('Unmeasured proposal shown as a decision');
      }
      const frame=page.frames().find(v=>v.parentFrame());
      const overflow=await frame.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);
      if(overflow)throw Error('Overflow '+arm+' '+i);
    }
    const end=await f.locator('#js-questions .answer').allTextContents();
    if(arm==='sol-proposer'&&JSON.stringify(end)!==JSON.stringify(['Decision: UNCERTAIN in all 5 runs','Decision: NOT RUN in all 5 runs','Decision: NOT RUN in all 5 runs','Decision: NOT RUN in all 5 runs']))throw Error('Wrong Sol final answers');
    if(!/NOT LOCALLY ROBUST/.test(await f.locator('#js-next-action').textContent()))throw Error('Missing final acceptance');
  }
  const layouts=[];
  for(const width of [736,360,320])for(const scheme of ['light','dark']){
    await page.setViewportSize({width,height:1300});await page.emulateMedia({colorScheme:scheme});
    await page.waitForTimeout(100);
    const frame=page.frames().find(v=>v.parentFrame());const sizes=await frame.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
    if(sizes.scroll>sizes.client+1)throw Error('Mobile overflow');layouts.push({width,scheme,...sizes});
  }
  await page.setViewportSize({width:900,height:1800});await page.emulateMedia({colorScheme:'light'});
  await choose('js-arm','luna-proposer');await choose('js-step',0);
  await page.screenshot({path:'/private/tmp/calitree-jacket-simple.png',fullPage:true});
  await choose('js-arm','sol-proposer');await choose('js-step',23);
  await page.screenshot({path:'/private/tmp/calitree-jacket-simple-sol.png',fullPage:true});
  if(network.length||errors.length)throw Error(JSON.stringify({network,errors}));
  const result={steps,questionDecisions:questions,layouts,network,errors,seedLabelsVerified:true,solFinalLabelsVerified:true};
  fs.writeFileSync(root+'/calitree-jacket-simple-qa.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));await browser.close();
})().catch(async e=>{console.error(e);if(browser)await browser.close();process.exitCode=1;});
