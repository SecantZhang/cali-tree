# DSG decomposition does not reliably preserve the original CaliTree score

On 12 previously observed AURORA cases, with five fresh executions per format, the DSG observation graph plus an original-rubric readout matched **44/60 paired labels (73.3%)**. Only **3/12 cases matched on all five repeats**. This implementation is not a score-preserving replacement for the original scorer. It often retains the dominant judgment, but introduces unresolved cases and some changed judgments.

“Original” means the exact saved, label-free seed program from the prior comparison, including its bindings and executable checker template. It does not mean a human annotation, the optimized program, or a new monolithic prompt. Two original programs contain supporting checks. This distinction was fixed before the live run.

## Main results

| Measure | Result |
|---|---:|
| Exact paired label agreement, unresolved counted as non-match | 44/60 = 73.3% |
| Pairs where both formats resolve | 50/60 = 83.3% |
| Agreement among resolved pairs, pooled descriptive count | 44/50 = 88.0% |
| Mean per-case resolved-only agreement | 90.0% |
| Cases matching on all five repeats | 3/12 |
| Cases with matching modes among resolved repeats | 11/12 |
| Original resolved coverage | 59/60 = 98.3% |
| DSG readout resolved coverage | 50/60 = 83.3% |
| Mean per-case ordinal absolute difference, resolved pairs | 0.067 on the 0–1 label scale |
| All-cross-repeat agreement within cases | 72.7% |
| Agreement on the nine multi-question cases | 32/45 = 71.1% |

Mode agreement is a weaker result than repeat preservation: the DVD case's DSG mode uses only one resolved draw, and the mug case has a tie and no unique DSG mode. The three global-style cases remain single questions and average 80% paired agreement. They do not test multi-question decomposition. The 90% conditional figure weights each case equally; the 88% figure pools the 50 resolved pairs. Neither replaces the 73.3% full-coverage result.

There are six disagreements where both arms resolve, and ten unresolved paired comparisons. The original scorer is itself variable: 9/12 cases return the same resolved label on all five draws, versus 5/12 for DSG. Within-case pair disagreement, counting unresolved as disagreement, is 12.5% original versus 36.7% DSG. Among resolved within-case pairs, the descriptive counts are 11/116 (9.5%) versus 12/88 (13.6%). Much of the operational gap therefore comes from coverage loss. These are repeated measurements of 12 cases, not 60 independent test cases; this small exploratory run does not establish a population-level effect.

## Per-case scores

`?` means unresolved. Native DSG fractions are shown alongside labels for transparency, not as a calibrated conversion to yes/partial/no.

| Case | Instruction | Questions | Original labels | DSG readout labels | Native DSG fractions | Paired agreement |
|---|---|---:|---|---|---|---:|
| 1 | transform the black DVD into a white DVD | 2 | yes,yes,yes,partial,? | ?,?,yes,?,? | 0.5,?,1.0,0.5,0.5 | 20% |
| 2 | Make her close her jacket fully | 3 | no,no,no,no,no | no,?,no,no,no | 0.667,0.667,0.667,0.667,0.667 | 80% |
| 3 | Change the image into pencil drawing | 1 | yes,yes,yes,yes,yes | yes,yes,partial,yes,yes | 1.0,1.0,0.0,1.0,1.0 | 80% |
| 4 | Give the woman a helmet | 3 | yes,yes,yes,yes,yes | ?,yes,yes,yes,? | 0.333,1.0,1.0,1.0,0.333 | 60% |
| 5 | Change the background into a basketball court | 2 | yes,yes,yes,yes,partial | yes,yes,yes,yes,yes | 1.0,1.0,1.0,1.0,1.0 | 80% |
| 6 | Move the mug to the right of the headphones | 3 | yes,yes,yes,yes,yes | no,yes,yes,no,partial | 0.667,1.0,1.0,0.667,0.667 | 40% |
| 7 | Move the book behind the flower | 3 | no,no,no,no,no | no,?,?,no,no | 0.667,0.667,?,0.667,0.667 | 60% |
| 8 | Stuffing the paper into the cup | 3 | no,no,no,no,no | no,no,no,no,no | 0.0,0.333,0.333,0.333,0.333 | 100% |
| 9 | Make this look like a comic book photo | 1 | no,no,no,no,no | no,no,?,no,no | 0.0,0.0,?,0.0,0.0 | 80% |
| 10 | Turn the image into a drawing made from chalk | 1 | yes,yes,yes,yes,partial | yes,yes,yes,yes,yes | 1.0,1.0,1.0,1.0,1.0 | 80% |
| 11 | Put a frog in the toilet | 3 | yes,yes,yes,yes,yes | yes,yes,yes,yes,yes | 1.0,1.0,1.0,1.0,1.0 | 100% |
| 12 | the small gray rubber cylinder becomes brown | 2 | yes,yes,yes,yes,yes | yes,yes,yes,yes,yes | 1.0,1.0,1.0,1.0,1.0 | 100% |

