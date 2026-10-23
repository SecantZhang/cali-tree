# Local-fit-first portable trees (v18)

These nine files are executable feature-only policies from the audited local
compression run. They contain no training IDs or membership router. Splits 1, 2,
and 3 retain four, three, and two trees respectively; no complete root was found.

Load one policy with `PortableRuleExecutor` and call `predict_records(records)`.
Selecting one tree for a previously unseen case is not implemented by this bundle.
The reported 48/48 results score each tree only on its own training scope and
must not be interpreted as the accuracy of a combined deployed predictor.

See [the experiment report](../../docs/calitree_local_compression.md) for local
accuracy constraints, compression, incomplete merges, and bounded search limits.
