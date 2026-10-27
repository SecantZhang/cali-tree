# Prepared full development evaluation of semantic facet experts

Status: **prepared and verified offline; not authorized or run**. V112 remains
selected. Its source-held balanced accuracy is67.9%; the over80% target is not
achieved by the small fitting diagnostic.

The next experiment obtains source-bound Sol facts for all276 development
evaluation cases and all99 protected originals. It keeps the existing915-case
teacher fitting evidence. Only the new observer measurements are limited to the
375 evaluation/protection cases; no evaluation cases or old training outputs
are discarded. The fixed source folds supply215–221 genuine fitting cases per
outer fold with the new observations, including43–45 Partial and26–27 Yes cases.

The pilot already supplies23 valid Sol observations. Its rejected N108 slot
stays unavailable and is never resampled. Therefore this collection needs
**351 new requests**. All80 reserved sources stay excluded. This remains the
existing source-held development population, not a new untouched final test.

Each call uses the exact v155 Sol evidence-first observation prompt/schema,
`gpt-6.1-sol`, low reasoning, temperature omitted and an8192 completion-token
ceiling. The instruction and two ordered benchmark images are the evidence.
No human labels, source identifiers or compiled check text enter the API request.
The reconstructed outcome-primary rubric is applied afterward to the returned
facts. It is not an instruction to the model to output a human grade.

The upload inventory contains **509 cached image files**, with702 image
occurrences across351 two-image requests. The destination is
**https://api.openai.com/v1**. The other uploaded content is the edit instruction,
generic observation rubric/value guide and its JSON schema. Human reference
grades stay in a separate local file.

## Budget and failure handling

- Maximum351 new paid requests; no transport retries, repaired answers or
  resampling of a failed/interrupted slot.
- Four fixed, disjoint queues of88/88/88/87 requests. Each has its own durable
  ledger and131072 completion tokens, totaling **524288 tokens**, including
  reasoning. Workers cannot borrow tokens from each other. A call starts only
  if its full8192-token reservation fits the worker budget.
- A provider rejection or three consecutive invalid results in a worker stops
  new work globally. Already reserved in-flight calls finish and stay counted.
  A worker exhausting its budget stops before another request. Missing facts
  remain unavailable and retain the existing pipeline fallback.
- One process lock prevents duplicate collection launches. Terminal/stopped
  runs cannot automatically restart. Request histories are isolated per worker.

Expected cost is about **$1.87**, extrapolating the23 valid Sol pilot calls,
with a working estimate of **$1.50–$4.00**. Different image sizes or model
reasoning can change this. The full completion allowance costs **$5.24288 plus
input charges**, not a total-charge cap. The verified standard
[Sol rates](https://developers.openai.com/api/docs/models/gpt-6.1-sol) are$2/$10
per million input/output tokens. No key, auth header or.env file is copied into
the experiment's source snapshots.

## Frozen fitting and evaluation plan

Learn at most four short correction/selection regions, each requiring a
positive outcome-grade witness plus at most one or two named semantic guards.
Use only genuine fold-training views under the existing five source folds.
Every proposed rule is vetoed if it changes a correct actual original case;
verify all99 originals and all144 local slots after fitting and merging.

Compare retaining prior expert priority with learned semantic precedence under
that same local veto. Strict priority should not become an untested constraint
preventing correction of a mistaken earlier expert on new sources. The primary
configuration is learned precedence, two guards, loss cost2, at most four rules
and at least three distinct supporting sources. Eight fixed configurations are
declared in the protocol before collecting new observations.

Keep the existing covered/valid route as the domain for a new expert. Invalid,
unavailable or unresolved observations retain V112. Recompute rule eligibility,
merged coverage and routes. Every276-case prediction, including fallback, stays
in the accuracy/balanced-accuracy denominators. Report raw strict/outcome-primary
Sol readouts, regular judge, V112 and the learned compact policy. No default
promotion occurs unless the actual requested accuracy/local/coverage criteria
are verified.

## Review and verification

Frozen files are in `logs/exps/261025-source-facet-collection-v161-r1`:
`protocol.json`, `jobs.json`, `worker_assignments.json`,
`reused_observations.json`, `memberships.json`, `upload_inventory.json`,
`manifest.json`, source snapshots and `preflight_verification.json`.
`references_not_uploaded.json` stays local and never enters an API payload.

Preflight verifies every original/held-source membership, reserved-source
exclusion, program and image binding, exact cached-prompt equivalence, request
key, source snapshot and disjoint worker assignment.28 targeted tests pass,
including actual mocked parallel ledgers hitting their token caps, global
provider-stop behavior and refusal to restart terminal runs. No model call or
credential resolution occurred during preparation/verification. A new explicit
paid-call/upload approval bound to the manifest and limits is required before
`--live`; no such approval is recorded yet.

The downstream v162 selector and v163/v164 auditors are implemented while approval
is pending.36 targeted tests pass; the eight affected tests pass again after an
additional response-model binding check. A complete351-slot parallel mock run
passes the native auditor, with its resulting cache explicitly marked ineligible
for real fitting. The actual collection is still unstarted.

The selector uses a closed vocabulary of named evidence, a positive outcome
witness for every grade change, hard local vetoes, and at least three supporting
sources. It merges only adjacent equivalent-action regions using exact Boolean
absorption/complementary union. The independent fitting auditor re-induces every
model, checks all915-row predictions and exhaustively compares native/merged
rules across up to12 Boolean predicates. No new source-held selector has been
fitted and no new accuracy is claimed yet.

Inference integration is also implemented as an opt-in v166 overlay. It retains
the original old-observer review mask and prechecks existing semantic conditions
before requesting one full Sol observation. Explicit retained-None or invalid
records fall back without resampling. Only a matching full-fit binding can be
exported against the full parent; evaluation-fold artifacts cannot use that parent.

42 targeted tests pass. Across six cached contexts, all1219050 predicate and5490
priority comparisons match the fitting projection. A separate empty-rule probe
replays915 actual high-level requests with identical parent judgments, rationales,
routes and sources, including99 original decisions. This is inference equivalence,
not a trained new model or an accuracy gain. V112 remains selected.

A cached-only fallback experiment is now complete and independently audited.
Its best source-held balanced accuracy is67.4%, below V112's67.9%, so it is not
promoted. Its fitting/inference mask correction is also applied to the prepared
Sol selector's downstream features, without changing any observation request,
source case, model setting or budget.46 targeted tests pass. See
`docs/calitree_cached_opinions_v172.md`. The real collection remains unstarted
pending the original explicit351-request approval.
