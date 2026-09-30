# Simple real-model CaliTree tests

The actual cached optimized AURORA prompt diagnostic is documented in
[reports/optimized_aurora_20260926.md](reports/optimized_aurora_20260926.md).
Unlike the synthetic tests below, it uses public source/edited images and
records unsupported decomposition semantics without substituting grading rules.

The open-vocabulary image strategy and real AURORA development experiments are
described in [reports/vision_decomposition_progress_20260926.md](reports/vision_decomposition_progress_20260926.md).
Its live three-arm tests are in `test_twoway_vision_aurora.py`; the default
unreviewed strategy and optional review/resolution variants are scored against
the same human-derived labels. Run those tests individually with explicit model
and report-directory arguments; full live-suite runs can make many image calls.

These experiments use the existing production prompt decomposition and merge
implementation, with a real model for every decision comparison. There are no
mocked model responses. They use text evidence, so no datasets, images,
embeddings, or TextGrad setup are needed.

The rubric has two requirements: **red color** and **circular shape**. Both met
means `yes`, exactly one met means `partial`, and neither met means `no`.

| Object | Expected combined decision |
| --- | --- |
| Red circle | yes |
| Red square | partial |
| Blue circle | partial |
| Blue square | no |

## Run individually

From the repository root, using configured provider credentials:

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_prompt_decomposition.py --calitree-live -v -s
.venv/bin/python -m pytest tests/unit/calitree/test_merging_algorithm.py --calitree-live -v -s
```

Without `--calitree-live`, the tests skip and make no network calls. The default
model is the project's `DEFAULT_TEXT_MODEL` (`CRITICAL_TEXT_MODEL`, otherwise
`gpt-4.1`). Override the model/provider explicitly when needed:

```sh
.venv/bin/python -m pytest tests/unit/calitree --calitree-live --calitree-engine gemini --calitree-model gemini-2.5-pro -v -s
```

## What gets checked

- **Prompt decomposition:** extract criteria, priorities, and constraints using
  the current default `calitree_v2` template. Recompose them as a rubric and compare
  all four decisions against the original prompt and expected labels. The
  original and recomposed rubrics must each score 4/4. Normal CaliTree uses these
  components for clustering; recomposing them for judging is this experiment's
  semantic-preservation check.
- **Compatible merging:** synthesize a combined rubric from a color-only and a
  shape-only rubric using the production merge template and coordinator. Compare
  source and merged decisions, then require 4/4 fit decisions and perfect balanced
  accuracy on four separate validation records. Prompt optimization is disabled
  to measure synthesis itself.
- **Conflict:** red-only and blue-only requirements for the same object must
  produce a conflict and preserve the separate branches.
- **Dropped requirement:** deliberately evaluate a damaged color-only candidate.
  It fits two easy training cases perfectly, but must fail the generalization
  guard on cases that distinguish color from shape.

The three merge tests can also run individually with their pytest `::test_name`
suffix. The full experiment uses about 15 generation calls with temperature 0.
Model behavior can still vary; failures are useful results, not silently retried
until the model passes.

## Inspect the results

`-s` prints the original, decomposed, and merged prompts plus decision tables.
Markdown and JSON reports are saved under `.cache/calitree-tests/<UTC timestamp>/`.
JSON includes components, judgments and rationales, acceptance decisions, and
exact model request/response records. Files are written before semantic assertions
so a failed quality check remains inspectable. A separate model-call trace is
also saved when a test exits, including when parsing or an API call fails early.

Use `--calitree-report-dir /absolute/path` to choose a report location. Successful
API calls are genuine evidence about these small text cases; they do not measure
image-judging performance or establish generalization beyond this fixture.

## Harder example: interacting rules and exceptions

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_harder_examples.py --calitree-live --calitree-max-tokens 4096 -v -s
```

The harder rubric has color, relative-position, and numeric-count requirements;
strict versus allowed-shade matching; exact versus minimum counts; preservation
vetoes with explicit exceptions; unknown evidence; unrequested checks; and
untrusted caption instructions. A successful edit cannot override an unauthorized
identity or background change, and permission for one change cannot excuse a
different failure.

