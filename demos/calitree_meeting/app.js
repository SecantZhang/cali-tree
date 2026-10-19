/* Offline presentation. All empirical records are immutable exports in data.js.
 * Merge history is replayed from v11 artifacts; counterfactual probes remain explicitly synthetic. */
(() => {
'use strict';
const D = window.CALITREE_DATA;
const app = document.getElementById('app');
const labels = ['no', 'partial', 'yes'];
const stages = ['System map', 'Inputs & labels', 'Selection policies', 'Decision check sets', 'Evidence & meaning', 'Batch calibration', 'Recorded merging', 'Frozen inference', 'Results & boundaries'];
const subtitles = ['From an edited image to a traceable judgment', 'One edit, three inputs, one reference', 'Selection happens at several different boundaries', 'Make the instruction physically testable', 'Observe first. Interpret relative to the request.', 'Learn a reusable rule, then freeze it', 'Eight groups become one reusable root', 'Follow the twelve cases through the saved policy', 'Separate what works from what is still a hypothesis'];
const notes = [
  'The current research path keeps the M1 evidence and M2 vocabulary, then learns one root through seven accepted exact-union merges. Training constructs a hierarchy; inference executes a single rule tree with no M4 router.',
  'These are twelve real development sources, four per reference class. The AURORA reference is a released mean binned at 0.5 and 1.5. It is not an individual check annotation. Training sources are separate, but these cases have historical exposure.',
  'Distinguish grouping, pair ranking, complete-root selection, and inference. Semantic groups use cached label-blind evidence; fitting uses original references. Root selection is training-only and prefers qualified child-predicate reuse. M4 is absent.',
  'Concrete questions bind the instruction to the actual target. Every question retains role, desired polarity, dependencies, and content identity. These case-specific bindings are separate from portable rule conditions.',
  'The observer answers exact physical questions, then a text-only pass interprets the cached evidence relative to the request. Neither sees dataset references. Hashes protect attachment, not visual or semantic truth.',
  'The current root fits 46/48 with fourteen terminal rules and eleven predicates. Keep the earlier reviewed M2 policy visible as a 44/48 baseline. Both are local fitting measurements; the selected root uses only predicates available from its two children.',
  'M5 ranks pairs from condition/operation overlap and mutual transfer. M6 relearns on all original descendant sources and checks strict above-90% fit plus child retention. M7 searches bounded balanced unions. Five selected merges need full-grammar repair; final-root reuse is child-only.',
  'New cases do not traverse the training merge history. They use the same three upstream model stages and execute one saved root. The default replay is v11; switch to reviewed M2 to compare exact paths. H01 and H07 remain No-reference cases predicted Partial by v11.',
  'The selected root gets 46/48 locally and 10/12 on historically exposed development. It compresses nineteen child rules into fourteen at the final merge, losing one correct answer within the allowed budget. Three training Yes cases still have unresolved meaning-versus-policy conflicts. Final evaluation and broader robustness remain separate.'
];
const state = {stage: 0, caseIndex: 0, check: null, notes: true, revealed: false, tab: 'current', selection: 'candidate', merge: 'accept', replay: 0, playing: false, sandbox: null, flowStep: 3, treeNodes: {}, treeStep: null, mergeStep: 7, mergeTab: 'rounds', mergeRound: 0, roundSelected: null, roundPlaying: false, mergeGraph: 'lineage', inferencePolicy: 'merged', mergeInspector: null};
let timer = null;
let roundTimer = null;
let inspectorReturn = null;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const title = s => String(s).replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
const label = n => n < 0 ? 'unresolved' : labels[n];
const badge = (s, cls='') => `<span class="tag ${esc(cls)}">${esc(s)}</span>`;
const outcome = n => badge(title(typeof n === 'number' ? label(n) : n),typeof n === 'number' ? label(n) : n);
const pct = n => (n*100).toFixed(1)+'%';
const current = () => D.cases[state.caseIndex];
const btn = (text, action, value, cls='') => `<button class="${cls}" data-action="${action}" ${value == null ? '' : `data-value="${esc(value)}"`}>${text}</button>`;
const tabs = (items, action, selected) => `<div class="tabs" role="group">${items.map(([id,name])=>btn(esc(name),action,id,id===selected?'active':'')).join('')}</div>`;
const io = (input, output) => `<div class="io"><div><label>Input</label>${input}</div><span class="arrow">→</span><div><label>Output</label>${output}</div></div>`;
const details = (name,obj) => `<details><summary>${esc(name)}</summary><pre>${esc(JSON.stringify(obj,null,2))}</pre></details>`;
function casebar() {return `<div class="casebar"><span class="case-label">Follow a case</span>${D.cases.map((c,i)=>btn(c.case,'case',i,i===state.caseIndex?'active':'')).join('')}</div>`;}
function pair(c, compact=false) {return `<div class="pair">${[['source_image','SOURCE · original'],['edited_image','EDITED · model output']].map(([key,text])=>`<figure><img src="${esc(c.images[key])}" alt="${esc(c.case+' '+text+' for '+c.instruction)}" ${compact?'style="height:170px"':''}><figcaption>${text}</figcaption></figure>`).join('')}</div>`;}
function facts(c) {return c.features.features;}
function currentPolicy(){return state.inferencePolicy==='m2'?D.m2.policy:D.policy;}
function predicted(c){return state.inferencePolicy==='m2'?c.m2_prediction:c.prediction;}
function execute(features,policy=currentPolicy()) {
  if(!features) return {prediction:-1, trace:[],reason:'missing_evidence'};
  if(!features.meaning_available) return {prediction:-1, trace:[],reason:'missing_semantic_interpretation'};
  let node=policy.tree; const trace=[];
  while(node.feature) {const value=features[node.feature];trace.push({feature:node.feature,value});node=node[value?'true':'false'];}
  return {prediction:node.prediction,trace,reason:'portable_semantic_rule'};
}
function metrics(pred, refs) {
  const per=labels.map((_,k)=>{const support=refs.filter(y=>y===k).length, predicted=pred.filter(y=>y===k).length,correct=pred.filter((p,i)=>p===k&&refs[i]===k).length;return {support,predicted,correct,recall:support?correct/support:0,f1:support+predicted?2*correct/(support+predicted):0};});
  const correct=pred.filter((p,i)=>p===refs[i]).length;
  return {correct,total:refs.length,accuracy:correct/refs.length,macro_f1:per.reduce((s,c)=>s+c.f1,0)/3,unresolved:pred.filter(p=>p<0).length,per};
}
function stats(items) {return `<div class="stats">${items.map(([v,l])=>`<div class="stat"><strong>${v}</strong><span>${l}</span></div>`).join('')}</div>`;}
function overview() {
  const cards=[['01','▧','Case input','Instruction + SOURCE + EDITED',1],['02','⌘','Bound checks','Instruction → exact physical questions',3],['03','◉','Evidence','One visual observation of the pair',4],['04','≋','Meaning','Text-only, instruction-relative facts',4],['05','⑂','Frozen policy','Reusable deterministic rule execution',7]];
  return `<div class="panel merge-direct-cta"><div><div class="eyebrow">Interactive merging illustration</div><h2>8 policies → 4 → 2 → 1</h2><p class="small muted">Replay the actual selected merges, one balanced round at a time. All 48 original sources stay in the construction.</p></div>${btn('Open 8 → 4 → 2 → 1','open-merge-rounds',null,'primary')}</div><div class="panel dark"><div class="eyebrow" style="color:#acc9b1">The research question</div><h2 style="font-size:27px;margin:10px 0">Can a judge learn what humans mean by<br>“the requested edit was satisfied”?</h2><p class="muted" style="max-width:750px;font-size:13px">CaliTree turns local calibration examples into explicit evaluation policies. Each judgment can be traced back to the instruction, physical evidence, and a frozen rule.</p>${stats([['12','real development cases'],['90','bound physical questions'],['0','new model calls in this demo']])}</div>
  <div class="pipeline">${cards.map((c,i)=>(i?'<span class="arrow">→</span>':'')+`<button class="flowcard" data-action="stage" data-value="${c[4]}"><span class="flowindex">${c[0]} / INFERENCE</span><span class="flowicon">${c[1]}</span><strong>${c[2]}</strong><p>${c[3]}</p>${badge('Implemented')}</button>`).join('')}</div>
  <div class="grid2"><div class="panel"><div class="row"><h3>Training path</h3>${badge('Implemented')}</div><p class="small muted">48 fixed training sources → 8 label-blind semantic seeds → 7 accepted union merges → one frozen v11 policy.</p><div class="tokens">${['8 × 6','4 × 12','2 × 24','1 × 48'].map(x=>`<span class="token">${x}</span>`).join('')}<span class="token">reuse-first root · 46/48 local fit</span></div></div><div class="panel"><div class="row"><h3>Recorded reuse-first merging</h3>${badge('Implemented · M5–M7')}</div><p class="small muted">Rank pairs → reuse or refine child predicates → fit full descendant unions → enforce retention → select a complete root. M4 is skipped.</p>${btn('Illustrate 8 → 4 → 2 → 1','open-merge-rounds',null,'primary small')}</div></div>
  <div class="callout">Two different trees: the <b>training lineage</b> records which policies were pooled; the <b>deployed rule tree</b> tests evidence predicates. The v11 judge executes only the final root, without training membership, a specialist router, or child votes.</div>`;
}
function dataset() {
  const c=current();
  return `${casebar()}<div class="grid2"><section class="panel"><div class="row"><h3>${c.case} · Benchmark example</h3>${badge('Recorded data')}</div><p class="case-title">“${esc(c.instruction)}”</p>${pair(c)}${btn('Enlarge images','images',null,'small ghost')}</section>
  <section class="panel"><h3>What enters and leaves the system?</h3><dl class="kv"><dt>Task input x</dt><dd>Instruction + source image + edited image</dd><dt>Generator output</dt><dd>The edited image, already produced by an editing model</dd><dt>Judge output ŷ</dt><dd>No / Partial / Yes, or Unresolved + evidence/rule trace</dd><dt>Reference y</dt><dd>${outcome(c.reference)} · released mean ${c.human_score.toFixed(4)} / 2</dd><dt>Reference use</dt><dd>Supervised fitting on training; scoring on development. Hidden from compilation, observation, interpretation, and runtime rule execution.</dd></dl><div class="numberline"><div><b>No</b><br>mean &lt; 0.5</div><div><b>Partial</b><br>0.5 ≤ mean &lt; 1.5</div><div><b>Yes</b><br>mean ≥ 1.5</div></div><p class="small muted">Released aggregate means, not individual votes. “Unresolved” is a system abstention, not a fourth reference label.</p>${details('Inspect case identity & reference',{case:c.case,source_group:c.source_group,human_score:c.human_score,reference:c.reference,image_hashes:c.image_hashes})}</section></div>
  <section class="panel" style="margin-top:18px"><h3>The study split</h3><div class="splitstrip"><div><strong>48</strong>Training<span>4 original batches × 12 sources</span></div><div><strong>12</strong>Development<span>These examples · 4 per class</span></div><div><strong>50</strong>Reserved final<span>Excluded from this demo</span></div></div><p class="small muted">Source-disjoint across study partitions. The 12 have historical research exposure. The final reservation is study-relative; historical exposure is disclosed in the M0 report.</p></section>
  <h3>The complete twelve-case set</h3><div class="casegrid">${D.cases.map((x,i)=>`<button class="casecard ${i===state.caseIndex?'active':''}" data-action="case" data-value="${i}"><img src="${esc(x.images.edited_image)}" alt="${esc(x.case+' edited image')}" loading="lazy"><strong>${x.case}</strong><div class="instruction">${esc(x.instruction)}</div>${outcome(x.reference)}</button>`).join('')}</div>`;
}
function selection() {
  const which=state.selection;
  const content={
    data:`${badge('Recorded protocol')}<h2 style="margin-top:14px">Select cases by source, not by output row</h2><div class="flowlane"><div class="nodebox"><strong>Source identities</strong><span class="muted">Decoded pixels + dataset lineage</span></div><span class="arrow">→</span><div class="nodebox"><strong>Fixed partitions</strong><span class="muted">48 training / 12 development / 50 reserved</span></div><span class="arrow">→</span><div class="nodebox"><strong>Balanced dev slice</strong><span class="muted">4 No + 4 Partial + 4 Yes</span></div></div><p class="small">A source group remains in one partition even when it has multiple editor outputs or file encodings. Keep extraction failures and missing records in the original denominator.</p><div class="callout">Labels can stratify the dataset at design time. They cannot route a new case or decide which evidence to observe at runtime.</div>`,
    candidate:`${badge('Implemented v11')}<h2 style="margin-top:14px">Select a complete, reusable root</h2><ol class="small"><li>Only roots covering the full original 48-source union can be exported.</li><li>All selected parents must pass strict above-90% union fit, source/instruction support, class and immediate-child retention gates.</li><li>Prefer child-only predicate reuse, then bounded refinement, then disclosed full-grammar repair.</li><li>Within a reuse category, rank accuracy, macro-F1, worst-class recall, complexity, and stable identity.</li><li>Freeze the selection before scoring the twelve development cases.</li></ol><div class="callout">The selected child-only root scores <b>46/48</b>. A higher-fitting 47/48 full-grammar alternative exists; the training-only selection favors qualified reuse. No development label chooses the root.</div><table><thead><tr><th>Retained root</th><th>Training</th><th>Reuse kind</th></tr></thead><tbody>${D.merge.runs.semantic8_reuse.retained_root_candidates.map(r=>`<tr class="${r.node_id===D.merge.root?'selected':''}"><td>${r.node_id===D.merge.root?'Selected root':'Alternative root'}</td><td>${r.training.correct}/48</td><td>${esc(title(r.reuse_kind))}</td></tr>`).join('')}</tbody></table>`,
    routing:`${badge('M4 deliberately skipped')}<h2 style="margin-top:14px">Inference uses one frozen policy</h2><div class="flowlane"><div class="nodebox"><strong>Current evidence</strong>Instruction-bound physical and semantic facts</div><span class="arrow">→</span><div class="nodebox"><strong>One v11 root</strong>Deterministic predicate tests</div><span class="arrow">→</span><div class="nodebox"><strong>Verdict + trace</strong>No / Partial / Yes / Unresolved</div></div><div class="callout">The eight initial groups and seven merges are training history. No group identity, source membership, specialist scope, or child vote is available to the exported decision logic.</div><p class="small muted">The earlier v9 routed experiment retained M2 after all thirteen merge proposals were rejected. That separate study exposed broad-scope routing regressions. The current v11 union experiment removes that stage.</p>`,
    merge:`${badge('Recorded M5 implementation')}<h2 style="margin-top:14px">Select promising child pairs</h2><p class="small">Score each pair using predicate overlap, operation overlap, and mean mutual-transfer macro-F1 on the two child fitting cohorts. Record shared mistakes separately. Similarity ranks proposals; the M6 union and retention gates determine acceptance.</p><p class="small">M7 searches balanced binary unions, retains up to two policy alternatives per union, and respects the declared depth-three / 1,536-pair budget. The selected semantic-eight lineage has seven merges.</p>${btn('Inspect proposal scores and parent learning →','open-merging-algorithm',null,'small')}`
  };
  return `${tabs([['data','Dataset sampling'],['candidate','Candidate policy'],['routing','Inference routing'],['merge','Merge proposals']],'selection',which)}<section class="panel">${content[which]}</section>${io('Allowed selection inputs depend on the boundary','Frozen manifest, policy, route, or candidate pair + provenance')}`;
}
function candidateTable() {
  return `<div class="tablewrap"><table><thead><tr><th>Search profile</th><th>Local correct</th><th>Nodes</th><th>&gt;90%?</th><th>Selection</th></tr></thead><tbody>${Object.entries(D.candidates).map(([k,v])=>`<tr class="${k===D.selected_profile?'selected':''}"><td class="mono">${esc(k)}</td><td>${v.metrics.correct}/48</td><td>${v.nodes}</td><td>${v.eligible?'Qualifies':'Below floor'}</td><td>${k===D.selected_profile?'Selected before review':'Retained comparison'}</td></tr>`).join('')}</tbody></table></div>`;
}
function checks() {
  const c=current(),list=c.program.checks,selected=list.find(k=>k.id===state.check)||list[0];
  return `${casebar()}<p class="case-title">${c.case} · ${esc(c.instruction)}</p>${io('Instruction only; no images, labels, or prior verdicts',`${list.length} bound questions + requirement/dependency graph`)}
  <div class="check-layout"><section class="panel"><h3>The decision check set</h3><p class="small muted">Click a question to inspect its exact contract.</p><div class="checklist">${list.map(k=>`<button class="checkbtn ${k.id===selected.id?'active':''}" data-action="check" data-value="${esc(k.id)}">${badge(title(k.role),'unknown')} <code>${esc(k.id)}</code><span class="checkquestion">${esc(k.question)}</span></button>`).join('')}</div></section>
  <section class="panel"><div class="row"><h3>Question · ${esc(selected.id)}</h3>${badge('Bound artifact')}</div><p style="font-size:18px">${esc(selected.question)}</p><dl class="kv">${[['Instruction span',selected.source_quote],['Role / kind',title(selected.role)+' / '+title(selected.kind)],['Target',selected.target],['Reference',selected.reference],['Applicability',selected.applicability_condition],['Expected answer',selected.expected_state],['Dependencies',selected.dependencies.join(', ')||'None'],['Absence polarity',selected.absence_when],['Source anchor',selected.absence_source_anchor],['Question SHA-256',`<code>${esc(selected.check_ref)}</code>`]].map(([k,v])=>`<dt>${k}</dt><dd>${k==='Question SHA-256'?v:esc(v)}</dd>`).join('')}</dl><div class="callout">A <b>case-specific physical question</b> can name an object. The <b>learned policy</b> cannot use that object name, exact instruction, source ID, or image hash as its decision condition.</div>${details('All requirements & authorized changes',{requirements:c.program.requirements,contract:c.program.contract})}</section></div>
  <section class="panel" style="margin-top:18px"><h3>Six roles prevent different facts from collapsing together</h3><div class="tablewrap"><table><tbody>${[['outcome','The requested physical endpoint'],['identity','Original-instance correspondence when the task needs it'],['preservation','Expected continuity; does not count as affirmative progress'],['intermediate','A concrete configuration toward a linked requested endpoint'],['collateral_disappearance','An unrelated source entity disappearing'],['collateral_deformation','An unrelated structure, size, shape, or topology changing']].map(([k,v])=>`<tr><td>${badge(title(k),'unknown')}</td><td>${v}</td></tr>`).join('')}</tbody></table></div><p class="small muted" style="margin-top:10px">Required Not Applicable becomes an applicability diagnostic with an unknown effective state. Absence requires source anchoring and adequate edited coverage when an original object must be identified.</p></section>`;
}
function evidence() {
  const c=current(),entries=Object.values(c.record.checks),k=entries.find(x=>x.id===state.check)||entries.find(x=>x.role==='outcome')||entries[0];
  const obs=k.observation;
  return `${casebar()}<p class="case-title">${c.case} · ${esc(c.instruction)}</p>${io('Bound program + ordered SOURCE / EDITED pair','Raw/effective physical states → text-only semantic interpretation')}
  <div class="grid2"><section class="panel">${pair(c,true)}<h3 style="margin-top:15px">Recorded physical answers</h3><div class="tablewrap"><table><thead><tr><th>Question</th><th>Raw</th><th>Effective</th><th>Expected</th></tr></thead><tbody>${entries.map(x=>`<tr class="${x.id===k.id?'selected':''}"><td>${btn(esc(x.id),'check',x.id)}<br><span class="small muted">${title(x.role)}</span></td><td>${esc(x.asserted_state)}</td><td>${esc(x.state)}</td><td>${esc(x.expected_state)}</td></tr>`).join('')}</tbody></table></div></section>
  <section class="panel"><div class="row"><h3>${esc(k.id)} · evidence</h3>${badge('Cached model observation')}</div><p class="small">${esc(k.question)}</p><div class="evidencebox"><b>Source</b>${esc(obs.source_evidence)}</div><div class="evidencebox"><b>Edited</b>${esc(obs.edited_evidence)}</div><div class="evidencebox"><b>Comparison</b>${esc(obs.comparison)}</div><dl class="kv"><dt>Anchor / coverage</dt><dd>${esc(obs.source_anchor)} / ${esc(obs.edited_coverage)}</dd><dt>Diagnostics</dt><dd>${esc(k.diagnostics.join('; ')||'No normalization diagnostics for this check')}</dd></dl><div class="callout">Physical <code>true / false / unknown / not_applicable</code> are distinct from satisfaction <b>No / Partial / Yes</b>. A collateral check expecting false is satisfied by false.</div></section></div>
  <section class="panel" style="margin-top:18px"><div class="row"><h3>Instruction-relative interpretation</h3>${badge('Cached text-only model pass')}</div><p class="small muted">Receives the instruction and cached physical record. No images, dataset references, or earlier satisfaction verdicts.</p>${Object.entries(c.interpretation.requirements).map(([id,r])=>`<div class="evidencebox"><b>Requirement ${esc(id)}</b><div class="tokens">${['progress','endpoint_gap','retention_need','identity_materiality','collateral_materiality','evidence_consistency'].map(f=>`<span class="token">${title(f)}: ${esc(r[f].replaceAll('_',' '))}</span>`).join('')}</div><p style="margin:14px 0 0">${esc(r.explanation)}</p></div>`).join('')}<div class="callout amber">Model-produced facts can be wrong or disputed. H03’s mug contour, for example, is a recorded materiality dispute. Matching hashes prove attachment to a question and image pair; they do not prove visual truth.</div>${details('Inspect normalized features & diagnostics',{features:c.record.features,diagnostics:c.record.diagnostics})}</section>`;
}
function calibration() {
  const t=state.tab,baseline=t==='m2';
  const controls=tabs([['current','Current merged root'],['m2','Earlier reviewed M2'],['audit','M2 verification & support'],['local','Historical local batches'],['constrained','Earlier local learner'],['prompt','Prompt-tree optimization']],'tab',t);
  const policy=baseline?D.m2.policy:D.policy;
  const graph=`<section class="panel"><div class="row"><h3>${baseline?'Earlier M2 · 44/48 locally':'Merged root v11 · 46/48 locally'}</h3>${badge('Exact saved policy')}</div><p class="small muted">Choose a development case to illuminate its path. Short labels abbreviate the exact predicate descriptions in the inspector. Counts refer to these twelve development records, not training support.</p>${casebar()}${fullTree(baseline?'m2-policy':'full-policy',facts(current()),Infinity,policy)}${baseline?`<details><summary>Earlier M2 candidate-selection table</summary>${candidateTable()}</details>`:'<div class="callout">This is the final root only. The training lineage is available in Recorded merging; inference performs no M4 routing or per-merge model call.</div>'}</section>`;
  const content=t==='current'?window.CaliTreeMergeView.summary(D)+graph:t==='m2'?m2Summary()+graph:t==='audit'?m2Summary()+m2Audit():t==='local'?localBatches():t==='prompt'?promptOptimization():constrained();
  return controls+content;
}
function promptOptimization() {
  return `<section class="panel"><div class="row"><h3>Optimize → decompose → check → aggregate → validate</h3>${badge('Implemented modular path','historical')}</div><p class="small">The prompt-tree implementation learns rubric prompts. This is a different fitting mechanism from v8’s portable semantic rule search.</p>${io('Seed rubric + selected leaf fit cases + fit references','Measured optimized prompt + compiled policy + decision sets + validation artifact')}<div class="grid2"><div><h3>Optimizer plans</h3><table><tbody>${[['TextGrad','Textual-gradient feedback and bounded prompt updates'],['GEPA','Reflective candidate search through an isolated worker'],['Sequential plans','TextGrad → GEPA or GEPA → TextGrad'],['Best of both','Independent proposals from the same seed'],['Evaluate only','Retain and measure the supplied prompt']].map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('')}</tbody></table><div class="callout">Retain the seed. Select by fit <b>balanced accuracy</b>, then raw accuracy, then earlier candidate. The current v8 selection policy instead uses its local-accuracy floor and support/complexity ordering.</div></div><div><h3>Two-way decomposition</h3><div class="nodebox"><strong>Rubric → policy</strong>Compile the selected evaluation rubric separately from the instruction.</div><div class="nodebox" style="margin-top:10px"><strong>Instruction → check plan</strong>Bind what must be inspected in this case.</div><div class="nodebox" style="margin-top:10px"><strong>Evidence + policy → verdict</strong>Structured two_way executes a bounded policy DSL. two_way_vision uses semantic model aggregation over observed conditions; it is not the deterministic DSL.</div><p class="small muted" style="margin-top:12px">Fit labels may inform optimization. Reserved-validation and final-test labels do not enter optimizer/reflection calls. Judge usage and optimizer completion-token budgets are recorded separately.</p></div></div></section><section class="panel"><h3>Inspectable stage artifacts</h3><div class="tokens">${['optimization','compilation','instruction_decomposition','evidence_checks','aggregation','validation'].map(s=>`<span class="token">${s}</span>`).join('')}</div><p class="small" style="margin-top:15px">The canvas can run through a stage, freeze a completed immutable artifact, or rerun from a boundary. Prompt, strategy, model/template identity, instruction, question, image-byte and target bindings prevent an incompatible pin from silently executing. Recomputing metrics uses saved predictions with zero model calls.</p><p class="small muted">Leaf/merge artifacts preserve scope IDs, served IDs, correct IDs, ancestor lineage, policy hashes, plans, observations, predictions, budgets, and acceptance history. A successfully merged node does not automatically become the global fallback.</p></section>`;
}
function m2Summary() {
  const a=D.m2.portability_audit;
  return `<section class="panel"><div class="row"><div><h3>M2 completed · reviewed portable semantic rules</h3><p class="small muted">Completion confirmed in “CaliTree Dataset Preparation”; implementation <code>${esc(D.m2.implementation_ref.slice(0,8))}</code>.</p></div>${badge('Implemented & verified')}</div><div class="tokens">${['M0 · study contract frozen','M1 · bound evidence implemented','M2 · portability objective met','M4 · skipped; M5–M7 · implemented'].map((s,i)=>`<span class="token ${i===3?'residual':''}">${s}</span>`).join('')}</div>${stats([[`${a.local_correct}/${a.local_total}`,'local agreement, missing record retained'],[a.rules,'reviewed terminal rules'],[D.m2.equivalent_check_audit.equivalent_check_variants,'equivalent-check probes; zero changes']])}<p class="small">Completion means <b>reusable rule conditions + &gt;90% local agreement</b>. The deployment policy excludes case IDs, instruction/object literals, coordinates, raw check counts, majority shortcuts, and observed-case signature lookup. Statistical transfer is a separate evaluation.</p></section>`;
}
function m2Audit() {
  const m=D.m2,a=m.portability_audit,e=m.equivalent_check_audit;
  return `<div class="grid2"><section class="panel"><h3>Selection → review → deployment</h3><div class="rule"><b>47/48 · deeper fit</b><br>19 terminal rules. Retained as fitting-capacity diagnostic.</div><div class="rule"><b>46/48 · selected compact fit</b><br>15 rules. Qualifies above 90%; selected by support, complexity, and depth.</div><div class="rule"><b>44/48 · reviewed deployment</b><br>14 rules. A contradictory Yes exception was pruned while retaining the accepted accuracy floor.</div><p class="small">The removed exception predicted Yes along conditions asserting every requirement had a missing core endpoint. The reviewed artifact preserves the resulting errors rather than keeping that exception.</p>${details('Exact saved semantic-review action',m.semantic_review)}<table><thead><tr><th>Reference class</th><th>Local correct</th></tr></thead><tbody>${Object.entries(D.m2.training_metrics.per_class).map(([k,v])=>`<tr><td>${title(k)}</td><td>${v.correct}/${v.support}</td></tr>`).join('')}</tbody></table></section><section class="panel"><h3>What the verification establishes</h3><div class="gates">${[[`${m.preservation_and_tests.scoped_tests_passed} scoped implementation tests passed`,true],[`${e.equivalent_check_variants} ID/order/duplicate probes over ${e.observed_cases} observed cases: zero feature/prediction/trace changes`,e.passed],[`All ${a.predictions_independently_recomputed} training predictions independently recomputed`,a.predictions_independently_recomputed===48],[`Every rule has ≥${a.minimum_rule_source_support} source cases and ≥${a.minimum_distinct_instruction_support} distinct instructions`,true],['Reordering training rows and replacing source/batch IDs reproduces the deployment artifact',m.source_invariance_audit.deployment_artifact_byte_content_identical],['No training records or case identifiers in executable runtime artifact',!a.runtime_has_case_identifiers_or_training_records],['No reserved-final predictions',a.reserved_test_predictions===0]].map(([name,ok])=>`<div class="gate ${ok?'':'fail'}"><span class="mark">${ok?'✓':'×'}</span>${name}</div>`).join('')}</div><div class="callout amber">The 515 probes hold semantic interpretation fixed. They verify rule-level portability under equivalent cached-check changes; they do not test fresh model extraction, paraphrases, or repeated visual calls.</div>${details('Exact portability audit',a)}${details('Exact equivalent-check audit',e)}</section></div><section class="panel" style="margin-top:18px"><h3>Why these are reusable rules</h3><p class="small muted">Inspect any terminal rule’s abstract conditions and supporting instructions. Support examples are training/audit metadata; runtime execution receives neither the examples nor their identifiers.</p>${m.rule_support_examples.map((r,i)=>`<details class="support-rule"><summary>Rule ${i+1} · ${title(label(r.prediction))} · ${r.support} sources / ${r.distinct_instructions} instructions</summary><div class="rule">${r.conditions.map(c=>`${c.value?'TRUE':'FALSE'}: ${esc(D.m2.policy.predicate_descriptions[c.feature])}`).join('<br>')}</div>${r.examples.map(x=>`<p class="small"><code>${esc(x.case)}</code> · ${esc(x.instruction)}</p>`).join('')}</details>`).join('')}</section>`;
}
const SHORT_RULES={
  outcome_all_false_any:'Any requested outcome check failed?',
  collateral_disappearance_absence_unknown_all:'All collateral-absence checks unknown?',
  preservation_spatial_relation_true_all:'All preservation / spatial checks true?',
  meaning_collateral_materiality_minor_incidental_all:'All collateral differences minor?',
  meaning_retention_need_recognizable_counterpart_sufficient_all:'Recognizable counterpart sufficient?',
  meaning_endpoint_gap_core_endpoint_missing_all:'Every requirement missing a core endpoint?',
  meaning_progress_uncertain_any:'Any requirement has uncertain progress?',
  meaning_collateral_materiality_material_unrequested_change_all:'All requirements have material collateral?',
  preservation_other_physical_false_any:'Any other preservation check failed?',
  outcome_all_true_all:'All requested outcome checks true?',
  preservation_attribute_false_all:'All preservation / attribute checks failed?',
  meaning_progress_requested_endpoint_all:'Every requested endpoint established?',
  requires_contact:'Does the request require contact?',
  requires_spatial_relation:'Does the request require a spatial relation?',
  collateral_disappearance_absence_false_all:'All collateral absence checks false?',
  collateral_disappearance_absence_true_all:'All collateral absence checks true?',
  intermediate_all_true_all:'All intermediate checks true?',
  meaning_endpoint_gap_none_all:'No endpoint gap in every requirement?',
  meaning_identity_evidence_same_instance_all:'Same instance for every requirement?',
  meaning_progress_incidental_change_only_all:'Only incidental change in every requirement?'
};
function fullTree(id,values,maxTests=Infinity,policy=D.policy){return window.CaliTreeRuleTree.render(policy.tree,{id,values,maxTests,selected:state.treeNodes[id]||'r',shortLabels:SHORT_RULES,descriptions:policy.predicate_descriptions,rows:D.cases.map(c=>({id:c.case,features:facts(c)}))});}
function localBatches() {
  return `<div class="callout">This tab shows the <b>historical v16 teacher-distilled local experiment</b>, not v8. Each G batch contains 12 sources. The local rules fit teacher predictions; dataset reference agreement is reported separately. V8 later fits dataset references directly.</div><div class="grid2">${D.local_groups.map(g=>`<section class="panel"><div class="row"><h3>${g.name} · local reusable policy</h3>${badge('Historical measured fit','historical')}</div>${stats([[`${g.metrics.correct}/12`,'dataset reference agreement on its own batch']])}${['yes','partial'].map(l=>`<div class="rule"><b>${title(l)} if</b><br>${g.policy[l].map(clause=>clause.map(a=>`${esc(a.fact.replaceAll('_',' '))} = ${esc(a.test)}`).join('<br>AND ')).join('<br>OR<br>')}</div>`).join('')}<p class="small muted">Otherwise No, subject to the historical evaluator’s uncertainty bounds. Maximum 3 atoms/clause and 3 clauses/boundary; positive-clause support ≥2 source cases.</p></section>`).join('')}</div><section class="panel" style="margin-top:18px"><h3>Why merge local policies?</h3><p class="small">A local shortcut can fit its own cases and fail elsewhere. The saved v16 policies scored 6/12, 9/12, 9/12, and 8/12 respectively on the shared development set under their original evidence path. Pooling broader support may expose unsupported exceptions; a hierarchy can retain distinctions a common parent loses.</p><p class="small muted">Those scores come from the historical v16 transfer report, not the M1/v8 replay shown in this demo. Four policies evaluated on the same twelve sources still provide twelve independent evaluation examples.</p></section>`;
}
function constrained() {
  return `<section class="panel"><div class="row"><h3>Small anonymous monotone rule grammar</h3>${badge('Earlier implemented baseline','historical')}</div><p class="small">The earlier LocalEvidenceRuleCalibrator fits and scores the same 12 cached single-call evidence records. It is a separate local fitting diagnostic.</p><div class="grid2"><div><h3>Allowed questions</h3>${['Source preserved?','Every core condition has progress?','Every core condition complete?','Every constraint has progress?','Every constraint complete?'].map(x=>`<div class="rule">${x}</div>`).join('')}</div><div><h3>Search policy</h3><ol class="small"><li>At most two learned levels, three split nodes, four leaves.</li><li>Each learned leaf has ≥2 distinct unguarded source cases.</li><li>Protect fixed-policy No; retain unknown evidence as Unresolved.</li><li>Learned leaves are Partial or Yes; better fulfillment cannot reduce the label.</li><li>Maximize same-batch correct, then fewer splits and fewer changes from the original policy.</li></ol><div class="callout amber">These fixed No/monotonicity restrictions belong to this earlier baseline. They were not reinstated as universal label gates in the newer v8 learner.</div></div></div><p class="small muted">A separate EvidenceBatchCalibrator uses multinomial logistic regression with categorical/numeric evidence and TF-IDF text, selecting regularization by stratified CV on a separate 36-case calibration batch. It is a statistical baseline, not a semantic rule hierarchy.</p></section>`;
}
function merges(){return window.CaliTreeMergeView.render(D,state);}
function traceView(result) {
  const total=result.trace.length,step=state.flowStep===4?total:state.treeStep??total;
  return `<div class="tree-advance">${btn('Start at root','tree-reset')}${btn('Previous test','tree-back')}${btn('Next test →','tree-next')}<span class="readout">${step} / ${total} predicate tests followed</span></div>${fullTree('full-trace',facts(current()),step,currentPolicy())}${step>=total?`<div class="result ${label(result.prediction)}"><div><span class="small">Frozen rule output</span><br><strong>${title(label(result.prediction))}</strong></div>${badge('No model call')}</div>`:`<div class="callout">Decision pending · ${total-step} predicate tests remain. Follow the highlighted branches to a leaf.</div>`}`;
}
function flowDetail(c,pred) {
  if(state.flowStep===0)return `<h3>1 · Instruction → bound program</h3><p class="small muted">Input: instruction only. Output: ${c.program.checks.length} questions. This compiler never sees reference labels.</p>${c.program.checks.map(k=>`<div class="rule">${badge(title(k.role),'unknown')} <code>${esc(k.id)}</code><p style="margin:8px 0 0">${esc(k.question)}</p></div>`).join('')}`;
  if(state.flowStep===1)return `<h3>2 · Images + program → observations</h3><p class="small muted">One SOURCE-first presentation. Effective states preserve dependencies, applicability, and absence safeguards.</p><table><thead><tr><th>Check</th><th>Physical state</th><th>Expected</th></tr></thead><tbody>${Object.values(c.record.checks).map(k=>`<tr><td>${esc(k.id)}<br><span class="muted small">${title(k.role)}</span></td><td>${esc(k.state)}</td><td>${esc(k.expected_state)}</td></tr>`).join('')}</tbody></table>`;
  if(state.flowStep===2)return `<h3>3 · Evidence → instruction-relative meaning</h3><p class="small muted">Text-only interpretation; no images, target labels, or prior verdicts.</p>${Object.entries(c.interpretation.requirements).map(([id,r])=>`<div class="evidencebox"><b>${esc(id)}</b>${['progress','endpoint_gap','identity_materiality','collateral_materiality'].map(k=>`<p><span class="muted">${title(k)}:</span> ${esc(title(r[k]))}</p>`).join('')}<p>${esc(r.explanation)}</p></div>`).join('')}`;
  if(state.flowStep===4)return `<h3>5 · Prediction + reference → evaluation</h3>${traceView(pred)}<div class="evidencebox"><b>Reference used only for scoring</b>${outcome(c.reference)} · released mean ${c.human_score.toFixed(4)} / 2<p style="margin-top:12px">${label(pred.prediction)===c.reference?'Agreement on this recorded development source.':'Disagreement retained. Inspect evidence, interpretation, and policy separately before assigning a cause.'}</p></div>`;
  return `<h3>4 · Project facts → ${pred.trace.length} predicate tests</h3>${traceView(pred)}`;
}
function inference() {
  const c=current(),pred=execute(facts(c)),rows=D.cases.slice(0,state.replay);
  const chosen=state.sandbox,fiction=chosen?execute({...facts(c),[chosen]:!facts(c)[chosen]}):null;
  return `${tabs([['merged','Merged root v11'],['m2','Earlier reviewed M2']],'inference-policy',state.inferencePolicy)}${casebar()}${tabs([['0','1 · Compile checks'],['1','2 · Observe images'],['2','3 · Interpret evidence'],['3','4 · Execute policy'],['4','5 · Score prediction']],'flow',String(state.flowStep))}<div class="grid2"><section class="panel"><div class="row"><h3>${c.case} · follow one case</h3>${badge(state.inferencePolicy==='m2'?'Earlier M2 replay':'Current merged root replay')}</div><p class="case-title">${esc(c.instruction)}</p>${pair(c,true)}<div class="flowlane" style="grid-template-columns:1fr;margin-bottom:0"><div class="nodebox"><strong>1 · Compile</strong>${c.program.checks.length} instruction-bound questions</div><div class="nodebox"><strong>2 · Observe + interpret</strong>Cached physical states and instruction-relative meaning</div><div class="nodebox"><strong>3 · Project + execute</strong>Portable Boolean predicates → deterministic saved tree</div></div><div class="callout">Fresh case: 1 instruction-only compilation + 1 visual observation + 1 text-only interpretation. This replay: <b>zero calls</b>. No reference label enters this rule traversal.</div><button data-action="reveal" class="small" ${state.flowStep<3?'disabled':''}>${state.revealed?'Hide reference':'Reveal reference after prediction'}</button>${state.revealed&&state.flowStep>=3?`<div style="margin-top:12px">Reference ${outcome(c.reference)} · mean ${c.human_score.toFixed(4)}<br><span class="small muted">${label(pred.prediction)===c.reference?'Agreement on this recorded case.':'Disagreement is preserved; inspect observations, meaning, and rule conditions separately.'}</span></div>`:''}</section>
  <section class="panel">${flowDetail(c,pred)}<p class="small muted" style="margin-top:15px">Policy artifact <code>${esc(currentPolicy().artifact_ref.slice(0,20))}…</code></p>${state.flowStep===3?`<div class="whatif">${badge('Synthetic counterfactual','illustrative')}<p style="margin-top:10px">Flip one predicate to see how the frozen tree responds. This is a rule-level probe; it does not alter the source evidence or represent a coherent re-observation.</p><select id="sandbox-select" aria-label="Predicate to flip"><option value="">Choose a predicate…</option>${Object.keys(currentPolicy().predicate_descriptions).map(k=>`<option value="${esc(k)}" ${k===chosen?'selected':''}>${esc(currentPolicy().predicate_descriptions[k])}</option>`).join('')}</select>${fiction?`<p style="margin:12px 0 0">${facts(c)[chosen]?'True → False':'False → True'} · synthetic output ${outcome(fiction.prediction)}</p>${details('Synthetic decision trace',fiction.trace)}`:''}</div>`:''}</section></div>
  <section class="panel" style="margin-top:18px"><div class="row"><div><h3>Replay all twelve cases</h3><p class="small muted">Replay reveals saved cases in order. It does not fit, call a model, or select a policy.</p></div><div class="tools">${btn(state.playing?'Pause':'Run twelve','play',null,'primary small')}${btn('Reset','reset-replay',null,'small')}</div></div><div class="progress">${D.cases.map((_,i)=>`<i class="${i<state.replay?'done':''}"></i>`).join('')}</div>${rows.length?`<table><thead><tr><th>Case</th><th>Instruction</th><th>Prediction</th><th>Reference</th><th>Agreement</th></tr></thead><tbody>${rows.map((x,i)=>`<tr class="replayrow ${i===rows.length-1?'just':''}"><td>${btn(x.case,'case',i)}</td><td>${esc(x.instruction)}</td><td>${outcome(predicted(x).prediction)}</td><td>${outcome(x.reference)}</td><td>${label(predicted(x).prediction)===x.reference?'✓':'Disagreement'}</td></tr>`).join('')}</tbody></table>`:'<div class="reveal-placeholder">Ready · 12 historically exposed development cases</div>'}</section>`;
}
function resultPage() {
  const refs=D.cases.map(c=>labels.indexOf(c.reference)),pred=D.cases.map(c=>c.prediction.prediction),m=metrics(pred,refs),old=metrics(D.cases.map(c=>c.m2_prediction.prediction),refs),diag=metrics(D.cases.map(c=>c.diagnostic.prediction),refs);
  return `<div class="grid2"><section class="panel"><div class="row"><h3>Current merged root · recorded development replay</h3>${badge('Exact frozen artifact')}</div>${stats([[`${m.correct}/12`,'full-denominator agreement'],[m.macro_f1.toFixed(3),'macro-F1'],[`${12-m.unresolved}/12`,'resolved outputs']])}<div class="confusion"><span></span>${['No','Partial','Yes','Unres.'].map(x=>`<span class="axis">${x}</span>`).join('')}${labels.map((y,k)=>`<span class="axis">Ref ${title(y)}</span>${[0,1,2,-1].map(p=>{const n=pred.filter((v,i)=>v===p&&refs[i]===k).length;return `<span class="cell ${p===k?'diag':n?'err':''}">${n}</span>`;}).join('')}`).join('')}</div><p class="small muted" style="margin-top:12px">Rows: reference. Columns: prediction. H01 and H07 are preserved disagreements: both No references receive Partial.</p><div class="callout amber">These twelve sources have historical exposure. The 10/12 result was scored after training-only root selection; it is a small development diagnostic, not final-test accuracy or a broad transfer claim.</div></section><section class="panel"><h3>Compare the same twelve evidence records</h3><table><thead><tr><th>Policy</th><th>Training</th><th>Development</th><th>Rules</th></tr></thead><tbody><tr><td>Reviewed M2 baseline</td><td>44/48</td><td>${old.correct}/12</td><td>14</td></tr><tr><td>Fresh refit control</td><td>${D.merge.fresh_refit_control.training.correct}/48</td><td>${D.merge.fresh_refit_control.development.correct}/12</td><td>${D.merge.fresh_refit_control.rules}</td></tr><tr class="selected"><td>Selected reuse-first root</td><td>46/48</td><td>${m.correct}/12</td><td>14</td></tr></tbody></table><h3 style="margin-top:18px">Development recall</h3><table><thead><tr><th>Reference</th><th>Earlier M2</th><th>Merged root</th></tr></thead><tbody>${labels.map((name,k)=>`<tr><td>${title(name)}</td><td>${old.per[k].correct}/${old.per[k].support}</td><td>${m.per[k].correct}/${m.per[k].support}</td></tr>`).join('')}</tbody></table><p class="small muted" style="margin-top:12px">M1’s fixed uncalibrated readout remains ${diag.correct}/12 with ${diag.unresolved} unresolved. It is a separate diagnostic. The reserved final fifty: <b>Not evaluated here</b>.</p></section></div><section class="panel" style="margin-top:18px"><h3>Every case and disagreement retained</h3><table><thead><tr><th>Case</th><th>Instruction</th><th>Reference</th><th>Earlier M2</th><th>Merged root</th></tr></thead><tbody>${D.cases.map((c,i)=>`<tr><td>${btn(c.case,'open-inference',i)}</td><td>${esc(c.instruction)}</td><td>${outcome(c.reference)}</td><td>${outcome(c.m2_prediction.prediction)}</td><td>${outcome(c.prediction.prediction)} ${label(c.prediction.prediction)===c.reference?'✓':''}</td></tr>`).join('')}</tbody></table></section><div class="statusgrid"><section class="panel"><h3>What is implemented, and what remains open</h3><p>${badge('Implemented research')}<br><span class="small">M1 bound evidence, M2 portable rule learning, and M5–M7 exact-union reuse-first merging. M4 is deliberately skipped in this path.</span></p><p>${badge('Qualified local consolidation')}<br><span class="small">Seven selected merges, all 48 sources retained, final child-only vocabulary, 19 → 14 rules and 36 → 27 policy nodes at the last merge.</span></p><p>${badge('Limits','illustrative')}<br><span class="small">Five lower-level merges require full-grammar repair. Three training Yes decisions still have cached endpoint/incidental-progress conflicts. Rule-level portability does not prove semantic correctness.</span></p><p>${badge('Separate work','unknown')}<br><span class="small">M8/final evaluation, broad statistical transfer, repeated extraction robustness, and broader integration remain separate.</span></p>${btn('Inspect study controls and semantic conflicts →','merge-limits',null,'small')}</section><section class="panel links"><h3>Source ledger</h3><p class="small muted">All results are replayed from saved local records. The export independently recomputes the seven union gates and pair diagnostics and all 48/12 frozen-root predictions. No new judge calls or final-case records.</p>${D.provenance.map(p=>`<p><code>${esc(p)}</code><br><code class="muted">${esc(D.source_hashes[p]||'')}</code></p>`).join('')}${details('Frozen union package manifest',D.merge.package_manifest)}${details('Current deployment policy',D.policy)}</section></div>`;
}
const renderers=[overview,dataset,selection,checks,evidence,calibration,merges,inference,resultPage];
function render() {
  const stage=state.stage;
  const previousDialog=app.querySelector('.mi-dialog'),scroll=app.querySelector('.mi-body')?.scrollTop||0;
  const active=document.activeElement;
  const focus=previousDialog?.contains(active)?{id:active.id,action:active.dataset.action,value:active.dataset.value,treeKey:active.dataset.treeKey,treeNode:active.dataset.treeNode}:null;
  app.innerHTML=`<div class="shell"><aside class="sidebar"><div class="brand"><svg viewBox="0 0 32 36" fill="none" aria-hidden="true"><path d="M16 32V18M16 23L6 15M16 18L26 10M16 12V5" stroke="#c7ddbc" stroke-width="2"/><circle cx="6" cy="12" r="4" fill="#a7c996"/><circle cx="26" cy="7" r="4" fill="#a7c996"/><circle cx="16" cy="5" r="4" fill="#e1ebc9"/></svg>CaliTree</div><p class="eyebrow">An end-to-end walkthrough</p><nav class="nav" aria-label="Presentation chapters">${stages.map((name,i)=>`<button data-action="stage" data-value="${i}" class="${i===stage?'active':''}" ${i===stage?'aria-current="step"':''}><span class="num">${String(i+1).padStart(2,'0')}</span>${name}</button>`).join('')}</nav><div class="sidebottom"><strong>Research snapshot · Oct 15, 2026</strong>12 real development cases<br>7 recorded semantic merges<br>100% offline replay</div></aside><main class="main"><header class="topbar"><span class="breadcrumb">RESEARCH DEMO &nbsp;/&nbsp; ${esc(stages[stage])}</span><div class="tools"><span class="offline"><i class="dot"></i>Offline · no API calls</span>${btn(state.notes?'Hide speaker notes':'Speaker notes','notes',null,'ghost')}<a class="version-link" href="six-case-demo.html">6-case explainer ↗</a>${btn(document.body.classList.contains('presenting')?'Exit present':'Present','present',null,'ghost')}</div></header><div class="content"><div class="heading"><div><div class="eyebrow">${String(stage+1).padStart(2,'0')} / ${stages.length} · ${esc(stages[stage])}</div><h1>${subtitles[stage]}</h1></div>${badge(stage===6?'Recorded v11 merge study':'Code-backed research snapshot')}</div><p class="intro">${['Explore the implemented evidence, local learning, exact-union merging, and single-policy inference flow.','A source image and an edit instruction go to the editing model. CaliTree judges the resulting edited image against that request.','Dataset sampling, fitted-model selection, inference routing, and merge proposal ranking use different information.','Inspect the real instruction-specific program. Check identities bind every later observation to the question it actually answers.','A physical observation is evidence. The calibration policy decides how that evidence maps to human satisfaction.','Compare the current merged root with the earlier reviewed M2 baseline, and inspect their saved rule trees.','Replay the selected eight-group construction, actual parent gates, reuse modes, controls, and limitations.','Traverse the current saved root or the earlier M2 tree, reveal references afterward, and replay all twelve cases.','Inspect every prediction and keep implementation status, illustrative behavior, and measured performance distinct.'][stage]}</p>${renderers[stage]()}${state.notes?`<aside class="presenter"><span class="eyebrow">Speaker notes · ~1 minute</span>${notes[stage]}</aside>`:''}<footer class="footnav"><button data-action="prev" ${stage===0?'disabled':''}>← Previous</button><span class="muted">${stage+1} / ${stages.length} &nbsp;·&nbsp; <span class="kbd">←</span> <span class="kbd">→</span> chapters &nbsp; <span class="kbd">[</span> <span class="kbd">]</span> cases &nbsp; <span class="kbd">N</span> notes</span><button class="primary" data-action="next" ${stage===stages.length-1?'disabled':''}>Next chapter →</button></footer></div></main></div>`;
  app.insertAdjacentHTML('beforeend',window.CaliTreeMergeInspector.render(D,state.mergeInspector,state.treeNodes));
  document.body.classList.toggle('merge-inspector-open',!!state.mergeInspector);
  app.querySelector('.shell').inert=!!state.mergeInspector;
  window.CaliTreeRuleTree.mount(app);
  window.CaliTreeMergeRounds.mount(app,state);
  if(state.mergeInspector){
    const body=app.querySelector('.mi-body');body.scrollTop=state.mergeInspector.resetScroll?0:scroll;state.mergeInspector.resetScroll=false;
    const dialog=app.querySelector('.mi-dialog');let target;
    if(focus?.id)target=dialog.querySelector('#'+focus.id);
    else if(focus?.treeKey)target=[...dialog.querySelectorAll('[data-tree-key]')].find(el=>el.dataset.treeKey===focus.treeKey&&el.dataset.treeNode===focus.treeNode);
    else if(focus?.action)target=[...dialog.querySelectorAll('button[data-action]')].find(el=>el.dataset.action===focus.action&&el.dataset.value===focus.value);
    (target||dialog.querySelector('.mi-close')).focus({preventScroll:true});
  }
}
function stopRound(){clearInterval(roundTimer);roundTimer=null;state.roundPlaying=false;}
function stop() {clearInterval(timer);timer=null;state.playing=false;stopRound();}
function setMergeRound(n,{playing=false,nodeId=null}={}){
  if(!playing)stopRound();
  const crossChapter=state.stage!==6;
  state.stage=6;state.mergeTab='rounds';state.mergeRound=Math.min(3,Math.max(0,Number(n)));
  state.roundSelected=nodeId||window.CaliTreeMergeRounds.model(D).levels[state.mergeRound][0].node_id;
  render();if(crossChapter)window.scrollTo({top:0,behavior:'instant'});
}
function openMergeInspector(id){
  if(!D.merge.nodes[id])return;
  if(!state.mergeInspector){const active=document.activeElement;inspectorReturn=active?.dataset.roundNode?{roundNode:id}:
    active?.dataset.treeKey==='merge-history'?{history:active.dataset.treeNode}:
    {action:active?.dataset.action,value:active?.dataset.value};}
  stop();state.mergeInspector={...window.CaliTreeMergeInspector.initial(D,id),resetScroll:true};render();
}
function closeMergeInspector(){state.mergeInspector=null;render();
  const restore=inspectorReturn?.roundNode?app.querySelector(`[data-round-node="${inspectorReturn.roundNode}"]`):
    inspectorReturn?.history?app.querySelector(`[data-tree-key="merge-history"][data-tree-node="${inspectorReturn.history}"]`):
    [...app.querySelectorAll('button[data-action]')].find(el=>el.dataset.action===inspectorReturn?.action&&el.dataset.value===inspectorReturn?.value)||app.querySelector('[data-action="mi-open"]');
  restore?.focus?.({preventScroll:true});inspectorReturn=null;
}
function selectRoundNode(id){const n=D.merge.nodes[id];if(!n)return;setMergeRound(n.height,{nodeId:id});app.querySelector(`[data-round-node="${id}"]`)?.focus?.();openMergeInspector(id);}
function setStage(n) {stop();state.stage=Math.max(0,Math.min(stages.length-1,Number(n)));state.sandbox=null;state.treeStep=null;render();window.scrollTo({top:0,behavior:'instant'});}
function setCase(n) {state.caseIndex=(Number(n)+12)%12;state.check=null;state.revealed=false;state.sandbox=null;state.treeStep=null;state.treeNodes={};render();}
function images() {
  const modal=document.createElement('div');modal.className='modal';modal.setAttribute('role','dialog');modal.setAttribute('aria-modal','true');modal.setAttribute('aria-label','Source and edited image comparison');modal.innerHTML=`<div class="modal-inner"><div class="row"><h2>${current().case} · Image comparison</h2>${btn('Close ×','close-modal')}</div><p>${esc(current().instruction)}</p>${pair(current())}</div>`;app.append(modal);modal.querySelector('button').focus();modal.addEventListener('click',e=>{if(e.target===modal)modal.remove();});
}
app.addEventListener('click',e=>{
  if(e.target.classList.contains('mi-overlay')){closeMergeInspector();return;}
  const b=e.target.closest('button[data-action], [data-round-node]');if(!b)return;
  if(b.dataset.roundNode){selectRoundNode(b.dataset.roundNode);return;}
  const value=b.dataset.value;
  switch(b.dataset.action) {
    case 'mi-open':openMergeInspector(value);break;
    case 'mi-close':closeMergeInspector();break;
    case 'mi-tab':state.mergeInspector.tab=value;state.mergeInspector.resetScroll=true;render();break;
    case 'mi-filter':state.mergeInspector.filter=value;render();break;
    case 'mi-view':state.mergeInspector.view=value;render();break;
    case 'mi-trace':state.mergeInspector.traceStep=value==='all'?null:Number(value);render();break;
    case 'mi-case':state.mergeInspector.caseId=value;state.mergeInspector.traceStep=null;render();break;
    case 'mi-prev':
    case 'mi-next':{const s=state.mergeInspector,rows=window.CaliTreeMergeInspector.context(D,s.id).rows,i=rows.findIndex(r=>r.case===s.caseId);s.caseId=rows[(i+(b.dataset.action==='mi-next'?1:rows.length-1))%rows.length].case;s.traceStep=null;render();break;}

    case 'tree-reset':state.treeStep=0;render();break;
    case 'tree-next':state.treeStep=Math.min(execute(facts(current())).trace.length,(state.treeStep??0)+1);render();break;
    case 'tree-back':state.treeStep=Math.max(0,(state.treeStep??execute(facts(current())).trace.length)-1);render();break;
    case 'stage':setStage(value);break;
    case 'prev':setStage(state.stage-1);break;
    case 'next':setStage(state.stage+1);break;
    case 'case':setCase(value);break;
    case 'check':state.check=value;render();break;
    case 'selection':state.selection=value;render();break;
    case 'tab':state.tab=value;render();break;
    case 'flow':state.flowStep=Number(value);state.sandbox=null;render();break;
    case 'open-merge-rounds':setMergeRound(0);break;
    case 'round-stage':setMergeRound(value);break;
    case 'round-reset':setMergeRound(0);break;
    case 'round-back':setMergeRound(state.mergeRound-1);break;
    case 'round-next':setMergeRound(state.mergeRound+1);break;
    case 'round-play':
      if(state.roundPlaying){stopRound();render();break;}
      stop();if(state.mergeRound===3)setMergeRound(0);state.roundPlaying=true;state.mergeTab='rounds';render();
      roundTimer=setInterval(()=>{const next=state.mergeRound+1;if(next>=3)stopRound();setMergeRound(next,{playing:true});},2200);break;
    case 'round-policy':
    case 'round-details':{stopRound();const n=D.merge.nodes[value],l=window.CaliTreeMergeView.lineage(D);state.mergeStep=D.merge.steps.find(e=>e.node_id===value)?.step||0;state.treeNodes['merge-history']=l.reverse[value];state.mergeGraph=b.dataset.action==='round-policy'?'policy':'lineage';state.mergeTab='history';render();break;}
    case 'merge-step':state.mergeStep=Number(value);delete state.treeNodes['merge-history'];render();break;
    case 'merge-tab':stopRound();state.mergeTab=value;render();break;
    case 'merge-graph':state.mergeGraph=value;render();break;
    case 'open-merging-algorithm':state.mergeTab='algorithm';setStage(6);break;
    case 'inference-policy':stop();state.inferencePolicy=value;state.replay=0;state.treeStep=null;state.treeNodes={};state.sandbox=null;state.revealed=false;render();break;
    case 'notes':state.notes=!state.notes;render();break;
    case 'present':document.body.classList.toggle('presenting');render();break;
    case 'images':images();break;
    case 'close-modal':b.closest('.modal').remove();break;
    case 'selection-stage':state.selection='candidate';setStage(2);break;
    case 'merge-limits':state.mergeTab='limits';setStage(6);break;
    case 'open-inference':state.inferencePolicy='merged';state.caseIndex=Number(value);state.check=null;state.revealed=false;setStage(7);break;
    case 'reveal':state.revealed=!state.revealed;render();break;
    case 'reset-replay':stop();state.replay=0;render();break;
    case 'play':
      if(state.playing){stop();render();break;}
      if(state.replay===12)state.replay=0;
      state.playing=true;
      function tick(){state.caseIndex=state.replay;state.flowStep=3;state.check=null;state.sandbox=null;state.revealed=false;state.replay++;if(state.replay===12)stop();render();}
      tick();if(state.playing)timer=setInterval(tick,1200);break;
  }
});
app.addEventListener('change',e=>{if(e.target.id==='mi-case'){state.mergeInspector.caseId=e.target.value;state.mergeInspector.traceStep=null;render();return;}if(e.target.id==='sandbox-select'){state.sandbox=e.target.value||null;render();}});
document.addEventListener('keydown',e=>{
  if(state.mergeInspector){
    if(e.key==='Escape'){e.preventDefault();closeMergeInspector();return;}
    if(e.key==='Tab'){
      const items=[...app.querySelectorAll('.mi-dialog button:not([disabled]),.mi-dialog select,.mi-dialog summary,.mi-dialog [tabindex="0"]')].filter(el=>{
        for(let parent=el.parentElement;parent&&!parent.classList.contains('mi-dialog');parent=parent.parentElement){
          if(parent.tagName==='DETAILS'&&!parent.open&&!parent.querySelector('summary')?.contains(el))return false;
        }return true;
      });
      const index=items.indexOf(document.activeElement);
      if(e.shiftKey&&index<=0){e.preventDefault();items.at(-1)?.focus();}
      else if(!e.shiftKey&&(index===items.length-1||index<0)){e.preventDefault();items[0]?.focus();}
    }
    return;
  }
  const roundNode=e.target.closest('[data-round-node]');if(roundNode&&['Enter',' '].includes(e.key)){e.preventDefault();selectRoundNode(roundNode.dataset.roundNode);return;}
  if(e.target.closest('select,input,textarea,[data-tree-widget],[data-round-map]')||e.ctrlKey||e.metaKey||e.altKey)return;
  if(e.key==='Escape'){document.querySelector('.modal')?.remove();return;}
  if(document.querySelector('.modal'))return;
  if(e.key==='ArrowRight'){e.preventDefault();setStage(state.stage+1);}
  if(e.key==='ArrowLeft'){e.preventDefault();setStage(state.stage-1);}
  if(e.key===']'){e.preventDefault();setCase(state.caseIndex+1);}
  if(e.key==='['){e.preventDefault();setCase(state.caseIndex-1);}
  if(e.key.toLowerCase()==='n'){state.notes=!state.notes;render();}
});
window.CaliTreeRuleTree.bind(app,(key,id)=>{state.treeNodes[key]=id;if(key==='merge-history'){const node=window.CaliTreeMergeView.lineage(D).map[id];state.mergeStep=D.merge.steps.find(e=>e.node_id===node)?.step||0;openMergeInspector(node);return;}render();});
// A small public read-only hook supports parity verification without depending on UI text.
window.CaliTreeDemo=Object.freeze({execute,metrics});
for(const c of D.cases) {
  const p=execute(facts(c));
  if(JSON.stringify(p.trace)!==JSON.stringify(c.prediction.trace)||p.prediction!==c.prediction.prediction)throw new Error('Exported merged policy replay mismatch: '+c.case);
  const old=execute(facts(c),D.m2.policy);if(old.prediction!==c.m2_prediction.prediction||JSON.stringify(old.trace)!==JSON.stringify(c.m2_prediction.trace))throw new Error('Earlier M2 replay mismatch: '+c.case);
}
window.addEventListener('hashchange',()=>{if(window.location.hash==='#merging')setMergeRound(0);});
if(window.location.hash==='#merging'){state.stage=6;state.mergeTab='rounds';}
render();
})();
