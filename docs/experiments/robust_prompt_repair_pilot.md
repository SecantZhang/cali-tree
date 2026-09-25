# Repeated-evaluation GEPA repair pilot

## Completed results

All 100 mutation rounds completed. Final evaluation contains exactly 900 fresh
judgments: ten cases × three arms × 30 draws. There are 2,106 completed calls total
(100 reflection and 2,006 judge calls), no invalid judgments, and estimated list
cost **$2.769588**, below the $15 cap.

| Arm | Final correct / 300 | Accuracy | Pairwise disagreement | All-30-correct cases | Accepted edits |
|---|---:|---:|---:|---:|---:|
| Unchanged | 224 | 74.7% | 28.3% | 3 | 0 |
| Single-draw repair | 266 | 88.7% | 9.8% | 3 | 6 |
| Repeated repair | 241 | 80.3% | 22.1% | 4 | 2 |

Repeated repair improved over unchanged by **5.7 percentage points** (descriptive
paired case-bootstrap 95% interval **[-2.3, +19.0]**), but trailed single-draw repair
by **8.3 points** (**[-27.0, +8.7]**). Neither interval excludes zero. This pilot does
not establish a population ranking or an advantage from repeated evaluation.

### What happened

- Eight repeated-repair candidates passed screening and contract checks; fresh
  confirmation rejected six. Two edits were adopted, on C05 and C10.
- **C10:** repeated repair achieved 30/30 correct, versus 11/30 unchanged and 27/30
  single-draw repair. The revised rubric explicitly addressed duplicated objects
  and imprecise placement.
- **C05:** repeated repair scored 10/10 in confirmation but only 9/30 in final
  evaluation. Unchanged scored 10/30; single-draw repair scored 29/30. An audit
  verified identical logged request content, settings, images, and returned model
  version between confirmation and final calls. Perfect small-batch confirmation
  did not establish reliable correctness.
- **C08:** single-draw repair regressed to 6/30, versus 17/30 unchanged. Repeated
  repair retained its original prompt and scored 18/30.
- Single-draw repair changed five final prompts (six accepted edits); repeated
  repair changed two. Differences between arms on unchanged identical prompts
  reflect fresh sampling, not prompt optimization effects.

These observations support further work on confirmation design, but do not show
that this repeated-feedback prototype solves robustness. Future evaluation should
separate feedback aggregation from the acceptance gate, replicate optimization
trajectories, and assess confirmation across multiple batches. Fresh API calls do
not by themselves establish statistical independence or stationarity.

### Verification and interruptions

- **58 offline experiment tests passed**, including real GEPA with mocked LLMs.
- Independent audit verified all input/code hashes, 100 rounds, 900 exact final
  identities, 2,106 unique provider response IDs, prompt lineages, acceptance gates,
  search-before-final ordering, and accuracy recomputed from raw responses.
- 190 transport-failure records were logged, including the initial sandboxed
  network failure. Two final-evaluation interruptions required resuming; all
  completed outputs were retained and only missing requests were completed.
- Estimated costs exclude unknown charges for failed requests and cache discounts.
- Returned model ID throughout: `gpt-5.4-mini-2026-03-17`.

[Verification record](../../logs/exps/260924-09:37:00-exps/verification.json) ·
[C05 confirmation audit](../../logs/exps/260924-09:37:00-exps/confirmation_audit.json)

## Question

Does repeated correctness feedback and independent confirmation improve the
reliability of per-case prompt repair on the existing ten-case subset?

This is an in-sample diagnostic: ten previously selected AURORA source/instruction
cases, each with its own existing prompt. It is not a shared-prompt experiment.
For a single case, the proposed mean-plus-tail loss is only a rescaling of error;
therefore this prototype optimizes repeated correctness without a tail penalty.

## Frozen protocol

- Official GEPA 0.1.4, isolated Python 3.12 environment.
- Official OpenAI GPT-5.4-mini for judging and reflection; reasoning none.
- Judges: temperature 0.3, maximum 512 completion tokens.
- Reflection: temperature 0, maximum 4,096 completion tokens.
- Unchanged prompt; single-draw GEPA; five-draw GEPA with fresh confirmation.
- Five mutation proposals per case and repair method, one search trajectory.
- GEPA current-best, no merging, no response caching, no perfect-score skipping.
- Each round invokes one official GEPA mutation. Its fresh training-parent and
  child evaluations determine strict screening improvement. Initial and conditional
  validation evaluations are also logged and billed; no outcome is cherry-picked.
- Repeated repair additionally requires strictly better correctness in ten fresh
  candidate and ten fresh incumbent draws. Ties retain the incumbent.
- Prompts that repeat identifiers/instructions, omit the output contract, or
  explicitly prescribe an unconditional label are rejected. These syntactic
  safeguards cannot prove semantic generalization.
- No early stopping on perfect observed correctness. Final prompts are frozen
  before 30 fresh draws per case/arm (900 final judgments).
- Scheduling/order seed 44; model outputs remain stochastic.

Both repair arms receive five proposals; repeated repair consumes more calls.
Results cannot establish superiority at equal evaluation cost. Human labels are
available to feedback construction and local scoring, but never included as target
fields in judge requests. All rationales are observed model explanations, not
verified internal reasoning or independent annotations.

## Reproduction

```bash
/opt/homebrew/bin/python3.12 -m venv .venv-gepa
.venv-gepa/bin/python -m pip install 'gepa==0.1.4' 'requests>=2.31'
PYTHONPATH=. .venv/bin/python run/robust_prompt_repair_pilot.py \
  --output-dir logs/exps/260924-09:37:00-exps --dry-run
PYTHONPATH=. .venv/bin/python run/robust_prompt_repair_pilot.py \
  --output-dir logs/exps/260924-09:37:00-exps --live --resume
PYTHONPATH=. .venv/bin/python run/robust_prompt_repair_pilot.py \
  --output-dir logs/exps/260924-09:37:00-exps --report
```

The run refuses changed configurations, source hashes, image hashes, or completed
request identities. Live calls require explicit gating. The $15 estimated-cost cap
reserves conservative input/image and maximum-output allowances for pending calls.
Prices are configured standard list estimates; cache discounts and unknown failed
request billing are excluded. A budget or persistent transport failure leaves the
run incomplete and resumable; completed malformed judgments remain incorrect.

The dry-run upper bound is 3,100 judge calls plus 100 reflection calls, estimated
at $13.70 under the documented planning token assumptions. Actual usage is logged.
The first launch, `260924-09:35:00-exps`, failed before any API call because resolving
the virtualenv Python symlink selected the base interpreter. The runner now
preserves that symlink; the live run uses a new frozen configuration.

## Artifacts and interpretation

- [Generated report](../../logs/exps/260924-09:37:00-exps/report.md)
- [Metrics and costs](../../logs/exps/260924-09:37:00-exps/summary.json)
- [Frozen configuration](../../logs/exps/260924-09:37:00-exps/run_config.json)
- [Runner](../../run/robust_prompt_repair_pilot.py)
- [Offline tests](../../tests/unit/experiments/test_robust_prompt_repair_pilot.py)

Report mean and per-case accuracy, class recalls, pairwise disagreement, stable
wrong cases, all-30-correct cases, accepted edits, calls, tokens, and cost.
Descriptive paired bootstrap intervals resample the ten cases, not individual
repetitions. Final evaluation never selects or revises prompts.