## Why the scoring changes

**Supporting facts are not completed edits.** For “Make her close her jacket fully,” DSG asks whether the woman exists, whether her jacket exists, and whether the jacket is fully closed. Every native fraction is 2/3 because the first two answers are yes and the last is no. The original program returns `no` five times; the original-rubric readout returns `no` four times and unresolved once. A native score of 2/3 therefore does not mean two-thirds of the requested closure was completed. Across all 60 pairs, the native fraction numerically equals the original ordinal label only 34 times (56.7%), a diagnostic comparison of different constructs.

**Binary end-state questions can lose progress evidence.** One jacket readout says the observation establishes that the jacket is open, but does not establish whether it is more closed than before. In the pencil case, one binary answer is no while the supporting description indicates some pencil-like styling; the readout returns `partial` while the native fraction is zero. Keeping visual evidence text helps, but does not guarantee preservation of the original progress rubric.

**Separate questions can disagree about the referent.** DVD observations alternate between identifying a white disc and being unable to distinguish the referenced disc from a second one. Helmet observations sometimes identify a helmet but disagree about whether its wearer is the referenced woman. These produce unresolved readouts. Those are model observations, not independently verified image facts.

**Some resolved judgments also change.** The mug-right-of-headphones case returns `yes` on every original execution, while DSG returns `no, yes, yes, no, partial`. This cannot be explained by transport failures alone. The pilot identifies a fidelity failure; it does not establish which judgment is visually correct.

## Method and limits