- Decomposition compares the original and extracted/recomposed rubric on **29
  hand-labeled records**, including eight records with changed targets.
- Merging combines color/position and count rubrics, measures all **21 fit
  records**, applies the production guard, and then checks **all eight validation
  records** independently of the guard's six-record sampling cap.

The harder tests judge one record per model call, matching the production
runtime's evaluation pattern. Four calls run concurrently to reduce latency.
There are up to **143 calls** across both tests, including all source,
fit, and validation comparisons. Unlike the simple experiments, these cases are
not packed together in a single generation, which avoids cross-case interference.
Prompts and labels are saved to
`harder_decomposition.md`, `harder_merging.md`, and `harder_merge_validation.md`,
with full JSON reports alongside them. A failure records the exact mismatched
cases and rationales; the tests do not relax expected labels to make the model pass.

In the initial `gpt-4.1` run with individual judgments, the original rubric got
25/29 cases right and the decomposed rubric got 21/29. The merged rubric got
19/21 fit cases and 6/8 validation cases right, and the production guard rejected
it. Both strict tests failed. These results include baseline-model mistakes;
they do not establish that decomposition or synthesis alone caused every error.

## Two-way prototype: instruction decomposition and individual checks

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_two_way_decomposition.py --calitree-live --calitree-max-tokens 4096 -v -s
```

This test-only prototype takes the same 29 harder records through three arms:

1. Original rubric, judged against the existing structured records.
2. Reference instruction plan, individually checked by the model, aggregated in Python.
3. Natural-language instruction, decomposed by the model without observations or
   labels, then individually checked and aggregated using the same pipeline.

`two_way.py` separates instruction plans, atomic conditions, and aggregation.
Requested color/position/count checks carry their own operator and expected value.
Identity and background permissions remove only their corresponding preservation
checks. Each checker call receives one condition and its observed value; captions,
other evidence, final targets, and other cases are absent. The model returns
`satisfied`, `violated`, or `unknown`; Python decides `no`, `partial`, or `yes`.
Malformed plans/responses fail instead of falling back to an overall judgment.
Identical instruction parses and atomic requests are cached within the experiment.

The reference arm isolates checking from instruction parsing. Assertions check
instruction plans, each atomic result against exact structured predicates, and
all final labels against hand-written targets. Baseline errors are reported but
are not asserted as prototype failures. Twelve offline tests cover aggregation,
scope, permissions, missing evidence, and invalid plans; they run without opt-in.

This prototype uses the harder fixture's hand-specified rubric policy. It does
**not** yet compile arbitrary learned prompts into reducers or modify the
production runtime. The instructions are rendered from structured fixture intent;
these results do not establish quality on unrestricted user wording or images.
Reports include all natural instructions, plans, atomic evidence/rationales,
per-arm mismatches, and raw model calls in `two_way_decomposition.md/json`.

The first live two-way run with `gpt-4.1` passed: original **25/29**,
reference-plan arm **29/29**, and model-plan arm **29/29**. All ten distinct
instruction plans and 29 distinct atomic checks matched their references, using
68 model calls total. The live run passed all 13 tests. This measures the combined
pipeline, not the isolated benefit of parsing: input representation, call
isolation, and deterministic aggregation also differ from the baseline.

## Automatically generated rubric rules

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_generated_rules.py --calitree-live --calitree-max-tokens 4096 -v -s
```

`generated_policy.py` compiles the rubric itself into a JSON policy: supported edit
types, preservation guards, scoped permissions, ordered decision rules, and a
fallback label. The model sees only the rubric, never examples or expected labels.
A validated interpreter executes Boolean combinations, count comparisons, and
guard-status comparisons. Guard statuses require explicit equality, avoiding ambiguous
not-satisfied tests that mix failures with uncertainty or exempt checks. No generated
Python code is executed. Each rule cites
a numbered source line of the rubric, and each final decision records the matched
rule and the facts used. Source grounding is a trace, not proof of equivalence.

