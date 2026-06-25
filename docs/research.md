# VEJudge Research Notes

## Judge Input Strategies

These are research variants to be evaluated empirically, not assumed equivalent:

| Strategy | When to use | Risk |
|---|---|---|
| **A: Direct video** | Short clips, video-capable model, temporal behavior is central | Expensive; opaque internal frame sampling |
| **B: Uniform frame sampling** | Cheap baseline, mostly static videos | Misses motion artifacts, audio, short temporal failures |
| **C: Keyframe / shot sampling** | Multi-scene videos, better coverage than uniform | Misses continuous motion defects |
| **D: Segment-level judging** | Long videos, localized errors, timestamp-tied rationales | Requires aggregation logic |
| **E: Multimodal summary** | Scale — extract captions, ASR, OCR, quality metrics first | Preprocessing pipeline complexity |

The first research question: **which input representation gives the best human agreement per dollar of inference cost?**

---

## Evaluation Metrics

Report all against a held-out human-labeled test set:

| Metric | Purpose |
|---|---|
| Spearman / Kendall correlation | Ranking agreement with humans |
| Mean absolute error | Score distance |
| Quadratic weighted kappa | Ordinal scale agreement |
| Pairwise preference accuracy | A/B agreement with humans |
| Calibration error | Whether confidence matches correctness |
| Per-category breakdown | Reveal category-specific failures |

Always report per-category results. A judge can look strong overall while failing on text editing, audio sync, object removal, or long-range motion.

---

## Common Failure Modes to Watch

| Failure | Mitigation |
|---|---|
| Surface realism bias — rewards visually clean outputs that ignore the instruction | Put `instruction_alignment` first in rubric |
| Frame-only blindness — misses flicker, motion defects | Add segment-level clips and temporal metrics |
| Audio neglect | Include ASR, audio features, explicit audio rubric |
| Source drift blindness — misses unintended source changes | Provide side-by-side source/output evidence |
| Overconfident rationales without evidence | Require timestamps and `evidence` fields |
| Scale drift across prompts or models | Version prompts; always calibrate |
| Long-video compression | Segment and summarize hierarchically |

---

## First Experiment Checklist

1. Select 100–300 video editing examples with human overall scores and sub-scores.
2. Split into seed calibration, validation, and held-out test sets.
3. Preprocess into uniform frames, keyframes, and short segments.
4. Run three judge variants: frame-only, segment-level, multimodal summary + keyframes.
5. Parse all outputs to the unified JSON schema above.
6. Compare raw judge scores vs. human scores.
7. Fit simple calibration models (linear regression first).
8. Evaluate on held-out set; report per-category.
9. Inspect worst disagreements manually.
