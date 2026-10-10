# V4 uncertainty handling and adaptive proposer experiment

Experiment artifacts: [saved run](../../logs/exps/261009-adaptive-leaf-v4/manifest.json),
[live report](../../logs/exps/261009-adaptive-leaf-v4/report.md).

## Method

The exact twelve previously observed AURORA cases were retained: four satisfied, four partial and four unsatisfied,
with distinct source-pixel groups and verified original image hashes. Each case is independently fitted; repeated
executions are measurements within that case, not new examples or a held-out generalization test.

Both arms share a newly compiled, label-free v4 seed and its preparation audit. Both use the same corrected runtime,
strict robustness policy, safe structural edits, proposal caps and per-case allowances. Their observations and histories
remain independent. Compilation, discovery, native TextGrad feedback, visual checks and semantic audits use GPT-6 Luna.
The adaptive arm changes only its proposer to GPT-6.1 Sol with medium reasoning after three completed stalled rounds.
The switch is permanent for that case; improvement before switching resets the streak. Provider failures do not trigger
this semantic escalation. All calls use official OpenAI, one HTTP attempt, without model substitution or schema repair.

V4 separates advisory context, known prerequisites and activation. Unknown progress no longer blocks independent
endpoint inspection. A skipped or blocked check does not automatically suppress later independent questions or the
image-free fulfillment readout. Unknown evidence is never converted into a negative observation or non-applicability.
Supporting facts do not directly earn completion credit.

Search is limited to fifteen rounds and two proposed transactions per round. Candidates are structurally validated and
audited before screening. The audited seed receives five confirmation draws; a candidate receives five fresh confirmation
draws only after a resolved target-matching screen. Comparable confirmed evidence governs selection and regression
protection. The original instruction, rubric, requirement ledger and requested bindings remain frozen.

All 24 selections were frozen after **1,653 preparation/search calls**, before any final draw. Each arm then receives
five fresh seed executions and five fresh selected executions. These outcomes cannot trigger another repair or change
selection. The approved ceiling is 3,600 calls / 4,608,000 completion tokens, including failed/interrupted attempts;
960 final calls / 983,040 tokens were reserved before search.

## Verification

The full offline unit suite passed before live execution: **1,310 passed, 23 skipped**. Focused v4 coverage includes
independent endpoint execution with uncertain context, required-unknown propagation, legitimate conditional skipping,
strict rejection of executed uncertainty, immutable edits, provenance and binding preservation, cache identity,
version dispatch, exact leaf reload, escalation timing/reset, intermediate recovery, regression protection,
failure/interruption accounting, final isolation and zero-call resume.

The production offline synthetic demo resolves a known endpoint while retaining an uncertain supporting observation.
That demonstrates the runtime fix; the strict robustness gate still rejects the uncertain executed support.

## Results

The experiment completed all 24 case-arm comparisons, using **2,341 calls**, **383,754 charged completion tokens** and
7,067,439 reported input tokens. Preparation/search used 1,653 calls; final verification used 688. Returned model identities
were `gpt-6-luna` and `gpt-6.1-sol`. There were 17 retained transport failures (seven during final verification), without
a three-consecutive-failure stop. No failed slot was retried and no model substitution occurred.

| Measure | Luna-only | Luna → Sol |
|---|---:|---:|
| Seed final reference matches / 60 | 27 | 29 |
| Selected final reference matches / 60 | 29 | 35 |
| Selected resolved draws / 60 | 58 | 59 |
| Locally robust leaves / 12 | 2 | 5 |
| Selected programmes changed from seed | 1 | 3 |
| Cases whose proposer escalated | 0 | 8 |

Each arm has 12 cases × five final draws = 60 measurements; this remains a twelve-case exploratory comparison.
Seed programmes were identical between arms, but their observations were fresh and independent, explaining the different
seed match totals. The adaptive arm's improvement is encouraging, not a statistically established general advantage.

The adaptive arm's three changed, finally robust programmes were:

- **Pencil drawing:** two support revisions plus a readout revision, proposed by Luna. Five final draws matched `partial`.
  The arm completed four started repair rounds (three without response/transport failure) before qualifying; it never escalated.
- **Basketball background:** Sol configured the progress question to run only after a failed or uncertain full-endpoint check.
  This legitimately omits unnecessary comparative evidence when a complete court background is established. It qualified
  on round four and matched `yes` in all five final draws.
- **Chalk drawing:** Sol revised a supporting check; the programme qualified on round twelve and matched `partial` in
  all five final draws. The saved programme and transaction contain the exact criterion and binding.

Comic and cylinder leaves also passed, but retained their seeds in both arms; those are baseline successes, not new
optimization gains. The Luna-only book repair improved final agreement from 2/5 to 4/5, but one unresolved final draw
prevented robust status. The adaptive book seed passed search confirmation but then produced only 2/5 final reference
matches. This demonstrates why search confirmation and final verification remain separate.

The jacket remained a stable mismatch: both selected programmes predicted `no` in all five final draws against a `yes`
reference. Its progress uncertainty no longer prevents independent closure inspection or readout execution. The runtime
defect is fixed, but the remaining visual/semantic/reference disagreement is not solved by the proposer switch.

Five shared seed audits were approved, three rejected, and four failed the source-grounding response contract.
All twelve seed compilations were structurally valid. An acceptance status of `unresolved` can mean that an audit is
unavailable or unapproved, even when the model resolved all five predictions; coverage and the recorded reasons distinguish
that from execution uncertainty. These failures are not hidden or treated as audit approvals.

The strict selection guard prevented regression on comparable **confirmation** evidence. Fresh final draws can still
regress: Luna-only final coverage was 58/60 versus its seed's 59/60. This is an experimental observation, not a reason to
replace the frozen candidate after evaluation.

## Reproducibility

[Protocol verification](../../logs/exps/261009-adaptive-leaf-v4/protocol_verification.json) passed label isolation,
image-free fulfillment, immutable original requirements, deterministic escalation, final-budget limits, unique logical
slots, fresh final executions and selection freezing. Both current-source and pinned-source replay completed with zero
new model calls and identical serialized case results and budget. The verifier normalizes Python tuple fields to their
portable JSON-array representation before comparison; this changes no programme, prediction or experiment selection.

```bash
.venv/bin/python logs/exps/261009-adaptive-leaf-v4/analyze_saved_run.py --replay
.venv/bin/python logs/exps/261009-adaptive-leaf-v4/replay_frozen_analysis.py
```

Detailed questions, observations, confidences and decisions are in
[component analysis](../../logs/exps/261009-adaptive-leaf-v4/component_analysis.json); per-model usage and class counts
are saved alongside it. Replays retain the 17 failed attempts and their conservative charges.

## Interpretation boundaries

The paired comparison tests proposer escalation under the corrected runtime. Comparing this run with historical pilots
is descriptive because seeds, protocol and observations differ. A semantic audit is fallible evidence; a high reported
confidence is not calibrated correctness. Unvisited alternatives remain untested, and local reference agreement does
not certify each atomic observation or establish generalization.

Some shared seed audits were rejected or failed the required source-grounding response contract. Those failures remain
recorded and did not become approvals or fabricated visual feedback. Diagnostic execution of such a seed supplies
repair evidence, but cannot earn selection scores or robust acceptance without a valid audit.
