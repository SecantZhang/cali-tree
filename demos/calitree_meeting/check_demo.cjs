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
w.eval(fs.readFileSync(path.join(dir,'rule-tree.js'),'utf8'));
w.eval(fs.readFileSync(path.join(dir,'merge-view.js'),'utf8'));
w.eval(fs.readFileSync(path.join(dir,'merge-rounds.js'),'utf8'));
w.eval(fs.readFileSync(path.join(dir,'merge-inspector.js'),'utf8'));
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
verify(D.m2.portability_audit.passed,'M2 portability audit exported');
verify(D.m2.rule_support_examples.length===14,'All fourteen reviewed rule supports exported');
verify(D.m2.equivalent_check_audit.equivalent_check_variants===515,'Exact equivalent-check audit exported');
verify(D.merge.steps.length===7&&Object.keys(D.merge.nodes).length===15,'Complete selected 8-seed / 7-merge construction exported');
verify(D.merge.training.correct===46&&D.merge.development.correct===10,'Latest recorded root results');
verify(!D.merge.m4_used&&!D.merge.selection_used_development,'No M4 router or development-based root selection');
verify(D.policy.artifact_ref===D.merge.package_manifest.policy_ref,'Runtime tree matches frozen v11 package');
verify(D.merge.semantic_warnings.length===3,'Semantic conflicts remain visible');
verify(D.merge.steps.filter(e=>e.mode==='full_grammar_repair').length===5,'Five selected repairs remain disclosed');
verify(D.merge.steps.at(-1).mode==='child_only','Final root uses inherited child predicates');
for(const c of D.cases) {
  assert.deepEqual(JSON.parse(JSON.stringify(w.CaliTreeDemo.execute(c.features.features))),JSON.parse(JSON.stringify(c.prediction)));
  assert.deepEqual(JSON.parse(JSON.stringify(w.CaliTreeDemo.execute(c.features.features,D.m2.policy))),JSON.parse(JSON.stringify(c.m2_prediction)));
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
for(const tab of ['current','m2','audit','local','constrained','prompt']) {click('tab',tab);verify(doc.querySelector('.panel h3'),'Calibration version renders');}
click('tab','audit');
verify(doc.querySelectorAll('.support-rule').length===14,'Every reviewed rule is inspectable');
verify(body().includes('147 scoped implementation tests passed'),'M2 verification scope explicit');
verify(body().includes('M2 completed'),'Completed M2 milestone visible');
click('tab','current');
verify(doc.querySelectorAll('.rt-node').length===27,'Current merged rule tree has all 27 nodes');
verify(doc.querySelectorAll('.rt-edge').length===26,'Current merged rule tree has all 26 connecting edges');
verify(!doc.querySelector('.policytree details'),'Rule tree is a branching canvas, not nested lists');
chapter(6);
const rounds=w.CaliTreeMergeRounds.model(D);
assert.deepEqual(JSON.parse(JSON.stringify(rounds.rounds.map(r=>r.count))),[8,4,2,1]);
assert.deepEqual(JSON.parse(JSON.stringify(rounds.rounds.map(r=>r.correct))),[38,44,47,46]);
const expectedSources=[...D.merge.nodes[D.merge.root].fit_sources].sort();
for(let i=0;i<4;i++){
  click('round-stage',i);
  verify(doc.querySelectorAll('.round-node.active').length===[8,4,2,1][i],'Only the current round policies are active');
  verify(doc.querySelector('.round-stage.active strong').textContent===String([8,4,2,1][i]),'Direct illustration exposes the active policy count');
  verify(doc.querySelectorAll('.round-edge.completed').length===[0,8,12,14][i],'Only completed round connections are highlighted');
  verify(rounds.rounds[i].total===48&&rounds.rounds[i].sources.length===48,'All original source denominators retained in each round');
  assert.deepEqual(JSON.parse(JSON.stringify([...rounds.rounds[i].sources].sort())),expectedSources);
  verify(!body().includes('undefined'),'Every round has complete recorded node metadata');
}
verify(body().includes('47/48')&&body().includes('19 rules to 14'),'Final round retains the measured compression tradeoff');
click('round-reset');verify(doc.querySelectorAll('.round-node.active').length===8,'Reset starts with eight policies');
click('round-next');verify(doc.querySelectorAll('.round-node.active').length===4,'Manual merge performs the first full round');
click('round-back');verify(doc.querySelectorAll('.round-node.active').length===8,'Back restores the previous frontier');
click('round-play');let roundTicks=0;while(tick&&roundTicks<5){tick();roundTicks++;}
verify(roundTicks===3&&!tick&&doc.querySelectorAll('.round-node.active').length===1,'Autoplay performs exactly three rounds and stops at one root');
click('round-play');click('round-play');verify(!tick,'Pause stops playback');
click('round-play');chapter(1);verify(!tick,'Leaving the merging chapter stops round playback');chapter(6);
click('round-stage',3);
const firstSeed=rounds.levels[0][0];
doc.querySelector(`[data-round-node="${firstSeed.node_id}"]`).dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
verify(doc.querySelectorAll('.round-node.active').length===8,'Clicking a previous policy opens its actual round');
verify(doc.querySelector('.mi-dialog'),'Round cell opens the before / after inspector directly');
click('mi-close');
// Frozen-artifact comparisons: all original cohort decisions, not oracle child selection.
for(const step of D.merge.steps){
  const parent=D.merge.nodes[step.node_id];
  verify(step.comparisons.length===parent.fit_sources.length,'No original slot dropped from the comparison');
  for(const r of step.comparisons){
    const row=D.merge.training_examples.find(e=>e.case===r.case),own=D.merge.nodes[r.owner];
    verify(own.fit_sources.includes(row.source_group),'Before prediction uses original owning child');
    assert.deepEqual(JSON.parse(JSON.stringify(w.CaliTreeDemo.execute(row.features,own.runtime))),JSON.parse(JSON.stringify(r.before)));
    assert.deepEqual(JSON.parse(JSON.stringify(w.CaliTreeDemo.execute(row.features,parent.runtime))),JSON.parse(JSON.stringify(r.after)));
    for(const child of step.children){
      assert.deepEqual(JSON.parse(JSON.stringify(w.CaliTreeDemo.execute(row.features,D.merge.nodes[child].runtime))),JSON.parse(JSON.stringify(r.children[child])));
    }
  }
}
for(const n of Object.values(D.merge.nodes)){
  click('round-stage',n.height);
  doc.querySelector(`[data-round-node="${n.node_id}"]`).dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  const dialog=doc.querySelector('.mi-dialog'),c=w.CaliTreeMergeInspector.context(D,n.node_id);
  verify(!!dialog&&doc.querySelector('.shell').inert,'Every recorded seed and parent opens an accessible modal');
  verify(doc.activeElement.dataset.action==='mi-close','New dialog receives keyboard focus');
  verify(doc.querySelectorAll('.mi-tree-card').length===3,'Original two child trees and merged tree shown');
  verify(dialog.textContent.includes(c.parent.name)&&!dialog.textContent.includes('undefined'),'Every inspector renders complete metadata');
  verify(!n.children.length?dialog.textContent.includes('pre-fit seed tree was not recorded'):true,'Seed history distinguishes first outgoing merge');
  for(const policy of [...c.children,c.parent]){
    verify(doc.querySelector(`[data-mi-policy="${policy.node_id}"]`).querySelectorAll('.rt-node').length===policy.complexity.nodes,'Every displayed tree matches frozen policy complexity');
  }
  click('mi-trace',0);verify(!dialog.isConnected&&doc.querySelectorAll('.mi-tree-card .rt-edge.on').length===0,'Start-at-root resets all three paths');
  click('mi-trace',1);verify(doc.querySelectorAll('.mi-tree-card .rt-edge.on').length===[...c.children,c.parent].filter(p=>p.runtime.tree.feature).length,'Step evaluates one predicate in each nonconstant tree');
  click('mi-trace','all');
  const selected=doc.querySelector('#mi-case').value,row=c.rows.find(r=>r.case===selected);
  verify(doc.querySelectorAll('.mi-tree-card .rt-edge.on').length===row.after.trace.length+Object.values(row.children).reduce((a,p)=>a+p.trace.length,0),'All highlighted paths match exact saved traces');
  click('mi-view',c.parent.node_id);verify(doc.querySelectorAll('.mi-tree-card').length===1,'Expand isolates a readable parent tree');
  click('mi-view','all');
  click('mi-tab','changes');verify(doc.querySelectorAll('.mi-comparisons tbody tr').length===c.rows.length,'All original sources visible in comparison table');
  click('mi-filter','regressed');verify(doc.querySelectorAll('.mi-comparisons tbody tr').length===c.rows.filter(r=>r.status==='regressed').length,'Lost-correctness filter is exact');
  click('mi-tab','rules');verify(doc.querySelectorAll('.mi-rule').length===[...c.children,c.parent].reduce((a,n)=>a+n.rules.length,0),'All terminal clauses and supports displayed');
  click('mi-tab','gates');verify(!doc.querySelector('.mi-dialog .gate.fail'),'Exact saved parent gates pass in inspector');
  click('mi-tab','evidence');verify(!doc.querySelector('.mi-dialog').textContent.includes('undefined'),'Cached evidence view has no missing-field string');
  click('mi-tab','artifacts');verify(doc.querySelector('.mi-dialog').textContent.includes(c.parent.runtime.artifact_ref),'Raw artifact retains full policy identity');
  doc.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  verify(!doc.querySelector('.mi-dialog')&&!doc.body.classList.contains('merge-inspector-open'),'Escape closes modal and releases scroll');
  verify(doc.activeElement.dataset.roundNode===n.node_id,'Closing restores focus to the clicked cell');
}
click('round-stage',3);click('mi-open',D.merge.root);
click('mi-tab','changes');click('mi-filter','regressed');
verify(doc.querySelectorAll('.mi-comparisons tbody tr').length===1,'Final 47→46 merge has exactly one lost case');
click('mi-filter','all');click('mi-case','G3C05');click('mi-tab','trees');
verify(!doc.querySelector('.mi-dialog .rt-edge.on')&&doc.querySelector('.mi-dialog').textContent.includes('Unresolved'),'Missing observation does not invent a tree path');
click('mi-tab','evidence');verify(doc.querySelector('.mi-dialog').textContent.includes('retained in full denominator'),'Missing source retained and explained');
click('mi-open',rounds.levels[0][1].node_id);verify(doc.querySelector('.mi-dialog').textContent.includes('Selected seed'),'Inspector can navigate directly between recorded cells');
click('mi-close');
click('round-reset');click('round-play');
const playbackSeed=rounds.levels[0][0].node_id;
doc.querySelector(`[data-round-node="${playbackSeed}"]`).dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
verify(!tick,'Opening merge details stops autoplay');
const last=doc.querySelector('.mi-dialog [data-mi-policy]:last-child [data-tree-action="select"]');last.focus();
const close=doc.querySelector('[data-action="mi-close"]');close.focus();
close.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true,cancelable:true}));
verify(doc.querySelector('.mi-dialog').contains(doc.activeElement),'Keyboard focus remains within inspector');
click('mi-close');

