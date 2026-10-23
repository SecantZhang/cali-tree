# Task-coverage reference gates

These frozen gates select advisory rules using a validated compiled instruction.
They contain task structures, reusable predicate conditions and aggregate support;
they contain no training source IDs or image paths. They do not predict a verdict
for a new input. Use `TaskCoveredJudge` for the final source/edited image judgment.

The three gates correspond to the three existing local training splits and are
separate alternatives. Do not ensemble them or choose among them using the new
example's reference label. See [the implementation and evaluation](../../docs/calitree_task_coverage.md).

The gates are experimental and not promoted. The completed paired test scores
33/48, 31/48 and 36/48 versus the regular judge's 33/48, 28/48 and 37/48. Two
original child batches regress. Local deterministic rule accuracy does not imply
that an LLM using the rule as reference retains that accuracy.