The experiment independently decomposes instructions and checks conditions using
the earlier prototype. It replaces the hand-specified reducer with the generated
policy. Applicable edits and preservation checks also come from that policy.
When a generated permission exempts a guard, no evidence check is performed. Its
preservation obligation is logically fulfilled for policy evaluation, and the
trace lists it separately in exempt_guards. This does not assert that preservation
was observed. Actual unknown evidence remains unknown and can trigger a cap.
Missing applicable checks, malformed policies, unknown facts, mixed comparison
types, and permissions bound to the wrong guard fail validation.

Three rubric variants run against the same 29 records, each with independent
expected labels: the original policy, an all-requested-edits-must-succeed policy,
and a color/position-only policy. The variants check whether generated aggregation
and applicability follow changed rubric wording. Twelve offline tests exercise rule
execution, fallback, uncertainty, permission binding, and malformed policies.
Live reports are `generated_rules.md/json`, containing generated policies, per-arm
expected labels, matched-rule traces, decomposition/check errors, and raw calls.
The Markdown table's Expected column is for the original rubric; variant targets
are recorded separately under `targets_by_policy`.

This remains a test-only compiler with a predefined vocabulary of edit conditions
and a bounded rule language. Unsupported rubrics must be rejected explicitly.
It does not yet support arbitrary visual conditions or integrate with production
CaliTree. Passing these examples measures these generated policies, not universal
rubric compilation.

The compiler permits one automatic repair for schema violations, passing the
validation error and previous output back alongside the original rubric. It does
not retry based on incorrect decisions or expose expected labels to generation.
All attempts are retained in the report and raw trace. If the repaired policy is
still invalid, or the rubric is explicitly unsupported, compilation fails.

The final `gpt-4.1` run passed all 13 generated-rule tests. The original, strict
all-edits, and color/position-only generated policies each got **29/29** decisions
correct. Earlier schema failures and incorrect exception/uncertainty handling are
preserved in the experiment reports; the final run used the corrected interpreter
and unchanged hand-written decision targets. These are fixture-specific results.

## Twenty hard holdout cases

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_twenty_hard_cases.py --calitree-live --calitree-max-tokens 4096 -v -s
```

`stress_cases.py` contains 20 authored natural-language instructions, structured
observations, and independent expected labels. The cases target compound edit
failures with uncertain preservation, zero successful edits, empty requested sets,
exact/minimum-zero counts, scoped permissions, changed targets, allowed versus
forbidden shades, and injected metadata. These deliberately chosen cases probe
failure modes; they are not a random benchmark.

The real-model test compares the original overall judge with both the previously
compiled policy in `fixtures/frozen_generated_policy.json` and a fresh policy
compiled before scoring. The saved policy is bound to its rubric by SHA-256 and
includes its original compiler prompt and provenance. The fresh compiler receives
only the rubric. It has the same single schema-repair allowance as the preceding
experiment; no decision errors or expected labels are fed back into generation.
Neither policy is modified during scoring.

Instruction plans are compared against independently authored structured intent.
Each distinct atomic judgment is checked against its exact predicate. Accuracy
and errors are reported separately for each final judging method, including label
counts and matched-rule traces. Invalid instruction plans or a failed compilation
are recorded as errors so the other cases/methods can still be measured. The
original overall judge receives structured instructions; the two-way methods
parse the authored natural instructions, so this comparison measures the whole
pipeline rather than isolating one change.

Two offline checks validate the 20 case targets and the frozen policy's schema and
rubric identity. The live quality test requires the current freshly compiled policy to get all
20 cases right; the immutable previous policy is reported as a historical control. Reports and a compact case-by-case summary are written before
assertions, preserving failures without lowering expected labels or retrying for
quality. Look for `twenty_hard_cases.md/json` and `summary.md` in the report directory.

The first 20-case `gpt-4.1` run scored **18/20** for overall judging and
**10/20** for both the frozen and fresh generated policies. The strict live test
failed. Two instructions produced invalid combined condition keys; eight other
cases failed because an uncertainty rule preceded the no-success rule. All 18
valid instruction plans matched their references, and all 25 distinct atomic
checks were correct. The policies and targets remain unchanged for inspection.

## Current pipeline: staged generated policies

The current compiler separates `veto_rules`, `decision_rules`, and `caps`.
Vetoes return immediately. Decision rules select the base label; conditional caps
can only lower that label in the order `no < partial < yes`. The model generates
conditions, labels, applicability, and exceptions for each stage from the rubric.
The interpreter supplies the meaning of an upper bound; it does not supply the
rubric's business rules. This prevents a preservation-uncertainty cap from
upgrading a failed edit to `partial`.

Fixed rubric predicates are represented in `criteria`; instruction-dependent
predicates come from the instruction plan. The same interpreter supports the
simple red/circular rubric and the harder edit rubrics. Fixed criteria take
precedence for their keys and are counted once. Instruction parsing uses explicit
single-value field descriptions and permits one schema-only repair. Neither
compiler receives target labels, and neither retries incorrect decisions.

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_decomposition_pipeline.py tests/unit/calitree/test_generated_rules.py tests/unit/calitree/test_prompt_decomposition.py --calitree-live --calitree-max-tokens 4096 -v -s
```

