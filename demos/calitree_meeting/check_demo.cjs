/* Offline source/data/interaction checks. No server, browser, credentials, or API. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('../../web/node_modules/jsdom');
const dir = __dirname;
const dom = new JSDOM(fs.readFileSync(path.join(dir,'index.html'),'utf8'), {runScripts:'outside-only',url:'http://localhost/'});
const w=dom.window;
w.scrollTo=()=>{};
let tick=null;
w.setInterval=fn=>{tick=fn;return 1;};
w.clearInterval=()=>{tick=null;};
w.eval(fs.readFileSync(path.join(dir,'data.js'),'utf8'));
w.eval(fs.readFileSync(path.join(dir,'app.js'),'utf8'));
const doc=w.document,D=w.CALITREE_DATA;
const click=(action,value)=>{
  const selector=`button[data-action="${action}"]${value==null?'':`[data-value="${value}"]`}`;
  const button=doc.querySelector(selector);assert(button,selector);button.click();
};
const body=()=>doc.body.textContent;
const chapter=i=>click('stage',i);
let assertions=0;
const verify=(condition,message)=>{assert(condition,message);assertions++;};
verify(D.cases.length===12,'Exactly twelve cases');
verify(new Set(D.cases.map(c=>c.source_group)).size===12,'Distinct development sources');
verify(D.cases.reduce((s,c)=>s+c.program.checks.length,0)===90,'All ninety checks exported');
for(const c of D.cases) {
  assert.deepEqual(JSON.parse(JSON.stringify(w.CaliTreeDemo.execute(c.features.features))),JSON.parse(JSON.stringify(c.prediction)));
  for(const image of Object.values(c.images)) verify(fs.existsSync(path.join(dir,image)),'Local image exists');
  for(const check of c.program.checks) verify(c.record.checks[check.id].check_ref===check.check_ref,'Bound question identity');
}
for(let i=0;i<9;i++) {chapter(i);verify(doc.querySelector('h1')?.textContent.length>10,'Chapter renders');verify(!body().includes('undefined'),'No undefined content');}
chapter(2);
for(const tab of ['data','candidate','routing','merge']) {click('selection',tab);verify(doc.querySelector('.panel h2'),'Selection boundary renders');}
chapter(3);
for(let i=0;i<12;i++) {
  click('case',i);
  verify(doc.querySelectorAll('.checkbtn').length===D.cases[i].program.checks.length,'Correct case check count');
  const last=D.cases[i].program.checks.at(-1);click('check',last.id);
  verify(body().includes(last.check_ref),'Selected check identity visible');
  chapter(4);verify(body().includes(D.cases[i].interpretation.requirements.r1.explanation),'Actual interpretation rendered');
  chapter(3);
}
chapter(5);
for(const tab of ['current','local','constrained','prompt']) {click('tab',tab);verify(doc.querySelector('.panel h3'),'Calibration version renders');}
chapter(6);
for(const [kind,expected] of [['accept','Accept illustrative replacement'],['reject','Reject illustrative replacement'],['partial','Accept illustrative replacement'],['support','Insufficient evidence']]) {
  click('merge',kind);verify(body().includes(expected),'Correct synthetic merge decision');
  const f=w.CaliTreeDemo.mergeFixture(kind);verify(f.scope.length===24,'Full scope retained');
  if(kind==='partial')verify(f.residual.length===4,'Residual promotion includes four cases');
}
chapter(7);
for(let i=0;i<12;i++) {
  click('case',i);
  for(let step=0;step<5;step++) {
    click('flow',step);
    verify(doc.querySelectorAll('.grid2 > .panel')[1].textContent.includes(`${step+1} ·`),'Every case traverses each dataflow stage');
    if(step<3)verify(doc.querySelector('[data-action="reveal"]').disabled,'No premature reference revelation');
  }
}
click('flow',3);click('case',2);
verify(!body().includes('mean 1.5833'),'Reference hidden before reveal');
click('reveal');verify(body().includes('mean 1.5833'),'Reference reveal after output');
const select=doc.querySelector('#sandbox-select'),name=D.cases[2].prediction.trace[0].feature;
select.value=name;select.dispatchEvent(new w.Event('change',{bubbles:true}));
verify(body().includes('synthetic output'),'Counterfactual visibly labeled');
assert.deepEqual(JSON.parse(JSON.stringify(w.CaliTreeDemo.execute(D.cases[2].features.features))),JSON.parse(JSON.stringify(D.cases[2].prediction)));
click('play');while(tick)tick();
verify(doc.querySelectorAll('.replayrow').length===12,'Replay completes all cases');
verify(doc.querySelectorAll('.replayrow').length===D.cases.length,'Original replay denominator');
click('reset-replay');verify(!doc.querySelector('.replayrow'),'Replay resets');
chapter(8);verify(body().includes('9/12'),'Development replay result');
verify(body().includes('44/48'),'Training result separately labeled');
verify(body().includes('Not evaluated here'),'Final set not presented as evaluated');
verify(w.CaliTreeDemo.execute({...D.cases[0].features.features,meaning_available:false}).prediction===-1,'Missing meaning abstains');
const standalone=fs.readFileSync(path.join(dir,'calitree-demo.html'),'utf8');
verify(!standalone.includes('src="data.js"')&&!standalone.includes('src="app.js"')&&!standalone.includes('href="style.css"'),'Standalone embeds all code');
verify((standalone.match(/data:image\/(?:png|jpeg);base64,/g)||[]).length===24,'Standalone embeds all 24 images');
verify(!/(?:src|href)="https?:/.test(standalone),'No remote assets');
// The exact standalone file must execute too, not merely have embedded strings.
const portable = new JSDOM(standalone,{runScripts:'dangerously',beforeParse(win){win.scrollTo=()=>{};}});
verify(portable.window.document.querySelector('h1')?.textContent.includes('traceable'),'Double-click build executes');
portable.window.close();dom.window.close();
console.log(JSON.stringify({passed:true,interaction_and_data_assertions:assertions,policy_trace_parity_cases:12,new_model_calls:0}));