The implementation follows the three-stage tuple → question → dependency structure described by [Cho et al., ICLR 2024](https://arxiv.org/abs/2310.18235) and the [DSG project](https://google.github.io/dsg/). Negative prerequisites mask dependent questions to zero. The native score averages all effective binary answers. This is an independent adaptation for source/edited image pairs, with explicit unknowns, requested/support roles, and a separate text-only readout of the original rubric. It is not an official-library replication, and the readout is not the published DSG score.

Each graph contains at most four questions; actual graphs have one to three. All 12 graphs are structurally valid. A label-blind diagnostic audit approves four, flags eight, and never filters which cases execute. Some audit complaints conflict with DSG's intended entity prerequisites; these judgments are evidence, not ground truth. The approved subset has 85% paired agreement, but is a small diagnostic subset containing all three singleton style cases. It is not the primary result.

Questions are generated without images or reference labels. VQA calls see the source/edited pair and one question; the readout sees the graph, observations, and original rubric, with no images, original prediction, or human label. No optimization, score-guided repair, threshold fitting, or favorable-candidate selection occurs. The runner completes preparation before scoring and freezes each graph. The implementation correction described below completed two previously rejected graphs after some first-case scoring draws had run; those earlier draws were retained, and no scoring feedback informed the correction. Arm order alternates by case and repeat. Human-reference agreement is secondary: original 30/60 (50.0%), DSG 27/60 (45.0%). Preserving the original score would not itself establish correctness.

For CaliTree, this result supports treating DSG as a candidate evidence decomposition while preserving requested-outcome aggregation. It does not support replacing the rubric with the average of all question answers. A future test could explicitly preserve target identity and source-to-edited progress in the question contract, then measure fidelity again under a separately frozen protocol. This run did not tune those rules after seeing the results.

## Execution, failures and validation

GPT-6 Luna was used throughout, temperature zero and reasoning `none`. All 302 completed provider responses returned `gpt-6-luna`. The 306 cumulative attempts used 382,951 measured input tokens and 14,298 measured completion tokens. Conservative completion accounting is 18,394 tokens, including four failed/interrupted slots charged at their 1,024-token caps. This is within the approved 450-call / 512,000-completion-token ceilings. No dollar cost is inferred from token counts.

| Phase | Calls | Measured input tokens | Measured completion tokens |
|---|---:|---:|---:|
| Tuples, questions, dependencies and diagnostic audits | 48 | 43,191 | 4,115 |
| Original saved-program scoring | 70 | 99,897 | 3,143 |
| DSG VQA plus original-rubric readout | 188 | 239,863 | 7,040 |

The DSG phase consists of 128 image-question calls and 60 text-only readouts. Three SSL transport errors occurred: one original check, one book-relation question, and one comic-style question. One DVD readout was interrupted during the implementation correction below. Each slot received one HTTP attempt; none was retried. Seven of the ten unresolved DSG draws instead arise from modeled uncertainty or insufficient observation evidence, with no call error.

The first snapshot rejected valid hyphenated tuple IDs due to an undocumented character restriction. That implementation defect was corrected without changing prompts, scores, or thresholds. All 57 earlier attempts, including completed scoring draws and the interrupted readout, were retained in the replacement run; the two saved tuple responses were reused exactly, followed only by their unattempted stages. This is recorded in `migration.json`; v1 and its source snapshot remain intact. The correction was unrelated to observed score agreement.

Offline verification: **1,142 unit tests passed, 23 skipped** after the correction (52 existing warnings). The new DSG suite has 16 tests. All **120 final scoring draws** reproduced their saved semantic outputs from the durable observations, and completed-run resume made **zero new calls** with an unchanged budget. The verifier checks graph/program identity, frozen source snapshots, image hashes, inherited attempts, model identities, stage caps, media isolation, and budget limits. Branch `codex/decision-program-optimizer` remains at `e27833f`; staging is preserved. No commit or push was made.

## Reproduce and inspect

- [Protocol and commands](../calitree_dsg_fidelity.md)
- [Runtime](../../critical/core/decision/dsg.py), [runner](../../run/calitree_dsg_fidelity.py), [offline tests](../../tests/unit/calitree/test_dsg_fidelity.py)
- [Frozen manifest](../../logs/exps/261006-dsg-fidelity-v2/manifest.json), [migration record](../../logs/exps/261006-dsg-fidelity-v2/migration.json)
- [Per-case CSV](../../logs/exps/261006-dsg-fidelity-v2/per_case.csv), [discordant traces](../../logs/exps/261006-dsg-fidelity-v2/discordances.json)
- [Audit and usage](../../logs/exps/261006-dsg-fidelity-v2/audit.json), [all results](../../logs/exps/261006-dsg-fidelity-v2/results.json)

```sh
PYTHONPATH=. .venv/bin/python logs/exps/261006-dsg-fidelity-v2/verify_run.py
PYTHONPATH=. .venv/bin/python logs/exps/261006-dsg-fidelity-v2/analyze.py
```

Both commands are offline. Provider jobs, exact graphs, observations, full LLM history, source snapshots, and the original checkpoint are under `logs/exps/261006-dsg-fidelity-v2/`. Existing earlier optimizer and ablation artifacts are preserved.