`test_decomposition_pipeline.py` requires exact ground-truth agreement on all
8 simple cases (four fit and four held-out), 29 harder cases, and 20 stress cases.
It also compares each newly compiled hard policy against an independent reference
across all 2,048 combinations of requested subsets, edit outcomes, preservation
states, and permissions. Those state-test results never feed back into generation.
`test_staged_policy.py` tests cap monotonicity, veto precedence, fixed criteria,
empty requested sets, exemptions, and every three-edit status combination.

The frozen flat policy remains unchanged and can be parsed/executed to inspect
historical behavior. The twenty-case comparison reports that historical control;
its current quality gate applies to the freshly compiled staged policy. Old
failed reports are preserved, and no case targets have been modified.

The corrected pipeline's verified `gpt-4.1` run scored **8/8 simple**,
**29/29 harder**, and **20/20 stress** decisions, with no plan or atomic-check
mismatches. Both independent hard-policy compilations matched all 2,048 finite
state combinations. The selected live verification command passed 17 tests; the
normal CaliTree unit directory passed 34 offline tests and skipped 12 live tests.
Historical target labels were checked against prior reports and remain unchanged.

## Frozen comparison on unseen cases

`test_unseen_comparison.py` compares the original hard rubric, a TextGrad-selected
rubric, and two-way decomposition of that exact selected rubric. All arms receive
the same natural instruction, observed values, and metadata. Structured reference
intent, fixture purposes, and holdout labels are never model inputs. A shared
input adapter explains how the existing rubric's field references apply to natural
instructions; it does not change the decision policy.

Optimization uses only the 21 old harder cases and 20 old stress cases. Two
TextGrad updates are proposed, and a candidate replaces the incumbent only if
training accuracy strictly improves. Ties retain the incumbent. The selected
prompt and its compiled policy are saved in `unseen_preparation.json` before
holdout annotations are loaded. The preparation is reusable only with matching
code, training-data, model, and rubric hashes. If no candidate improves, the
report explicitly records that the selected prompt is unchanged.

