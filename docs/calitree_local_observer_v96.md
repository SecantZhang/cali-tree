# Local task/preservation evidence for the over-85% goal

The current verified development replay is **227/276 (82.2%)** after the weighted semantic review described in [the v105 report](calitree_weighted_semantic_v105.md). The strict target is **235/276**, retaining all 99 original decisions, 144 local slots and 273/276 upstream coverage. Serving defaults remain unchanged.

## Stop searching the same booster prefixes

V93 cold-loads the existing six outer/full native models and computes the 200-, 400- and 800-tree stages. These stages share the same trees; they are correlated predictions, not independent visual evidence.

| Stage | Correct /276 | Gains / losses versus current |
|---|---:|---:|
| 200 trees |222|4 /7|
| 400 trees |223|3 /5|
| 800 trees |225|1 /1|

Even a perfect selector among all three stages and the existing decision could reach only **229/276**. Requiring the existing affirmative semantic warrants leaves an oracle maximum of 225/276. These are descriptive ceilings for this selector family, not achieved policies or limits on all possible methods. No prefix selector was fitted.

## New local observation contract

A pinned [Qwen3-VL 8B Instruct checkpoint](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) supplies a genuinely new model view of the two images. Revision: `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`. Public safetensors/configuration files (17,534,339,512 weight bytes) were downloaded without authentication; their SHA256 values are recorded. Project images, prompts and labels were not uploaded. Runtime loads only these local files with remote code disabled and offline flags enabled.

The available host is an Apple M4 Pro with 48 GB RAM and Metal acceleration. The isolated `/tmp/calitree-vision-v63` environment uses torch2.9.0, torchvision0.24.0, transformers4.57.6, float16/SDPA, one worker and greedy decoding. Images are limited to 256 visual tokens each (262,144 pixels maximum); output is capped at 256 tokens per input. The torch/torchvision pair follows [the official compatibility instructions](https://pytorch.org/get-started/previous-versions/).

The observer returns seven separate model claims plus short visible evidence:

- Target correspondence or authorized replacement.
- Requested endpoint state.
- Goal-directed versus incidental progress.
- Visible collateral type.
- Whether preservation is explicitly requested in the instruction.
- Whether collateral affects the requested goal.
- Whether retaining the same instance is essential.

No satisfaction label or human reference is supplied or requested. Unrelated collateral is not an automatic grade cap. Claims are bound to the exact program, ordered image pair, prompt and model profile. These are still model claims, not certified physical facts.

## Diagnostics and grammar repair

The first runtime attempt stopped before inference because torchvision was absent. Its three failed slots remain recorded. After pinning torchvision, the unconstrained v94 diagnostic stopped after three consecutive malformed responses: 3/7 attempted slots were valid, 877 completion tokens. None was repaired or promoted.

V95 uses [native JSON-schema token constraints](https://github.com/noamgat/lm-format-enforcer), pinned lm-format-enforcer0.11.3, as a new decoding profile. The same balanced original-training diagnostic then yields **12/12 valid records**, 1,356 completion tokens, with no retries or fitting. Valid JSON does not establish factual correctness or pipeline accuracy. Earlier failures remain separate and unchanged.

## Frozen review cache completed

The collection covers **224 existing fitting/development inputs**, including ten originals needed for local vetoes. It caches the union of:

1. Actual review regions where bound evidence is valid, no existing v72/v87 rule fires, and the full teacher's top support is below .8.
2. Each outer fold's genuinely inner-source-excluded fitting views meeting the same .8 support cue.

The threshold is a fixed reviewed-development routing cue, not a calibrated probability of correctness. In the scored population, 83/276 cases are in actual review. Of these, 78 have a single requirement and include 26 current errors. This establishes enough possible headroom to justify the experiment; it does not claim those errors will be fixed.

Every future controller uses only its own fold's actual or OOS membership. The cache union, other-fold eligibility and case/source identities cannot become predictors or select fitting rows. Observations outside that controller's region are masked out. Exact compatible v95 smoke requests are reused with source path/SHA; failed compatible slots would remain failed. Collection is capped at224 fresh local inferences/57,344 output tokens, one worker and no retries, API calls, uploads or reserved-source access.

Collection completed in `logs/exps/261023-local-review-cache-v96-r1`:224 responses,222 fresh attempts plus two exact smoke reuses,220 accepted observations and25,796 fresh output tokens. Four slots reached the256-token cap and remain failed: T15M4,S0166,S0167,S0428. The old session62763 is finished; do not restart it. The complete v98 audit passes36 native teachers, all source/fold masks and request/response accounting. Of83 primary review cases,82 have valid records.

## Compact policies and preservation checks

V97 completes eight fixed warrant-seeded searches: semantic/auxiliary vocabularies, one/two positive fitting sources, concrete-grade versus hybrid independent-review actions, at most eight rules with two guard conditions each. These score215–224/276 and are not promoted.

A new grade requires an affirmative local warrant. Goal-directed progress can justify Partial before the endpoint is established. A visible deletion can coexist with a successful task when it does not affect the requested goal. Contradictions and uncertainty alone cannot justify failure. Because the local record is global, new grading warrants are disabled for multiple-requirement instructions; they cannot borrow evidence across requirements.

Rules fit only their own genuine source-excluded review views. Every actual original input vetoes harmful rules. Existing v72/v87 context/priority and outside-region fallback stay fixed. Failed local observations keep the prior prediction and remain in the full276-case denominator. The runner refuses to fit or create output while the cache is incomplete.

The generic learner extension preserves its original default behavior: an independent regression audit re-induces all six old gates, cold-replays36 native models and executes915 bound judgments. It reproduces225/276,99/99 originals,144/144 slots and273/276 coverage. Subsequent weighted nonlinear interactions improve the full pipeline to the independently verified227/276; see the v105 report for the executable rubric and limitations.

To reproduce the compact-rule study, use a fresh output path:

```bash
PYTHONPATH=/tmp/calitree-catboost-v62:. /Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/.venv/bin/python -u -m run.calitree_local_warranted_rules_v97 \
  --cache logs/exps/261023-local-review-cache-v96-r1 \
  --output-dir NEW_PATH
```

An improved result still needs independent re-induction, source/reference checks and real bound-runtime replay before promotion. The over85% objective remains active and unmet. A separate v108 higher-resolution observation profile is now collecting the same224 cases; old responses and failures remain unchanged.

## Authoritative artifacts

- [Prefix headroom](../logs/exps/261023-prefix-experts-v93-r1/results.json).
- [Pinned local checkpoint identity](../logs/exps/261023-local-vlm-download-v94-r1/identity.json).
- [Constrained local diagnostic](../logs/exps/261023-local-grammar-v95-smoke-r1/results.json).
- [Review collection protocol](../logs/exps/261023-local-review-cache-v96-r1/protocol.json), [memberships](../logs/exps/261023-local-review-cache-v96-r1/memberships.json).
- [Existing-policy regression verification](../logs/exps/261023-v87-regression-after-v97-r1/verification.json).
