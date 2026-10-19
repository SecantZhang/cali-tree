/* Test the six-case teaching model without a server or model calls. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('../../web/node_modules/jsdom');
const dir=__dirname;
const dom=new JSDOM(fs.readFileSync(path.join(dir,'six-case-index.html'),'utf8'),{runScripts:'outside-only'});
const w=dom.window;let tick=null;
w.setInterval=fn=>{tick=fn;return 1;};w.clearInterval=()=>{tick=null;};
for(const file of ['rule-tree.js','six-search.js','six-case-reference.js'])w.eval(fs.readFileSync(path.join(dir,file),'utf8'));
w.eval(fs.readFileSync(path.join(dir,'six-case.js'),'utf8'));
const doc=w.document,model=w.CaliTreeSix;
let count=0;
const verify=(condition,message)=>{assert(condition,message);count++;};
const text=()=>doc.body.textContent;
function click(action,value){const b=doc.querySelector(`button[data-action="${action}"]${value==null?'':`[data-value="${value}"]`}`);assert(b,action+' '+value);b.click();}
const step=n=>click('step',n);
function feature(key,value){const s=doc.querySelector(`[data-feature="${key}"]`);assert(s);s.value=value;s.dispatchEvent(new w.Event('change',{bubbles:true}));}
verify(model.cases.length===6,'Exactly six examples');
for(const label of ['no','partial','yes'])verify(model.cases.filter(c=>c.reference===label).length===2,'Two examples per reference');
for(let i=0;i<6;i++)for(let s=0;s<8;s++){
  step(s);click('case',i);
  verify(doc.querySelectorAll('.case').length===6,'All six cases remain visible');
  verify(!text().includes('undefined'),'No missing text');
  verify(doc.querySelector('.visual h2'),'Every case/step renders a dominant visual');
  if(s===6)verify(!doc.querySelector('[data-reference]'),'All references hidden at runtime');
}
for(const c of model.cases){
  verify(model.predict(c.facts).label===c.reference,'Frozen rule matches intended invented outcome');
  verify(model.checks(c).length===3,'Three separate evidence roles per case');
  verify(Object.isFrozen(c)&&Object.isFrozen(c.facts),'Original examples immutable');
  verify(model.predict({...c.facts,reference:'intentionally_wrong'}).label===c.reference,'Reference not consumed by inference');
}
step(4);click('candidate','any');verify(text().includes('2/3'),'Progress-only candidate fails Partial in each batch');
verify(model.score(model.cases,'any')===4,'Weak candidate 4/6');
click('candidate','endpoint');verify(model.score(model.cases,'endpoint')===4,'Endpoint-only candidate also misses Partial');
click('candidate','shared');verify(model.score(model.cases,'shared')===6,'Three-way teaching rule 6/6');
verify(text().includes('cannot certify'),'Toy support limitation explicit');
function setting(id,value){const s=doc.getElementById(id);assert(s,id);s.value=String(value);s.dispatchEvent(new w.Event('change',{bubbles:true}));}
click('grow-reset');verify(doc.querySelectorAll('.rt-node').length===1,'Construction begins with majority leaf');
verify(text().includes('1/3 fit'),'Majority leaf reveals its actual errors');
click('grow-next');verify(doc.querySelectorAll('.rt-node').length===3,'First selected split grows two child nodes');
verify(text().includes('2/3 fit'),'First split reduces errors');
click('grow-next');verify(doc.querySelectorAll('.rt-node').length===5,'Second split completes the three-leaf tree');
verify(text().includes('3/3 fit'),'Completed local fit resolves Partial');
setting('learn-support',2);verify(doc.querySelectorAll('.rt-node').length===1,'Support floor prevents unsupported local splits');
setting('learn-batch','pooled');verify(text().includes('6/6 fit'),'Pooling supplies enough source support');
setting('learn-depth',1);verify(text().includes('4/6 fit'),'Depth budget limits fitting capacity');
setting('learn-depth',2);
const pooled=w.CaliTreeSixSearch.fit(model.cases,{maxDepth:2,minSupport:2});
verify(pooled.errors===0&&pooled.nodes===5,'Actual pooled toy search yields two splits');
for(const depth of [1,2,3]){
  const result=w.CaliTreeSixSearch.fit(model.cases,{maxDepth:depth,minSupport:2});
  const ref=w.CALITREE_SIX_REFERENCE.profiles[String(depth)];
  assert.deepEqual(JSON.parse(JSON.stringify(result.tree)),JSON.parse(JSON.stringify(ref.tree)));
  verify(result.nodes===ref.nodes,'Browser/Python M2 tree node parity');
  for(let i=0;i<6;i++)verify(['no','partial','yes'].indexOf(w.CaliTreeSixSearch.predict(result.tree,model.cases[i].facts))===ref.predictions[i],'Browser/Python M2 prediction parity');
}
doc.querySelector('[data-tree-node="rF"]').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
verify(text().includes('A2, A3, B2, B3'),'Clicking a node reveals its exact source partition');
setting('learn-depth',1);click('freeze-candidate');
verify(model.getFrozen().settings.maxDepth===1,'Freeze captures the selected depth constraint');
verify(Object.isFrozen(model.getFrozen().tree),'Frozen inference tree is immutable');
const frozenBefore=JSON.stringify(model.getFrozen());
step(4);setting('learn-depth',2);
verify(JSON.stringify(model.getFrozen())===frozenBefore,'Changing the search controls does not silently change the frozen policy');
click('freeze-candidate');click('walk-all');
verify(model.getFrozen().settings.maxDepth===2,'Explicit freeze replaces the candidate for replay');
step(5);verify(text().includes('acceptance remains pending'),'No unsupported hierarchy acceptance');
verify(text().includes('Separate validation sources: 0'),'Separate validation absence explicit');
verify(doc.querySelectorAll('.source').length===6,'Parent retains full six-case lineage');
click('bad-parent');verify(text().includes('Reject this toy candidate'),'Bad parent rejected visibly');
verify(text().includes('4/6'),'Rejection preserves training misses');
step(6);click('case',0);verify(doc.querySelector('.result strong').textContent==='Yes','Frozen default A1 Yes');
feature('material','true');verify(doc.querySelector('.result strong').textContent==='Yes','Learner cannot infer a constant, unsupported materiality distinction');
click('inference-model','guard');verify(doc.querySelector('.result strong').textContent==='Partial','Authored guard is distinct from the fitted tree');
click('reset-facts');verify(doc.querySelector('.result strong').textContent==='Yes','Original facts restore');
click('case',1);feature('endpoint','unknown');verify(doc.querySelector('.result strong').textContent==='Unresolved','Endpoint uncertainty can change output');
verify(doc.querySelector('.rt-widget.uncertain'),'Unknown evidence exposes multiple admissible tree paths');
verify(!doc.querySelector('[data-reference]'),'Reference remains hidden after controls');
click('walk-reset');verify(text().includes('Decision pending'),'Stepwise inference waits for a leaf');
click('walk-next');click('walk-next');verify(doc.querySelector('.result strong').textContent==='Unresolved','Unknown evidence branches preserve both admissible outputs');
verify(model.predict({endpoint:false,progress:false,material:'unknown'}).label==='no','Irrelevant unknown does not force abstention');
verify(model.predict({endpoint:false,progress:true,material:'unknown'}).label==='partial','Invariant Partial resolves despite unknown collateral');
verify(model.predict({endpoint:true,progress:true,material:'unknown'}).label==='unresolved','Material unknown changes possible Yes/Partial');
verify(model.predict({endpoint:'unknown',progress:false,material:false}).label==='unresolved','Unknown endpoint can change No/Yes');
step(0);click('play');let ticks=0;while(tick&&ticks<10){tick();ticks++;}
verify(!tick&&ticks===7,'Autoplay reaches the final step and stops');
verify(doc.querySelectorAll('.scoretable tbody tr').length===6,'Final score retains all six cases');
click('restart');verify(doc.querySelector('h1').textContent==='Six edits. One judging problem.','Replay restarts');
click('play');click('step',2);verify(!tick,'Manual navigation stops autoplay');
const built=fs.readFileSync(path.join(dir,'six-case-demo.html'),'utf8');
verify(!built.includes('src="six-case.js"')&&!built.includes('href="six-case.css"'),'Standalone code embedded');
verify(!/(?:src|href)="https?:/.test(built),'No external resources');
const standalone=new JSDOM(built,{runScripts:'dangerously'});
verify(standalone.window.document.querySelectorAll('.case').length===6,'Standalone renders all six examples');
standalone.window.close();dom.window.close();
console.log(JSON.stringify({passed:true,teaching_model_assertions:count,synthetic_cases:6,new_model_calls:0}));