`unseen_cases.py` contains 40 newly authored cases with 14 yes, 14 partial, and
12 no targets, including new values, paraphrases, negated irrelevant checks,
permissions, empty edit sets, zero/minimum boundaries, uncertainty, and metadata
distractions. These remain within the existing finite text-evidence vocabulary;
they are not real images, independently human-labeled examples, or new operation
families. The offline check validates labels against the independent reference
predicates and verifies that no full record overlaps training.

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_unseen_comparison.py --calitree-live --calitree-model gpt-4.1 --calitree-max-tokens 4096 --calitree-report-dir .cache/calitree-tests/unseen-frozen-20260926 -v -s
```

The first holdout evaluation is preserved in `unseen_comparison.json/md`, with
code/data hashes in `unseen_manifest.json`, full training/compilation calls in
the preparation, and a compact `summary.md`. There is one temperature-zero
judgment per case/arm, no accuracy-based retries, and only the existing bounded
schema repair for instruction parsing. The strict decomposition quality assertion
runs after saving results. An unfavorable result must not trigger pipeline fixes
or replacement of this holdout result. The same report directory refuses a second
evaluation after a result has been written.

The first frozen `gpt-4.1` holdout run scored **31/40 original**, **31/40
TextGrad-selected**, and **40/40 decomposed selected**. All instruction plans and
atomic checks matched their references; decomposition corrected nine selected-
prompt errors without any regressions. Training accuracy rose from 35/41 to
38/41, but the selected revision changed only formatting (the word sequence was
identical), so this does not compare against a stronger semantic rewrite. The
first proposal was rejected for removing the output contract; preparation resumed
from its saved training history before any holdout evaluation. Results and that
qualification are preserved under `.cache/calitree-tests/unseen-frozen-20260926/`,
including `interpretation.md`. Neither the holdout nor the pipeline was modified
after observing these results.

## Core implementation and recorded-response replay

The generated-policy and instruction/checking implementations now live in
`critical/core/optimization/prompt/calitree/decomposition/`. The main strategy is
`decomposition_twoway.py`; future strategies use `decomposition_<name>.py` and
inherit the `DecompositionAlgorithm` contract. The former `generated_policy.py`
test module is a compatibility import, and `TwoWayExperiment` delegates generated-
policy execution to the core implementation. The handwritten reducer and reference
guard selection remain independent, test-only oracles.

`test_decomposition_module.py` replays packaged real-model responses from the
previous simple, harder, stress, and unseen experiments, checking complete
judgments/traces for all 97 cases. It also tests builder callback integration,
persistent resume without new model calls, schema failures, unsupported semantics,
artifact integrity, cache separation, and injectable evaluator context. The replay
fixtures include original report hashes and template hashes. They validate the
implementation move and do not constitute fresh accuracy measurements or tuning
on the unseen cases. Original reports remain unchanged; their historical source
hashes correctly refer to the implementation used at the time.

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_decomposition_module.py -q
```

See `critical/core/optimization/prompt/calitree/decomposition/README.md` for public
usage, extension points, and the current structured-evidence boundary.

## Individual-case exploration with known-label feedback

The current user-directed exploration focuses on the accuracy of each real
AURORA case. `casewise_fitting.py` restarts from its cached optimized prompt,
compiles explicit observable conditions, evaluates each condition in a separate
SOURCE/EDITED vision call, and reduces the statuses in Python: any absent/unknown
means no, otherwise any partial means partial, otherwise yes. The first plan is
text-only and annotation-blind. A valid mismatch can trigger up to two revisions
using the known human label and images as explicit fitting feedback. Individual
condition checkers receive the instruction, one condition and the images; they
receive no annotation or previous final prediction. Pipeline errors are retained
and do not trigger label feedback.

This is fitting to known cases, with all attempts recorded. It is intentionally
not an estimate of generalization. Existing experimental results are preserved.
The runner is opt-in and does not change the default core strategy.

```sh
.venv/bin/python -m tests.unit.calitree.casewise_fitting --live \
  --baseline-dir .cache/calitree-tests/vision-visual-calibration-fresh32-20260926 \
  --output-dir .cache/calitree-tests/my-casewise-run --max-rounds 3
```

Use `--case J01` (repeatable) to inspect an individual case. Matching frozen
stages resume from content-addressed cache, including prompt, schema, model
settings and image hashes. Original, optimized, first-decomposed and revised
labels are saved per case along with every condition, observation, status and
explicit rubric conflict. Full histories and run configuration are linked to
`logs/exps/` via `log_directory.json`.
