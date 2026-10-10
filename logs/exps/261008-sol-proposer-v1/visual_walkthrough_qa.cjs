const {chromium}=require('../../../web/node_modules/playwright');
const fs=require('fs');
const root='/Users/zzhang/.codex/visualizations/2026/10/06/01a11245-a1f4-7cb0-be00-f8687489a6d0';
const data=JSON.parse(fs.readFileSync(root+'/calitree-sol-leaf-walkthrough-data.json','utf8'));
let browser;
(async()=>{
  browser=await chromium.launch({headless:true,channel:'chrome'});
  const context=await browser.newContext({viewport:{width:736,height:1000},colorScheme:'light'});
  await context.route('**/*',r=>/^(file:|data:|blob:|about:)/.test(r.request().url())?r.continue():r.abort());
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file://'+root+'/calitree-sol-leaf-preview.html');
  const frame=page.frameLocator('iframe');await frame.locator('#clw-stage option').first().waitFor({state:'attached'});
  const stats={stages:0,repairs:0,measurements:0,nodeSelections:0};
  async function choose(id,value){await frame.locator('#'+id).selectOption(String(value));await page.waitForTimeout(25);}
  async function check(){if(await frame.locator('#clw-error').isVisible())throw Error(await frame.locator('#clw-error').textContent());}
  for(let c=0;c<3;c++)for(const model of ['sol-proposer','luna-proposer']){
    await choose('clw-case',c);await choose('clw-model',model);
    const stages=await frame.locator('#clw-stage option').count();
    for(let stage=0;stage<stages;stage++){
      await choose('clw-stage',stage);stats.stages++;await check();
      const repairCount=await frame.locator('#clw-repair option').count();
      for(let repair=0;repair<Math.max(1,repairCount);repair++){
        if(repairCount){await choose('clw-repair',repair);stats.repairs++;}
        const options=await frame.locator('#clw-measure option').evaluateAll(nodes=>nodes.map(n=>n.value));
        for(const option of options){await choose('clw-measure',option);stats.measurements++;await check();}
      }
    }
    const run=data.cases[c].runs[model];
    const expected=Math.round(run.final.seed.agreement*5)+' → '+Math.round(run.final.selected.agreement*5)+' / 5';
    if((await frame.locator('#clw-matches').textContent())!==expected)throw Error('Wrong matches: '+c+' '+model);
    await choose('clw-measure','selected');
    const nodes=await frame.locator('#clw-flow button').count();
    for(let n=0;n<nodes;n++){await frame.locator('#clw-flow button').nth(n).click();stats.nodeSelections++;await check();}
    await choose('clw-draw',0);await frame.locator('#clw-flow button').first().click();await check();
  }
  const layouts=[];
  for(const width of [736,360,320])for(const theme of ['light','dark']){
    await page.setViewportSize({width,height:1200});await page.emulateMedia({colorScheme:theme});
    await choose('clw-case',0);await choose('clw-model','sol-proposer');
    await choose('clw-stage',(await frame.locator('#clw-stage option').count())-1);
    await frame.locator('#clw-flow button').nth(1).click();
    const surface=page.frames().find(f=>f.parentFrame());
    const overflow=await surface.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,
      root:document.getElementById('calitree-leaf-steps').getBoundingClientRect().width}));
    if(overflow.scroll>overflow.client+1)throw Error('Horizontal overflow '+JSON.stringify({width,theme,...overflow}));
    layouts.push({width,theme,...overflow});
    if(width===736&&theme==='light')await page.screenshot({path:'/private/tmp/calitree-sol-leaf-qa.png',fullPage:true});
    if(width===320&&theme==='dark')await page.screenshot({path:'/private/tmp/calitree-sol-leaf-mobile.png',fullPage:true});
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  const result={...stats,layouts,runtimeErrors:errors,savedMetricsVerified:true};
  fs.writeFileSync(root+'/calitree-sol-leaf-qa.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  await browser.close();
})().catch(async e=>{console.error(e);if(browser)await browser.close();process.exitCode=1;});
