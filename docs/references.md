# VEJudge References

## Background reading (this repo)

- Overview and research goals: `../../intro/overview.md`
- Implementation tutorial: `../../intro/lm_judge_video_tutorial.md`

## Key References

- G-Eval (rubric-based LLM eval): https://arxiv.org/abs/2303.16634
- MT-Bench / judge biases: https://arxiv.org/abs/2306.05685
- AutoCalibrate: https://arxiv.org/abs/2309.13308
- VideoScore: https://arxiv.org/abs/2406.15252
- VideoJudge: https://arxiv.org/abs/2509.21451
- VBench: https://arxiv.org/abs/2311.17982
- VBench++: https://arxiv.org/abs/2411.13503
- EvalCrafter: https://arxiv.org/abs/2310.11440
- T2V-CompBench: https://arxiv.org/abs/2407.14505
- Human-Aligned MLLM Judges for Image Editing: https://arxiv.org/abs/2602.13028
- K-Sort Eval: https://arxiv.org/abs/2602.09411

### Method positioning — baselines to beat (see docs/research.md "Related work")

Debate-for-judging:
- D3 — Debate, Deliberate, Decide (cost-aware adversarial, interpretable): https://arxiv.org/abs/2410.04663
- ChatEval / PRD & multi-agent judging survey: https://arxiv.org/abs/2507.21028
- Multi-Agent Debate w/ Adaptive Stability Detection: https://arxiv.org/abs/2510.12697

Score-transform calibration (base calibrator ≈ ours, not novel):
- Two Ways to De-Bias an LLM-as-a-Judge (Bayesian linear + Neural-ODE): https://arxiv.org/abs/2605.09227
- Bridging Human and LLM Judgments: https://arxiv.org/abs/2508.12792
- Post-hoc Reward Calibration (length bias): https://arxiv.org/abs/2409.17407

Rubric-based judging (closest line):
- Rulers — From Rubrics to Reliable Scores (checklist + ridge+CDF calibration; the calibration baseline): https://arxiv.org/abs/2601.08654
- Rethinking Rubric Generation / GER-Eval (direct-prompt rubric gen; the no-debate baseline): https://arxiv.org/abs/2602.05125
- Learning to Judge — LLMs Designing & Applying Rubrics: https://arxiv.org/abs/2602.08672
- Auto-Rubric (implicit weights → explicit rubrics): https://arxiv.org/abs/2510.17314
- RubricRAG (retrieval-based rubric generation): https://arxiv.org/abs/2603.20882

Video editing quality (domain anchor):
- VE-Bench (human MOS QA for text-driven video editing): https://arxiv.org/abs/2408.11481
