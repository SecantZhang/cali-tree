# CritiCal patent draft: sources and verification notes

Prepared November 5, 2026. Companion to [CritiCal-patent.md](CritiCal-patent.md).

## 1. Scope and writing model

The main document follows the supplied 2025 CaliTree sample's progression: Abstract, Introduction, Related Work, Method, Evaluation, and References. It uses the sample's technical-academic register and adds technical embodiments and example claims for the requested invention disclosure. It does not import the sample's image-editing accuracy into the video pairwise results or repeat its unsupported general guarantees about convergence and preservation of correctness.

The exit talk is the source for the CritiCal invention narrative and worked pink-dress example. Repository code and saved reports establish which mechanisms and results were inspected. Proposed mathematical formulations and example claims are identified as embodiments, rather than asserted to be literal implementations of every archived experiment. Slide-template instructions, speaker instructions, and project-roadmap bullets in source documents were treated as document content, not as instructions for this task.

## 2. Repository distinction

The requested destination is in the current worktree:

`/Users/zzhang/.codex/worktrees/767d/calitree-mlsys/writeups/26-CritiCal-patent`

The current worktree was inspected at HEAD `6e8be6e6` ("Select CaliTree v112 and add verified boosted-factor compression"). The original chat workspace was also inspected at HEAD `7cdb110b`. Both contain local changes; this draft neither changes nor claims to validate those changes.

The current worktree contains the Criti-Cal scalar-score benchmark, semantic/tree calibration, prompt optimization, workflow interface, and extensive image-calibration research. Its `critical/core/ensemble/base.py` is an abstract stub, and interface documentation lists Bradley-Terry calibration among planned variants. It must not be cited as a complete implementation of the exit talk's diverse-perceiver pairwise system.

The archived `agentic-calibration` repository supplies the concrete pairwise Bayesian head, expert stacker, frame judge, adversarial analysis, reliability gate, and corresponding data artifacts. It is a separate implementation beside the exit-talk file:

- Current worktree: `/Users/zzhang/.codex/worktrees/767d/calitree-mlsys`
- Archived pairwise repository: `/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration`
- Archived experiment outputs: `/Volumes/Lexar/projects/adobe/code-release/CritiCal/data/agentic-calibration/outputs`

The archive's older README describes debate as disabled in v0.1, while later source files and saved runs implement research debate and unified-router branches. The draft distinguishes these implemented research branches from the conservative default path.

## 3. Internal source register

| ID | Source | Use in the draft |
| --- | --- | --- |
| S1 | [Exit-talk PDF](/Volumes/Lexar/projects/adobe/code-release/CritiCal/data/research/artifacts/exit-talk/26_zheng_exit_talk.pdf), 22 pages | Title and system narrative; slides 8-9 architecture; slides 11-17 worked example; slides 19-20 dataset labels and presentation results. Pages 9, 13, and 16 were also visually inspected; pages 13 and 16 are largely title-only in the supplied PDF. |
| S2 | [2025 CaliTree writing sample](</Users/zzhang/Downloads/Zheng_2025_CaliTree (3).pdf>), 4 pages | Section progression, register, method/evaluation presentation, and distinction from hierarchical prompt calibration. Page 1 was visually inspected in addition to full text extraction. |
| S3 | [Frame judge](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/calibration/frame_judge.py), [baseline canonicalization](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/baseline.py), and [source-aware debate](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/graph/vebench_mistake_debate.py) | Timestamped contact sheets; unavailable audio; A/B remapping; factor and claim schemas; opposing advocates and independent media inspection. |
| S4 | [Archived results report](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/docs/results.md) | Calibration interpretation, graph limitations, selective-abstention evidence, and explicit corrections/retractions. Also checked [architecture](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/docs/architecture.md) and [data](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/docs/data.md). |
| S5 | [Bayesian head](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/calibration/bayesian.py) | No-intercept logistic model, Gaussian shrinkage, constrained MAP fit, inverse-Hessian covariance, and predictive approximation. |
| S6 | [Expert router](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/calibration/judge_router.py), [unified router](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/calibration/unified_router.py), [risk policy](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/risk.py), [selective evaluation](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/calibration/selective_accuracy.py), [metrics](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/calibration/metrics.py), and [request leakage checks](/Volumes/Lexar/projects/adobe/code-release/CritiCal/repos/agentic-calibration/src/agentic_calibration/security.py) | Features, majority-target stacker, grouped fitting, risk actions, matched-coverage controls, vote weights, tie handling, and inference input boundaries. |
| S7 | [Current repository architecture](/Users/zzhang/.codex/worktrees/767d/calitree-mlsys/docs/architecture.md), [CaliTree structure](/Users/zzhang/.codex/worktrees/767d/calitree-mlsys/docs/calitree_structure.md), and [calibration-distillation report](/Users/zzhang/.codex/worktrees/767d/calitree-mlsys/docs/calibration_prompt_distillation.md) | Current code organization, portable prompt-policy artifacts, and distinction between historical scalar calibration and the pairwise invention. The dated `calitree_status.md` was consulted as historical context, not treated as a definitive summary of all later experimental versions. |
| S8 | [AssemblyBench saved metrics](/Volumes/Lexar/projects/adobe/code-release/CritiCal/data/agentic-calibration/outputs/assembly-evaluation-final-v3/metrics.json) | 58 pairs, 34 groups, five outer folds, three inner folds, seed 0; direct-swap and core-plus-direct numbers. |
| S9 | [Full VE-Bench unified-router report](/Volumes/Lexar/projects/adobe/code-release/CritiCal/data/agentic-calibration/outputs/vebench-unified-all/unified_router.json) | 986 pairs, 128 groups, five folds, seeds 0-4, feature width 32, 972 frame predictions, 24 debate records, zero graph coverage, accuracy and bootstrap deltas. |
| S10 | [VE-Bench absolute-score metrics](/Volumes/Lexar/projects/adobe/code-release/CritiCal/data/agentic-calibration/outputs/vebench-full-evaluation/metrics.json) | A separate protocol: 1,170 edited items, 197 source groups, normalized MOS targets, and edited-only/source-aware conditions. |