click('round-stage',3);click('round-policy',D.merge.root);
verify(doc.querySelectorAll('.rt-node').length===27,'Round player opens the actual selected root policy');
click('merge-tab','history');click('merge-graph','lineage');
verify(doc.querySelectorAll('.rt-node').length===15,'Training lineage is a distinct 15-node tree');
verify(doc.querySelectorAll('.rt-edge').length===14,'Training lineage has fourteen child links');
verify(!body().includes('Illustrative teaching fixtures'),'Synthetic merge results replaced by recorded history');
click('merge-step',0);verify(doc.querySelectorAll('.rt-node.on').length===8,'Construction begins with eight six-source seeds');
for(const e of D.merge.steps){
  click('merge-step',e.step);
  verify(!doc.querySelector('.gate.fail'),'Every selected merge passes its actual recorded gates');
  verify(!body().includes('undefined'),'Every recorded step has complete provenance');
  const n=D.merge.nodes[e.node_id],sources=new Set(n.fit_sources),union=new Set(e.children.flatMap(id=>D.merge.nodes[id].fit_sources));
  assert.deepEqual([...sources].sort(),[...union].sort());
  verify(sources.size===e.sources,'Every parent retains the exact deduplicated descendant union');
  verify(e.decision.child_retention.every(r=>r.after.correct>=r.before.correct-r.max_additional_errors),'Each child loss stays inside the declared allowance');
}
verify(body().includes('19 to 14'),'Final-root rule compression explicit');
click('merge-graph','policy');verify(doc.querySelectorAll('.rt-node').length===27,'Selected parent opens its real executable policy tree');
click('merge-tab','algorithm');verify(body().includes('four')&&body().includes('M4'),'Bounded repair and skipped routing explained');
click('merge-tab','limits');verify(body().includes('G3C12')&&body().includes('historical'),'Semantic conflicts and development exposure retained');
chapter(7);
click('flow',3);click('case',0);
verify(doc.querySelector('.result strong').textContent==='Partial','V11 replay is the default');
click('inference-policy','m2');
verify(doc.querySelector('.result strong').textContent==='No','Earlier M2 remains an independent replay comparison');
click('inference-policy','merged');
for(let i=0;i<12;i++) {
  click('case',i);
  for(let step=0;step<5;step++) {
    click('flow',step);
    verify(doc.querySelectorAll('.grid2 > .panel')[1].textContent.includes(`${step+1} ·`),'Every case traverses each dataflow stage');
    if(step<3)verify(doc.querySelector('[data-action="reveal"]').disabled,'No premature reference revelation');
  }
}
click('flow',3);click('case',2);
for(let i=0;i<12;i++){
  click('case',i);
  verify(doc.querySelectorAll('.rt-edge.on').length===D.cases[i].prediction.trace.length,'Graph route matches every original saved case trace');
}
click('case',2);
click('tree-reset');verify(body().includes('Decision pending'),'Traversal waits before evaluating predicates');
verify(doc.querySelectorAll('.rt-edge.on').length===0,'No branches traversed at root');
for(let i=0;i<D.cases[2].prediction.trace.length;i++)click('tree-next');
verify(doc.querySelectorAll('.rt-edge.on').length===D.cases[2].prediction.trace.length,'Exactly the saved route is highlighted');
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
verify(body().includes('10/12'),'New merged-root development score');
verify(body().includes('46/48'),'New merged-root training score');
verify(body().includes('44/48'),'Training result separately labeled');
verify(body().includes('Not evaluated here'),'Final set not presented as evaluated');
verify(w.CaliTreeDemo.execute({...D.cases[0].features.features,meaning_available:false}).prediction===-1,'Missing meaning abstains');
const standalone=fs.readFileSync(path.join(dir,'calitree-demo.html'),'utf8');
verify(!standalone.includes('src="data.js"')&&!standalone.includes('src="app.js"')&&!standalone.includes('href="style.css"'),'Standalone embeds all code');
verify(!standalone.includes('src="rule-tree.js"')&&!standalone.includes('href="rule-tree.css"'),'Standalone embeds the tree renderer');
verify(!standalone.includes('src="merge-view.js"'),'Standalone embeds recorded-merge rendering');
verify(!standalone.includes('src="merge-rounds.js"'),'Standalone embeds the direct round illustration');
verify(!standalone.includes('src="merge-inspector.js"'),'Standalone embeds rich cell inspector');
verify((standalone.match(/data:image\/(?:png|jpeg);base64,/g)||[]).length===24,'Standalone embeds all 24 images');
verify(!/(?:src|href)="https?:/.test(standalone),'No remote assets');
// The exact standalone file must execute too, not merely have embedded strings.
const portable = new JSDOM(standalone,{runScripts:'dangerously',beforeParse(win){win.scrollTo=()=>{};}});
verify(portable.window.document.querySelector('h1')?.textContent.includes('traceable'),'Double-click build executes');
portable.window.close();dom.window.close();
const direct=new JSDOM(standalone,{runScripts:'dangerously',url:'http://localhost/#merging',beforeParse(win){win.scrollTo=()=>{};}});
verify(direct.window.document.querySelectorAll('.round-node.active').length===8,'Direct #merging entry opens the eight-policy illustration');
direct.window.close();
console.log(JSON.stringify({passed:true,interaction_and_data_assertions:assertions,policy_trace_parity_cases:12,new_model_calls:0}));
