# Focused robust candidate selection on C08 and C05

## Goal and baseline

Try to improve on the completed ten-case single-draw GEPA result (266/300 correct,
88.7% final accuracy) by concentrating on C08 and C05. C08 is the strongest
regression in that baseline (6/30 correct versus 17/30 for the original prompt).
C05 is a robustness trap: repeated GEPA achieved 10/10 in confirmation but 9/30
finally, whereas single-draw GEPA achieved 29/30.

This is development on previously seen cases. The current experiment can establish
whether a revised policy improves repeated judgments on these exact cases; it
cannot establish unseen-task transfer.

## Algorithm

- Candidate bank: original prompt, single-draw GEPA prompt, repeated GEPA prompt;
  generic scene/identity/count checklist variants; two GEPA mutations prompted by
  contrastive visual feedback for C08. C05 additionally gets a general relation
  checklist variant. Duplicates and prompts violating the JSON contract or copying
  the focal instruction are excluded.
- The C08 contrastive feedback contains an assistant visual audit: the source has
  two separated unlit candles; the edit groups three lit candles in a changed
  setting with text. This evidence is sent to the *optimizer*, not the judge. The
  requested rule must be reusable and omit case-specific details.
- Development: three independently scheduled blocks of eight judgments per
  candidate. Rank by mean accuracy minus 0.25 times the between-block range.
  Require at least a five-point score gain over the single-draw GEPA candidate.
- Confirmation: three further blocks of 12 fresh judgments for both candidate
  and GEPA incumbent. Accept only at least a ten-point mean correctness gain,
  with the candidate's worst block no more than ten points below the incumbent's.
- Freeze decisions before final evaluation. Re-evaluate the GEPA baseline prompt
  30 times for each of the ten cases. For focused cases with a different selected
  prompt, obtain 30 further fresh judgments. When prompts are identical, reuse the
  same final responses in both arms, so only changed prompts contribute to the
  paired difference.

All calls use the official OpenAI GPT-5.4-mini at temperature 0.3, reasoning none,
maximum 512 judge completion tokens. GEPA 0.1.4 reflection uses temperature zero.
The runner has live gating, checkpointed unique draw IDs, exact request hashes,
and a $5 estimated-cost cap. Cached successful calls are never treated as fresh
for another stage. Failed transport calls may be retried; malformed completed
responses count as incorrect.

## Reproduction

```bash
PYTHONPATH=. .venv/bin/python run/focused_robust_repair.py \
  --output-dir logs/exps/260924-11:27:00-exps --dry-run
PYTHONPATH=. .venv/bin/python run/focused_robust_repair.py \
  --output-dir logs/exps/260924-11:27:00-exps --live --resume
```

The dry-run upper bound is 264 development judge calls, 144 confirmation calls,
40 GEPA judge calls, 360 final judge calls, and two reflection calls. Actual calls
and cost depend on candidate duplication, selection, and confirmation gating.

## Completed results

The focused candidate selector beat the freshly evaluated single-draw GEPA
baseline on the exact ten-case set: **283/300 (94.3%) versus 274/300 (91.3%)**.
The gain is nine correct judgments, or +3.0 percentage points. The descriptive
paired case-bootstrap 95% interval is **[0, +9.0] points**; it includes zero
because only C08 changed. This is a fixed-set pilot, not a claim about new tasks.

| Case | Fresh GEPA / 30 | Challenger / 30 | Decision |
|---|---:|---:|---|
| C08 | 18 | **27** | GEPA prompt plus general scene/count checklist |
| C05 | 30 | 30 | Retain the existing GEPA prompt |
| Other eight | 226 | 226 | Identical prompts and shared final responses |
| **All ten** | **274** | **283** | **+9 correct** |

C08's selected checklist candidate scored **24/24 across three development blocks**,
**36/36 across three fresh confirmation blocks**, and **27/30 in final evaluation**.
It prompts the judge to separately inspect the requested relation and unrequested
changes to object identities, counts, and scene. This rule contains no reference
to candles or the focal instruction. The prior GEPA prompt alone returned 18/30
correct in the fresh final comparison.

C05's strongest candidate remained the earlier single-draw GEPA prompt. Preserving
it avoided the prior repeated-repair failure. Because the nine unchanged prompts
share final responses between arms, their contribution to the improvement is
exactly zero; the measured difference comes solely from C08.

The two **contrastively coached GEPA rewrites were not selected**. The winning
candidate was the earlier GEPA prompt with an assistant-authored general checklist
appended. This is evidence for the combined *candidate bank plus block-aware
selection plus explicit semantic checklist*, not proof that GEPA reflection itself
learned a better rule. The C08 visual audit was used during development, so the
method still needs a reliable automatic source of concept-level feedback before
full-dataset deployment.

## Verification

- Independent audit passed: 674 unique completed provider responses, exactly 330
  final judge calls, all final requests matching frozen prompts and image hashes,
  no target fields in judge requests, no invalid judge responses, recomputed
  274/300 and 283/300 scores, and final calls after candidate selection.
- Four focused and 14 prior pilot tests passed; `git diff --check` passed.
- Estimated list cost **$0.9095835**, below the user-approved $5 cap. 34 transport
  failure attempts were logged and recovered; unknown billing for failed calls is
  excluded from this estimate.
- The previous GEPA run had 266/300, while its **fresh** matched baseline here was
  274/300. That shift is why the contemporaneous 274/300 comparison is primary.

[Detailed report](../../logs/exps/260924-11:27:00-exps/report.md) ·
[Summary JSON](../../logs/exps/260924-11:27:00-exps/summary.json) ·
[Independent verification](../../logs/exps/260924-11:27:00-exps/verification.json)