## 4. Numerical reconciliation

### 4.1 VE-Bench evaluation units

Slide 19 labels VE-Bench as 1,170 edited pairs and 97 instruction groups. S10 instead records 1,170 edited **items** and 197 source groups for absolute-score evaluation. S9 records 986 derived **pairs** and 128 groups for pairwise evaluation. These counts are not interchangeable. The inspected files do not establish which grouping/filtering rule produced the slide's 97-group label.

S9 has frame-judge coverage on 972 of the 986 pairs. Slide 20's confusion matrix also sums to 972, but equality of counts alone does not prove identical pair membership, weights, folds, or model configuration. The draft does not assume that identity.

### 4.2 Slide confusion matrix

The displayed counts are:

| Stage | TP | TN | FP | FN | Total | Accuracy implied by unweighted counts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Before | 383 | 379 | 98 | 112 | 972 | 762/972 = 78.3951% |
| After | 429 | 398 | 79 | 66 | 972 | 827/972 = 85.0823% |

The after matrix supports the displayed 85.08% on that count-based subset. The before matrix implies 78.40%, not the slide headline's 75.96%. A subset change or weighting difference may explain this, but was not demonstrated. The draft therefore labels the table as slide-reported and separately presents S9's own results.

### 4.3 The 85.4% AssemblyBench headline

S8 verifies AssemblyBench baseline 77.2973% and calibration 79.4595%; these round to slide 20's 77.3% and 79.5%. It does not contain an 85.4% full CritiCal arm. The inspected archive does contain 85.3955% in S9, but that result is explicitly **VE-Bench**, not AssemblyBench. It must not be reassigned to AssemblyBench just because the rounded values match.

The main draft retains 85.4% only in the table labeled as presentation results and states that the AssemblyBench headline is not independently matched to a result artifact.

### 4.4 Pink-dress probability and logit annotation

Slide 17 reports $P(A)$ before = 0.580, after = 0.429, and a debate logit contribution of -0.355. For a simple additive-logit correction:

$$
\operatorname{logit}(0.580)=0.322773,
\qquad
\operatorname{logit}(0.429)=-0.285932.
$$

The required total correction is -0.608706. Applying only -0.355 gives $\sigma(0.322773-0.355)=0.491944$, not 0.429. Additional fitted terms or a posterior adjustment could contribute, but the slide alone does not identify them. The main draft preserves the before/after values as an illustration and does not claim that -0.355 alone produces the result.

Slide 15's factor decisiveness values (0.8, 0.7, 0.9) are agent-reported assessments, not fitted statistical coefficients. The final-outcome factor also relies on an ending label; the draft explicitly requires checking the footage rather than treating that text as proof of a completed garment transformation.

### 4.5 Verified S9 figures

