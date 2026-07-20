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

## Related work & baselines to beat (prior-art positioning)

The vejudge method — **human-grounded adversarial debate → extract semantic rubrics →
interpretable (semantic/ontology) tree calibration**, for an **MLLM video judge** — sits in
an *active* 2025–26 area. It is a novel *synthesis/mechanism* choice, not an empty problem;
the framing must be "does debate extract better rubrics, and does a semantic tree calibrate
better, than existing rubric-gen + regression calibration" — and it must benchmark against
the methods below. Full survey + links in `docs/references.md`.

**Prior art (the components already exist):**
- *Debate-for-judging*: ChatEval / PRD, and **D3 (Debate, Deliberate, Decide)** — a cost-aware
  *adversarial + interpretable* LLM-evaluation framework (arXiv 2410.04663). Ours differs by
  grounding one debater in the **real human score** (human-proxy) and using the debate to
  *extract reusable rubrics*, not reach inter-LLM consensus.
- *Score-transform calibration*: **"Two Ways to De-Bias an LLM-as-a-Judge"** (Bayesian linear
  + Neural-ODE, arXiv 2605.09227) ≈ our linear/bias calibrator — so the base calibrator is
  **not** novel.
- *Rubric-based judging* (closest line, hot): **Rulers — "From Rubrics to Reliable Scores"**
  (arXiv 2601.08654) and **rubric-generation** work (GER-Eval / "Rethinking Rubric Generation"
  2602.05125; Learning-to-Judge 2602.08672; Auto-Rubric 2510.17314; RubricRAG 2603.20882).

**The two concrete baselines to add to the comparator grid** (in
`core/calibration/debate/eval/rule_fit.py::fit_and_evaluate`, currently base/bias/linear/
CART/semantic):
1. **`ridge_cdf` — Rulers' calibrator**: 2nd-order **ridge regression (α≈2.5) + monotone CDF
   distribution alignment**, fit on the anchor set. This is the real bar for the *calibration*
   half; if the semantic tree can't beat it at scale, the tree isn't justified. Rulers reports
   **QWK** (0.40–0.71) on text essay/summarization sets — no video, no debate, no tree.
2. **`direct_rubrics` — GER-Eval-style extraction**: single-pass directly-prompted rubrics
   (no debate) fed to the *same* calibrator, vs our debate-mined rubrics. This isolates the
   **debate's value** — the single most important ablation. GER-Eval is direct prompting only,
   text only, human-corr 0.49–0.82 (unstable).

**Metrics for comparability**: report **QWK** (comparable to Rulers) *and* **SRCC/PLCC/KRCC**
(comparable to VE-Bench). The Eval/Alignment nodes already emit all of these.

**Label budget → center the paper on VE-Bench.** Rulers needs **N≈100–200** calibration
labels; the peanut track has **13** (33 multi-model). We cannot fairly run Rulers' calibrator
— let alone claim a tree beats it — below their minimum, so the head-to-head **must** live on
**VE-Bench (n≈1,170)**. Peanut/coconut/grapenut is the assembly-editing side-track.

**Target ablation grid** (one run, per dimension, QWK + SRCC/PLCC):
`{bias, linear, ridge_cdf(Rulers), CART, semantic-tree}` × `{debate-mined vs direct rubrics}`
× `{independent critic vs cold self-answer}` — the last already has a null result (the judge
won't self-flag), which is evidence for the critic. Also ablate ontology-weighting vs uniform.
Deferred (not built): the `ridge_cdf` + `direct_rubrics` comparators, and a human study on
rubric interpretability.

## Future directions

### Video reference database (retrieval-augmented judging) — parked

**Idea:** index every item's videos (source assets + final edit) so we can look up
structurally/perceptually **similar edits** (transition types, cut density, music/beat
presence, pacing) and hand the judge similar, already-human-scored examples as **calibration
anchors** at judgment time ("this transition pattern is like these, which humans scored ~3").
This is retrieval-augmented / kNN-anchored judging.

**Verdict: parked — not on the critical path, and premature at current scale.** Recorded here
as a potential future direction, not a near-term task. Reasoning:
- The core gap is **human-alignment/calibration**, not perception — the judge already sees the
  full video, and preprocessing already extracts per-item pattern features (shot boundaries,
  audio-event labels, blur/flicker, captions, transcript). A similarity DB doesn't directly
  attack the calibration gap.
- **Needs scale to work.** A retrieval pool of tens of items (peanut 13–54) returns neighbors
  that aren't actually similar, adding noise, not grounding. Only meaningful at **VE-Bench
  scale (~1,170)**.
- It's a substantial new subsystem (edit/video embeddings + an index + transition/music
  descriptors) orthogonal to the debate → rubric → semantic-tree thesis; high scope-creep risk.

**If revisited, do it as a measurable ablation, not a silent pipeline change:** retrieve k
human-scored neighbors as calibration anchors and A/B against the no-retrieval baseline on
VE-Bench, only if semantic-tree calibration plateaus with a residual gap that "similar-example
anchoring" plausibly closes.

**Cheaper adjacent win (also future, lower-risk):** a corpus-level **pattern-feature store**
(no similarity search) — a thin aggregation layer over the artifacts preprocessing already
caches, keyed by item id — enabling corpus-wide analysis of which recurring edit patterns
co-vary with human score. Those patterns become candidate **split features for the semantic
decision tree** and candidate axes for debate-mined rubrics, directly serving the thesis.
