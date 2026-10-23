# Next accuracy experiment: change the observer, hold decisions fixed

Current verified source-held development accuracy is 215/276 (77.9%), with all
99 original training cases retained. Strictly over 85% requires 235/276.

The new error audit finds 61 remaining errors: on 53, the correct label is already
available from the existing experts or regular judge; on eight it is unavailable.
Twenty are harmful overrides of a correct regular judgment. These are action
availability bounds, not evidence that an expert or visual observation is
factually correct. Low-confidence review at 0.65 covers 87 cases, including 35
errors, but simply falling back to regular would correct only 12 of those errors
and can also lose correct overrides.

The v50 sparse-rule screen tests unary conditions and two-condition ANDs with
shared sparse class weights. All eight configurations converge; the strongest
that preserves original training accuracy gets 201/276, below the 215/276 forest
control. All nine configurations (including control) are recounted. Only ten of
the 276 development examples have multiple compiled requirements, so a change
confined to multi-requirement aggregation cannot alone close the 20-case gap.

## Prepared paired study

Final plan: `logs/exps/261020-observer-diagnostic-v51-r1/protocol.json`.
The initial v51 cached-control prototype is retained but is **not the requested
run**. The r1 plan adds a fresh Luna control so that both observer arms are fresh.

- Twelve training/development examples from twelve source groups: six known
  errors and six correct controls, two per reference class/status combination.
  Fixed hash ranking selects the cases; invalid cached evidence is excluded to
  isolate observer effects. The sample is deliberately balanced and selected,
  so its accuracy is not an estimate of overall generalization.
- Arm A: fresh GPT-6 Luna image observation, followed by Luna interpretation.
- Arm B: fresh GPT-6.1 Sol image observation (medium reasoning, no temperature),
  followed by the same Luna interpretation stage.
- Both arms use identical frozen compiled questions, physical prompt/schema,
  image pairs, cached regular judgments, and source-excluded controllers. No
  new fitting, compilation, regular judging, prompt tuning or validation access.
- Each of the five controllers excludes its held sources, reproduces its prior
  predictions, and retains all 99 original training cases. Full preparation
  reproduces all 276 cached source-held predictions before any fresh calls.
- Query reference labels are separate from model inputs. Neither observer nor
  interpreter sees human labels, prior verdicts, controller predictions, or
  whether the case was selected as an error/control.

The outcome measures the observer model's downstream effect, including changed
bound check states and label agreement under a fixed controller. Sol is an
alternative observer, not a factual oracle. It is possible for better physical
observations to expose a mismatch in rules learned from Luna evidence.

## Limits and cost

Maximum **48 requests**: 12 Sol observations, 12 Luna observations, and 24 Luna
interpretations. Maximum **589,824 completion tokens**; no transport retries or
compiler repairs. Observer cap 16,384 per request; interpreter cap 8,192.

Expected cost **$0.45–$1.10**. The full completion allowance costs **$2.162688 plus
input charges**, at the previously verified [Sol rates](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
and [Luna rates](https://developers.openai.com/api/docs/models/gpt-6-luna).
This is additional paid scope beyond the completed training expansion.

Failed slots remain failed and are never resampled. Reports include fresh-arm
accuracy with failed slots incorrect, availability, and a separately named safe
path that retains the cached prediction when re-extraction fails. All twelve
examples remain counted. Arm-specific interpretation slot IDs prevent cache
reuse even if the two observers emit identical evidence.

## Verification and status

The offline rehearsal mocks credential loading and engine construction, uses
recorded bound observations, executes all 48 slots, and confirms 12 Sol / 36 Luna
requests with four slots per example. Both mock arms reproduce the six correct
cached predictions. No real authorization file or ledger is created in the
prepared experiment. Fifty-four focused tests pass.

Independent preflight: `261020-observer-diagnostic-preflight-v51-r1`.

## Completed approved run

The user explicitly approved r1 in response to
`call_bf2d1565f1fa42c794af9ad6e2e18dd1`. All 48 requests complete, with no failures
or retries. The independent audit rebuilds every request identity, schema/media
binding, model route, feature projection and fixed-controller prediction.

| Input evidence | Correct on selected 12 |
|---|---:|
| Cached Luna | 6/12 |
| Fresh Luna observer + Luna interpreter | 6/12 |
| Fresh Sol observer + Luna interpreter | 4/12 |

Sol corrects zero fresh-Luna errors and loses two fresh-Luna correct decisions.
This does not support an observer replacement under the existing controller.
It does not establish which observer is factually right: the controller was
learned from Luna evidence, and this is a selected training-only diagnostic.

Fresh Luna changes predicates on seven of twelve examples and changes final
predictions on three. Equal total accuracy hides those changes. This is direct
evidence of repeat-read instability in the current pipeline, conditional on this
sample; it does not estimate its population frequency. The three prediction
changes include one correction, one new error, and one wrong-label change.

Known usage: 166,488 input and 37,556 completion tokens, estimated **$0.298** using
the requested models' reviewed rates. No failed reservations. Both approved caps
are respected. There is no fitting, new regular judgment, deployment or reserved
source access. The 80 reserved validation sources and serving defaults remain
unchanged. Audit: `logs/exps/261020-observer-diagnostic-audit-v51-r1`.

## Independent cached-field experiment

The v52 experiment restores source anchoring, view adequacy and applicability
fields that the existing portable feature projection largely discards after
absence guards. Its 199 declared Boolean predicates use non-vacuous any/all and
polarity-normalized confidence conditions, without counts, raw text, object names
or source/case identifiers. Tests verify duplicate invariance, non-vacuous empty
roles, preservation of non-absence view confidence, and absence safeguards.

This is a separate offline study using only the pre-existing 375-example Luna
cache. It does not access either fresh v51 arm or fit the diagnostic controllers.
Seven source-held configurations are recounted. All retain the original 99
examples, but the best added-field result is 214/276 versus the exact 215/276
control. Those fields alone do not improve generalization. No serving change.