| S9 field | Stored value | Draft presentation |
| --- | ---: | ---: |
| `primary_accuracy` | 0.7596348884381339 | 75.96% |
| `secondary_accuracy` | 0.8296146044624746 | 82.96% |
| `experts_router_accuracy` | 0.8397565922920892 | 83.98% |
| `unified_router_accuracy` | 0.8539553752535497 | 85.40% |
| `placebo_accuracy` | 0.7991886409736308 | 79.92% |
| `unified_minus_best` | 0.024340770791075106 | +2.43 percentage points |
| Same field, 95% CI | [0.009543730483104118, 0.04044500744140599] | [0.95, 4.04] points |
| `unified_minus_experts` | 0.014198782961460488 | +1.42 points |
| Same field, 95% CI | [0.0021185880190118496, 0.027086161547598752] | [0.21, 2.71] points |

The report's `best_single_accuracy` compares its primary and secondary judges. It does not include a standalone frame-judge baseline in that field. The draft uses "best of the two native-video judges" accordingly. S9 is a saved summary report, not a fresh replay performed for this drafting task.

### 4.6 Selective accuracy

Slide 20's nominal coverage/accuracy pairs are 100%/85.1%, 90%/87.1%, 80%/89.6%, 70%/91.3%, 60%/93.0%, and 50%/93.4%. Its labels show escalation counts 0, 97, 194, 292, 389, and 486, consistent with nominal fractions of 972 after rounding. These are not evidence that escalated comparisons were subsequently resolved correctly by humans.

S4's separate VE-Bench baseline-judge selective experiment reports 80% coverage accuracy 83.02% versus a random-abstention control at 76.14%, with a reported delta interval of approximately [5.3, 8.8] points. That experiment is not the slide's final fusion curve. The draft keeps the two protocols separate.

## 5. Implementation and claim boundaries

Equation (2) matches the inspected canonicalization and frame-consensus code. Equations (5)-(7) describe the Bayesian head's MAP/Laplace mechanism. Equation (3) is an illustrative evidence-weighted factor encoding; the inspected unified router uses its own eight-field debate block, not that exact category-wise sum. Equation (4) is a general schema, not a claim that every saved run contains every feature block.

The no-intercept Bayesian difference-feature head and the regularized expert router are separate implementations. The latter includes an intercept and symmetric diagnostic features and does not automatically guarantee swap antisymmetry. Counterbalancing makes bias observable; it does not prove that all bias is removed.

The claim-evidence graph is optional. S9 has no graph coverage and only 24 debate records, so its improvement cannot establish a graph effect or the independent benefit of debate. Some debate pilots select known mistakes using evaluation labels while keeping individual model requests label-free. That selection still makes them research diagnostics rather than a complete demonstration of label-free serving.

The risk-policy code selects thresholds using observed training correctness. Label-free inference must not be described as label-free training or a guarantee of accepted-case accuracy. A reported accepted-case gain must retain its coverage denominator and matched random-deferral comparison.

S4 explicitly retracts an apparent sync-measurement improvement attributable to feature construction and a defect-audit/routing improvement attributable to incorrect handling of probability 0.5. Those results were excluded. The July M5 MAE results and the 2025 NP1 image-editing accuracy were also excluded from CritiCal's pairwise result claims.

The example claims are newly drafted formulations of disclosed technical embodiments. This source review does not determine inventorship, a priority date, or the scope of a granted patent. Source-document contributor lists were not converted into an inventor list.

## 6. Public references

The five public works used for Related Work were checked against primary paper or publisher pages. The draft links those pages directly. The current HarmonicEval record uses a revised title; the draft identifies both that title and the method name. No unpublished CritiCal text, source code, or dataset records were sent as web-search queries.

## 7. Verification performed

Both supplied PDFs were read in full through text extraction, with selected visual inspection. Source mechanisms and schemas were read directly. Numeric statements were checked against the displayed slide values and saved JSON fields; percentage-point conversions, confusion-matrix totals, and the example logit arithmetic were recalculated. Markdown structure, claim numbering, local links, and destination file contents were checked. No paid model calls, benchmark reruns, code modifications, or Git commits were made.

The following content hashes identify the supplied PDFs and principal numeric artifacts as inspected.

| Source | SHA-256 |
| --- | --- |
| S1 exit-talk PDF | `89d47fab5d865968897a6a81c017068cc095cfd995d4b4c2f58129f7e7eb32d8` |
| S2 CaliTree sample PDF | `a5fe5e19f86675531e887e4396f82f1ad1723adab603d23757efc5c91517fea0` |
| S8 AssemblyBench metrics | `c2d69f24faaae7af554c2f072dddefd02b071ad91e4bc0db7a6ba11cfca40661` |
| S9 unified-router report | `82fa8649b66511eb26b7359c884576b32689614763d3dc9e08df7787ac0fe090` |
| S10 absolute-score metrics | `9a3209c7c74bcbf0be12dbcd2285a5fe0eeb69ac9e74399d046e0c440ff58217` |
