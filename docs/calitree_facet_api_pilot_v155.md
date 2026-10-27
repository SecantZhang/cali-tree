# Prepared training-only semantic facet comparison

Status: **complete and audited**. All48 generation slots are terminal, with46
valid observations and the two initial authentication failures preserved. This is
a separate paid experiment from the completed local v153 diagnostic. V112 remains
selected, and the over80% balanced-accuracy goal is not yet achieved.

The same 24 protected fitting cases, eight per human grade, receive one fresh
Luna and one fresh Sol observation using the explicit evidence-first semantic
rubric. The models report requested progress, complete fulfillment, operation
fidelity, entity preservation, extent and supporting evidence. The unchanged
v150 executable tree maps these observations to No/Partial/Yes. Neither human
labels nor calibration examples appear in the request.

This tests the observer's ability to distinguish Partial from No and Yes before
paying for a larger evidence collection. It is adapted training research after
v150–v152, not an independent performance estimate. All 276 development
evaluation sources and all 80 reserved sources remain excluded.

| Arm | Model | Reasoning / temperature | Requests | Completion tokens per request |
|---|---|---|---:|---:|
| Luna | gpt-6-luna | none / 0 | 24 | 2,048 |
| Sol | gpt-6.1-sol | low / omitted | 24 | 8,192 |

The shared durable ledger permits at most **48 paid requests and 245,760
completion tokens**, including reasoning tokens. Each HTTP slot has one attempt,
with redirects and endpoint/model substitution disabled. Failed, truncated or
interrupted slots remain failures; no resampling or automatic repair. Provider
rejection or three consecutive transport failures stop the run. No compiler,
fitting, deployment or final-set access occurs.

All 24 cases remain in each arm's denominator. Larger-collection admission is
frozen at at least 23 valid records, 18 correct, five correct per grade and no
more than two literal categorical-gap/`material_gap="none"` contradictions. An
admission pass would authorize no larger paid collection by itself.

The expected cost is **$0.50–$1.50**, assuming roughly 4,000–8,000 total input
tokens per request including images and 1,000–4,000 Sol completion tokens. The
full output allowance costs **$1.990656 plus input charges**; this is not a total
charge cap. Verified 2026-10-25 standard rates are $0.10/$0.50 per million input/
output tokens for [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
and $2/$10 for [Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
The fetched [vision guide](https://developers.openai.com/api/docs/guides/images-vision)
does not establish a patch multiplier for these exact aliases, so image-token
cost is explicitly estimated rather than presented as exact.

The upload inventory contains **48 unique cached AURORA benchmark images**,
each sent once to each model: 96 image occurrences in 48 two-image requests.
The other uploaded content is the edit instruction, generic reconstructed rubric,
allowed-value guide and JSON schema. Original cached image bytes are sent to
**https://api.openai.com/v1**; no human reference grades are uploaded.

Reviewable frozen files are in `logs/exps/261025-paid-facet-probe-v155-r1`:
`protocol.json`, `jobs.json`, `upload_inventory.json`, `manifest.json`, source
snapshots and `preflight_verification.json`. Reference grades are stored
separately in `references_training_only.json` for reporting only.

Run preparation/verification makes no credential lookup or model request. Live
collection requires an explicit paid-call/upload authorization record bound to
the exact manifest hash and limits, as well as `--live`. The user's approval is
recorded in `authorization.json`.

## Authentication stop and credential discovery correction

The first Luna request returned401 `expired_secret_key`. After the user's
"Key refreshed" reply, a one-shot recovery record cleared only the global
provider stop latch. The failed slot and budget reservation were retained.
The next, different Sol slot returned401 `token_invalidated`; it was also
retained, and the ledger stopped again. The user subsequently clarified that
they recharged API credit rather than replacing the credential.

A single read-only `GET /v1/models` after that recharge returned401
`invalid_api_key`, with no images or generation. At that stop, the
remaining **46 generation requests and235,520 completion tokens** stayed within
the original allowance. The two rejected slots reserve10,240 tokens
conservatively; the provider reported no generation usage. These are transport
failures, not zero-accuracy model judgments.

The v155 runner copied an older experiment's credential setup and assigned the
manual-settings path to `.env`. This bypassed scoped JSON settings. Both known
checkouts currently have no saved manual JSON credential file, while the
resolved original-checkout `.env` was last modified September23; the discovery
bug therefore does not itself establish the cause of the rejected key.

The separate v157 continuation adapter fixes scoped JSON/default/explicit-file
lookup, preserves the frozen v155 prompts/models/slots/limits, and refuses to
clear a stopped ledger automatically. An explicit file with
no key cannot silently fall back to an older credential. The original v155
source snapshot remains unchanged. Twenty-one targeted tests pass, including
mocked full wire/budget execution for both adapters and invalid durable-slot
retention without another request.

The user then supplied the refreshed worktree `.env`. A non-generating check
returned200 and listed both requested models. The v159 recovery recorded the
second stopped budget and both failed-slot hashes; only the global provider
latch/error count changed. v157 then completed the remaining46 requests using
that exact file. No rejected slot was retried. The v158-r3 audit independently
checks all48 request/history/image/route identities, actual/reserved accounting
and both recovery events.

The strict rubric achieves Luna15/24 and Sol17/24; both fail the frozen strict
admission rule. Reported usage is87,128 input and5,648 completion tokens, plus
10,240 conservatively reserved for authentication failures. Estimated cost from
reported usage at the frozen rates is$0.1281284, not a billing invoice. All48
request slots are exhausted; unused token allowance does not authorize another
request.25 targeted tests pass. The adapted rubric result is documented in
`docs/calitree_outcome_reconstruction_v160.md`.
