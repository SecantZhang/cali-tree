# Current optimizer: harder-case stress test

Frozen before live calls on 2026-10-07. The user requested testing the current method on harder cases. Runtime, compiler, feedback, proposer, audits, and search algorithms are unchanged. Only the runner now reports the actual case count and supplied experiment scope, and a separate entry point freezes the stress-test selection.

Select the three lowest mean seed-agreement cases below 0.8 from the saved twelve-case optimizer comparison, excluding the previous six-case robust pilot. Agreement averages the custom, GEPA, and TextGrad baseline draws; those are repeated measurements on the same cases and shared seeds, not independent cases. Do not select on new outcomes or replace failures.

- Background to basketball court: prior mean seed agreement 7/9 (77.8%); reference yes.
- Chalk drawing: prior mean seed agreement 3/9 (33.3%); reference partial.
- Frog in the toilet: prior mean seed agreement 0/9; reference partial.

All three are previously observed local fitting cases, with verified original file hashes and distinct source-pixel groups. This subset deliberately emphasizes prior errors and is not class balanced. "Hard" means challenging for saved baseline judges, not objectively difficult or harder than every previous pilot case.

Use GPT-6 Luna through the official OpenAI provider, temperature 0, reasoning none, no substitution, one HTTP attempt per durable slot, stop after three consecutive transport failures. Run flat-greedy, flat-Pareto, tree-greedy, and tree-Pareto; rotate order as in the original experiment. Shared label-free compilation and audit, independent arm measurements and feedback, two search rounds, six proposal opportunities, four-check/depth-four caps, original 0.8 gates, five confirmation draws and five fresh final draws for each seed and selection. Freeze every arm before any final execution. Confidence is self-report, not calibrated correctness.

Ceilings: 1,800 model calls and 2,304,000 completion tokens. Search limit 109/case-arm; final limit 40/case-arm. Reserve 480 calls and 491,520 tokens before search; shared preparation at most six calls. Planned maximum 1,794 calls. Checker cap 1,024 tokens; other calls 2,048. Keep failures/interruptions, resume unattempted slots under identical frozen configuration. Measure agreement, coverage, label/requirement/check consistency, confidence, usage, and topology. Record whether harder cases elicit multiple checks; do not claim a decomposition comparison if they do not.

Run:

```bash
PYTHONPATH=. .venv/bin/python run/calitree_robust_hard_cases.py --live --output-dir logs/exps/261007-robust-hard-cases-v3
```

Replay uses the same command with `--resume`; the ledger never repeats attempted HTTP slots.
