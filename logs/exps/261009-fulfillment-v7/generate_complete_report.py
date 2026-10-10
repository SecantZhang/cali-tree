"""Generate the complete experiment report from saved data; no model calls."""
from collections import Counter
from pathlib import Path
import json

P=Path(__file__).resolve().parent
ROOT=P.parents[2]
OUT=ROOT/'docs/experiments/calitree_fulfillment_v7_complete_report.md'


def pct(n,d):return f'{100*n/d:.1f}%'
def name(label):return {'yes':'Satisfied','partial':'Partial','no':'Nonsatisfied',None:'Unresolved'}[label]
def distribution(rep):return ', '.join(f'{name(None if k=="unresolved" else k)} × {v}' for k,v in rep['label_distribution'].items())
def spec_link(arm,i):return f'../../logs/exps/261009-fulfillment-v7/frozen/{arm}/{i}.json'


def main():
    m=json.loads((P/'manifest.json').read_text());r=json.loads((P/'results.json').read_text())
    summary=json.loads((P/'summary.json').read_text());assert r['status']=='completed'
    rows=[];search={};details=[];machine=[]
    for arm in m['arms']:
        events=Counter();errors=Counter();actions=Counter();scope_calls=scope_tokens=0
        for i,c in enumerate(m['cases']):
            saved=json.loads((P/'frozen'/arm/f'{i}.json').read_text())['nodes']['leaf:'+c['id']]['result']
            h=saved['lineage'][-1];u=r['cases'][c['id']][arm]['usage']
            events.update(rounds_started=h['search_schedule']['rounds_started'],rounds_completed=h['search_schedule']['rounds_completed'],proposed=len(saved['lineage'])-1)
            for item in saved['lineage'][:-1]:
                if item.get('error'):errors[item['error']]+=1
                if item.get('structural_valid'):events['structural_valid']+=1
                if item.get('duplicate'):events['duplicate']+=1
                if item.get('screen_diagnosis'):events['screened_new']+=1
                actions.update(a['operation'] for a in item['transaction']['actions'])
            scope_calls+=u['search']+u['final'];scope_tokens+=u['completion_tokens_or_reserved']
        search[arm]={'events':dict(events),'errors':dict(errors),'operations':dict(actions),'calls':scope_calls,'charged_tokens':scope_tokens}
    for i,c in enumerate(m['cases']):
        by_arm={};detail=[f'### {i+1}. {c["instruction"]}',f'\nReference: **{name(c["target"])}**. Case identity: `{c["id"]}`.\n',
            f'[Source image](<{c["evidence"]["source_image"]}>) · [Edited image](<{c["evidence"]["edited_image"]}>)\n']
        for arm in m['arms']:
            row=r['cases'][c['id']][arm];saved=json.loads((P/'frozen'/arm/f'{i}.json').read_text())['nodes']['leaf:'+c['id']]['result']
            f=row['final']['selected'];seed=row['final']['seed'];program=saved['selected']['program'];h=saved['lineage'][-1];u=row['usage']
            by_arm[arm]={'seed':round(seed['agreement']*5),'selected':round(f['agreement']*5),'row':row,'saved':saved}
            changed=saved['seed']['program_ref']!=saved['selected']['program_ref']
            detail += [f'#### {arm}', '', f'Final seed → selected matches: **{round(seed["agreement"]*5)} → {round(f["agreement"]*5)} / 5**. '
                f'Selected labels: {distribution(f)}. Status: `{row["support_status"]}`. '
                f'Program changed: {"yes" if changed else "no"}. Checks: {len(saved["seed"]["program"]["nodes"])} → {len(program["nodes"])}.', '',
                f'Search rounds: {h["search_schedule"]["rounds_started"]} started / {h["search_schedule"]["rounds_completed"]} completed. '
                f'Stop: `{saved["stop_reason"]}`. Calls: {u["search"]} search + {u["final"]} final. '
                f'Charged completion tokens: {u["completion_tokens_or_reserved"]:,}.', '',
                f'[Exact saved program, candidates and edits]({spec_link(arm,i)}). Selected program hash: `{saved["selected"]["program_ref"]}`.', '',
                '| Check | Weight | Saved question |','|---|---:|---|']
            for n in program['nodes']:
                detail.append(f'| {n["id"]} | {100*n["weight_numerator"]/n["weight_denominator"]:.1f}% | {n["question"].replace("|","/")} |')
            detail += ['', '| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |',
                '|---|---|---|---|---|']
            for j,t in enumerate(f['traces'],1):
                v=t['fulfillment'];bounds=str(v['score']) if v['score'] is not None else f'[{v["lower"]}, {v["upper"]}]'
                score=', '.join(f'{o["check_id"]}: {o.get("fulfillment_score")}' for o in t['observations'])
                confidence=', '.join(f'{o["check_id"]}: {o["confidence"]}' for o in t['observations'])
                detail.append(f'| {j} | {bounds} | {name(t["label"])} | {score} | {confidence} |')
            detail += ['', 'Acceptance failures: '+(', '.join(row['acceptance']['reasons']) or 'none')+'.', '',
                'Raw labels before recovery: '+distribution(f['raw_measurements'])+'. '
                'Same-observation readout accuracy: '+', '.join(f'{mode} {round(v*5)}/5' for mode,v in f['counterfactual_agreement'].items())+'.', '',
                'Saved fulfillment anchors:', '']
            for n in program['nodes']:
                detail += [f'- **{n["id"]} — 0:** {n["zero_when"]}',f'- **{n["id"]} — 0.5:** {n["half_when"]}',f'- **{n["id"]} — 1:** {n["full_when"]}']
            detail += ['']
        rows.append(f'| {i+1} | {c["instruction"]} | {name(c["target"])} | {by_arm["binary"]["seed"]} → {by_arm["binary"]["selected"]} | '
            f'{by_arm["fulfillment"]["seed"]} → {by_arm["fulfillment"]["selected"]} | '
            f'{distribution(by_arm["fulfillment"]["row"]["final"]["selected"])} |')
        details+=detail;machine.append({'case_id':c['id'],'instruction':c['instruction'],'reference':c['target'],
            'arms':{a:{'result':v['row'],'saved_program_result':v['saved']} for a,v in by_arm.items()}})
    text='''# Complete report: CaliTree weighted fulfillment experiment

Experiment: `261009-fulfillment-v7`. Status: **completed after an explicitly authorized continuation**.

## 1. Decision-relevant findings

Weighted fulfillment achieved **48/60 correct final runs (80.0%)**, versus **35/60 (58.3%)** for this experiment's strict binary readout: **+21.7 percentage points**. All-five-correct cases improved from **7/12 to 8/12**. The entire draw-accuracy gain was on partial-reference cases.

These results support graded scoring under this shared observer, but **do not establish a new best optimizer**. The preceding v6 Luna-only experiment scored **52/60 (86.7%)**, and also had eight all-five-correct cases. Its Boolean observer differed. Switching thresholds alone on binary-optimized v7 programs actually changed accuracy from **35/60 to 34/60**; the improvement required criteria/anchors adapted to fulfillment scoring.

This remains local fitting on twelve previously observed cases. It establishes neither cross-case generalization nor correctness of each atomic judgment. Ten seeds and most selected programs contain one broad condition; the result is **not evidence that a decomposed prompt tree outperforms a broad judge**.

## 2. What was tested

The exact prior twelve AURORA cases were reused: four satisfied, four partial, four nonsatisfied, with distinct source-pixel groups and verified source/edited image hashes. All labels can guide their own leaf's fitting. Historical observations and feedback were excluded from the new run.

One label-free compilation per case produced a common decomposition, binding, score anchors and weight ledger. The two arms received identical seed conditions, differing only in their saved scoring mode. Both used GPT-6 Luna, temperature zero, reasoning none, with independent optimization histories and observations. No Sol proposer, semantic auditor or model-based final readout ran.

**Important baseline definition:** this pair uses an anchored numerical observer in both arms. The binary arm converts score **1** to a fully-complete vote and every known score below 1 to an incomplete vote; all/some/none determines its label. It is **not a rerun of the historical v6 model's Boolean pass/fail prompt**. This distinction limits claims about replacing the existing best implementation.

## 3. Scoring definitions

Each required component produces a fulfillment degree `f_i` in [0,1], grounded by saved examples for no achievement, half achievement and full achievement. Confidence is a separate estimate of certainty. A condition can be half fulfilled with high confidence; confidence never increases its score or weight.

For applicable required conditions, `F = sum(w_i × f_i) / sum(w_i)`:

| Fulfillment | Label |
|---|---|
| F >= 0.9 | Satisfied |
| F <= 0.1 | Nonsatisfied |
| 0.1 < F < 0.9 | Partial |

Code assigns equal immutable requirement budgets, then equal shares to their seed facets. Splitting divides the parent share equally while preserving its root. Auxiliary additions have zero weight. Required positive mass cannot be removed, and neither weights nor thresholds can be proposed by the model. Exact rational arithmetic protects threshold boundaries.

Unknown/invalid/transport-failed scores contribute a possible range [0,1], never a zero vote. The aggregate resolves only when its entire lower-to-upper range occupies one label band. Example: one half-weight condition at .5 and one unmeasured condition yield [.25,.75], safely partial **under the declared scores**. The missing atom remains explicit and can fail confidence/robustness gates.

## 4. Optimization and verification procedure

1. Compile the shared seed without reference labels or optimization feedback.
2. Independently screen each arm's program once. Confirm resolved matching candidates with five fresh draws.
3. Use node-level native TextGrad feedback and label-blind visual discovery to propose at most two immutable transactions per round, up to fifteen rounds. Allowed edits are revision, conserved splitting, zero-weight auxiliary addition and auxiliary removal.
4. Retain the seed and valid intermediates; reject broken coverage, weights, endpoints, schema or four-check limits. Rejected diagnostics return to later proposals.
5. Qualification requires 5/5 target agreement and resolved coverage, confidence >=.8 on executed checks, requirement/check consistency >=.8, and at least three eligible observations. This is empirical qualification without semantic-audit approval.
6. Freeze **all 24 selections before any final draw**. Execute each seed and selected program five fresh times. Final outcomes cannot trigger edits or candidate replacement.

The numerical observer receives the condition/anchors, source and edited images, and original requirement. It receives **no reference label, feedback, scoring mode, thresholds or weights**. Every trace records both deterministic readouts on its scores. Models cannot return the final category directly.

One transport-only recovery check per report is permitted in a distinct durable slot, selected in execution order without labels. Every other observation remains exact. Valid wrong/uncertain, schema-invalid and interrupted observations are never resampled. Raw results, both attempts and all charges remain saved.

## 5. Metrics and column meanings

- **Accuracy:** final labels matching the reference divided by 60 planned selected runs per arm. Unresolved draws are incorrect. Twelve cases × five repeats produces 60 measurements, not 60 independent cases.
- **Coverage:** fraction of runs producing a resolved label; a wrong answer still has coverage.
- **All-five-correct case ratio:** cases matching their reference in all five final runs divided by twelve. This matches the user's accurate-and-repeatable definition.
- **Locally robust:** qualified confirmation plus fresh final agreement, coverage, atomic consistency and confidence gates. Overall label stability alone is insufficient.
- **Seed → selected:** correct fresh final runs before/after local optimization; both measured independently. The seed was retained when no acceptable replacement survived.
- **Raw / effective:** scheduled observations before / after the one-check transport-recovery allowance.
- **Fulfillment score:** degree of completion; **confidence:** certainty of the observation. Neither is a calibrated probability of correctness.
- **Rounds started / completed:** dispatched repair rounds / rounds without infrastructure interruption. Started rounds still count against the fifteen-round cap.

## 6. Aggregate outcomes

| Metric | Binary | Weighted fulfillment |
|---|---:|---:|
| Seed correct final runs | 27/60 (45.0%) | 30/60 (50.0%) |
| Selected correct final runs | 35/60 (58.3%) | 48/60 (80.0%) |
| Selected resolved runs | 60/60 (100%) | 59/60 (98.3%) |
| Raw all-five-correct cases | 5/12 (41.7%) | 6/12 (50.0%) |
| Effective all-five-correct cases | 7/12 (58.3%) | 8/12 (66.7%) |
| Strict locally robust cases | 7/12 | 8/12 |
| Selected programs changed | 2/12 | 4/12 |

| Reference class | Binary matches | Fulfillment matches |
|---|---:|---:|
| Satisfied | 15/20 (75%) | 15/20 (75%) |
| Partial | 0/20 (0%) | 13/20 (65%) |
| Nonsatisfied | 20/20 (100%) | 20/20 (100%) |

The case-level gain was only one additional perfect case, despite thirteen additional correct draws. Pencil and chalk each matched four times rather than all five. A small dataset and within-case repeated measurements do not support a statistical significance or generalization claim.

## 7. All twelve cases

The match columns count correct final runs **out of five**, shown as seed → selected. Names are the original instructions. The last column describes the selected fulfillment program's final labels.

| # | Instruction | Reference | Binary matches / 5 | Fulfillment matches / 5 | Fulfillment selected labels |
|---|---|---|---:|---:|---|
'''+ '\n'.join(rows)+'''

## 8. What caused the difference

**Pencil:** the binary arm predicted nonsatisfied four times and satisfied once, with scores .65, .65, .85, .85 and 1. The fulfillment arm predicted partial four times and satisfied once, at .85, .65, 1, .75 and .85. Grading captured intermediate fulfillment, but one complete-score estimate still broke repeatability.

**Mug:** binary remained satisfied in 5/5. Fulfillment revised source-object binding and score anchors after four rounds, then returned .5 / partial in 5/5. Its saved binding explicitly discusses the original blue mug, a blue remnant, and multiple new candidate mugs. The model inferred partial movement; the original mug's identity remains ambiguous. Matching the reference does not certify correct object tracking.

**Chalk:** binary repeatedly scored .85 but converted every incomplete endpoint to a negative vote, yielding nonsatisfied in 5/5. Fulfillment correctly mapped .85 to partial in four runs. A failed primary call and failed recovery left one score unmeasured [0,1], so that case remained unresolved and not locally robust.

**Jacket:** both arms repeatedly scored 0 against a satisfied reference. **Frog:** both repeatedly scored 1 against a partial reference. Softer aggregation did not resolve these persistent disagreements. The experiment does not establish whether the visual interpretation, criteria or annotation is responsible.

## 9. Same-observation counterfactuals

These computations reuse the exact selected-program observations; they make no new model calls and do not select new candidates.

| Program family and observations | Binary readout correct | Fulfillment readout correct |
|---|---:|---:|
| Binary-optimized programs | 35/60 | 34/60 |
| Fulfillment-optimized programs | 35/60 | 48/60 |

On binary-optimized programs, the fulfillment mapping gained nine partial-case matches but lost ten nonsatisfied matches: DVD mean .25 and comic means .175–.275 became partial. Fulfillment optimization instead drove their observed degree to 0 using revised criteria/bindings. Therefore **switching the aggregation formula alone was insufficient**. The combined scoring-aware optimization performed better within this pair.

Independent optimization and fresh measurements still differ between arms. The counterfactuals isolate deterministic readout effects on each program's saved observations; they do not simulate how the other optimization path would evolve.

## 10. Search effort and rejected proposals

'''
    text+='| Measurement | Binary | Fulfillment |\n|---|---:|---:|\n'
    for label,key in [('Repair rounds started','rounds_started'),('Repair rounds completed','rounds_completed'),('Proposed transactions','proposed'),('Structurally valid transactions','structural_valid'),('Duplicate candidates','duplicate'),('New candidates screened','screened_new')]:
        text+=f'| {label} | {search["binary"]["events"].get(key,0)} | {search["fulfillment"]["events"].get(key,0)} |\n'
    text+='''
Binary used 488 case-scoped calls and 100,017 charged completion tokens; fulfillment used 367 calls and 57,132 tokens. The twelve shared compilation calls consumed another 3,329 completion tokens. These are recorded usage comparisons on this set, not universal efficiency estimates.

Three binary and four fulfillment transactions were rejected. Three rejections across both arms contained the word “progress” in a question; four tried to change the saved endpoint string. Duplicates were retained in history but not screened again.

**Guard limitations:** the jacket fulfillment proposal in round 11 asked whether the jacket was fully closed, partly closed with visible progress, or unchanged, while preserving its endpoint. The lexical progress guard rejected it. This could be a legitimate graded question, so the guard is more restrictive than a semantic check. Frog proposals that clarified a “newly added frog” were rejected for changing the endpoint text. Exact string equality can reject meaningful refinements. These candidates were not measured, and we cannot claim they would have improved accuracy. The rejections are implementation constraints, not semantic-audit judgments.

## 11. Transport, continuation and accounting

The initial run stopped at **188 calls / 51,046 charged completion tokens** after three consecutive TLS BAD_RECORD_MAC errors, with four selections frozen and zero final draws. The user explicitly authorized one continuation. Failed slots remained charged and were not retried; later unattempted work proceeded under identical sources/configuration.

The completed run used **867 calls / 160,478 charged completion tokens**, plus **2,239,059 returned input tokens**. All returned model identities were `gpt-6-luna`. There were **845 completed attempts and 22 transport failures**, split into fourteen search and eight final failures. Final execution included seven recovery calls: six succeeded and one failed. The remaining chalk unknown is a transport failure, not a negative observation or valid visual uncertainty.

All selections froze at call **580**, followed by **287 final calls**. There were zero semantic-audit, Sol-proposer or model-readout calls, no automatic schema repair, no model substitution and no certificate-verification changes.

Approved ceilings: 3,600 calls / 4,608,000 completion tokens. Each case-arm had 107 search and 42 final calls, with 1,008 final calls / 1,032,192 tokens reserved globally. Caps were 1,024 tokens per checker, 2,048 per compiler/gradient/discovery and 4,096 per proposal. Actual call use was 24.1% of the ceiling.

## 12. Historical comparison

| Saved experiment / arm | Selected draw accuracy | All-five-correct case ratio |
|---|---:|---:|
| v5 counting, Luna-only | 44/60 (73.3%) | 8/12 (66.7%) |
| v5 counting, Luna→Sol | 36/60 (60.0%) | 7/12 (58.3%) |
| v6 endpoints, Luna-only | 52/60 (86.7%) | 8/12 (66.7%), after recovery |
| v6 endpoints, Luna→Sol | 42/60 (70.0%) | 6/12 (50.0%), after recovery |
| v7 paired binary | 35/60 (58.3%) | 7/12 (58.3%), after recovery |
| v7 fulfillment | 48/60 (80.0%) | 8/12 (66.7%), after recovery |

The same case identities appear across these experiments, but compiler prompts, observation formats, criteria, search/confirmation rules and transport-recovery policies differ. They are descriptive comparisons. **V7 fulfillment did not beat the prior v6 Luna-only draw accuracy, and did not increase its perfect-case ratio.** The fresh paired binary baseline is strict completeness from numerical scores, not the prior Boolean judge.

## 13. Verification and reproducibility

Before live execution: **1,390 offline unit tests passed, 23 skipped**; all 22 focused fulfillment tests passed. A directly measured synthetic pixel demo, with zero model calls, verified 0/.5/.95/1 mapped to nonsatisfied/partial/satisfied/satisfied, while strict binary stayed nonsatisfied until full completion.

After completion, current-source and pinned-source replay passed with model calls forbidden. Independent verification recomputed exact rational bounds and both readouts, checked protected mass and common seed parity, label/mode/weight isolation, original image hashes/source groups, final freeze, unique durable slots and both-attempt recovery costs. Replays preserved results and accounting. No final outcome changed a selected program or threshold.

```bash
.venv/bin/python logs/exps/261009-fulfillment-v7/analyze_saved_run.py --replay
.venv/bin/python logs/exps/261009-fulfillment-v7/replay_frozen_analysis.py
.venv/bin/python logs/exps/261009-fulfillment-v7/generate_complete_report.py
```

Saved programs execute their original bindings, anchors, weights and thresholds. Previous v2–v6 artifacts retain their explicit version dispatch. No commit or push was made.

## 14. Conclusions and next experiments

1. Retain fulfillment as a useful representation of incomplete individual conditions; its partial-case benefit is demonstrated within this graded pair.
2. Do not assume softer thresholds improve every existing program. Nonsatisfied anchors/bindings need to distinguish genuine requested completion from unrelated/source features.
3. Replace overly broad lexical rejection with a typed distinction between graded endpoint questions and generic helper progress, and evaluate any relaxation separately. Do not treat endpoint paraphrases as automatically equivalent without explicit provenance.
4. Review jacket and frog images/annotations and the exact saved criteria; do not relabel solely to match the model. Fixed aggregation cannot correct a consistently wrong degree estimate.
5. Address transport reliability before expanding repeated image calls. Preserve raw/effective metrics and failed-slot accounting; never selectively resample valid wrong answers.
6. If testing decomposition itself, explicitly compare grounded multi-condition versus broad graded programs. Ten single-condition seeds in this experiment cannot establish a tree advantage.
7. Freeze any revised anchors/thresholds before a new evaluation. No numerical fulfillment ground truth was available here; subjective degree and reported confidence are not calibrated.

The result supports **scoring-aware local fulfillment optimization**, while leaving semantic correctness, calibration and cross-case generalization unproven.

## 15. Artifact index

- [Frozen manifest and exact case/image identities](../../logs/exps/261009-fulfillment-v7/manifest.json)
- [Machine-readable final results](../../logs/exps/261009-fulfillment-v7/results.json)
- [Summary](../../logs/exps/261009-fulfillment-v7/summary.json)
- [Class metrics](../../logs/exps/261009-fulfillment-v7/class_metrics.json)
- [Usage by returned model](../../logs/exps/261009-fulfillment-v7/usage_by_model.json)
- [Independent protocol verification](../../logs/exps/261009-fulfillment-v7/protocol_verification.json)
- [Frozen-selection hashes](../../logs/exps/261009-fulfillment-v7/selection_freeze.json)
- [Complete saved leaf bundle](../../logs/exps/261009-fulfillment-v7/leaves.json)
- [Full machine-readable report details](../../logs/exps/261009-fulfillment-v7/complete_report_statistics.json)
- [Earlier v6 report](calitree_counting_endpoints_v6.md)
- [TLS diagnostic findings](calitree_tls_diagnostics.md)

## Appendix: every selected question, weight, anchor, score and confidence

'''
    text+='\n'.join(details)+'\n'
    OUT.write_text(text)
    (P/'complete_report_statistics.json').write_text(json.dumps({'summary':summary,'search':search,'cases':machine},indent=2)+'\n')
    print(json.dumps({'report':str(OUT),'cases':len(machine),'arms':m['arms'],'words':len(text.split())}))


if __name__=='__main__':main()
