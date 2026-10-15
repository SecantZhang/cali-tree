# M2 v4: local capacity, conflict detection, and semantic regrouping

- Implemented a new opt-in M2 learner with no mandatory Yes/Partial label vetoes.
  M1 question/image authentication and raw observations remain unchanged.
- Added a label-blind role/kind distribution projector using any/majority/all
  states and coarse check counts. It distinguishes the old No/Partial feature
  collision without object names, case IDs, or instruction text in conditions.
- Added global and per-group conflict diagnostics: exact collisions, missing
  records, achievable equality bounds, closest cross-label pairs, and mixed
  terminal leaves.
- Replaced random batch membership with jointly learned semantic partitions
  after M1. Three groups contain 26, 12, and 9 observed sources and each fits
  all its training labels. Every terminal rule has at least two distinct sources.
- Full-denominator local accuracy improves from 29/48 to 47/48 (97.9%). The
  original G3C05 transport failure stays unresolved. No retries, replacements,
  reference edits, or new model calls were used.
- Held-out-group score improves from 16/48 to 23/48; supplementary development
  improves from 7/12 to 9/12. Partial recall is still 5/16 out of fold and 1/4 on
  development. Strong local fit does not establish transferable semantic rules.
- The tree has 35 nodes and 18 terminal rules, twelve supported by only two
  sources. Some predictions rely on check counts and uncertain evidence. These
  weaknesses are explicitly documented rather than hidden behind training fit.
- 114 scoped tests pass. Independent audit verifies nine policies, 91 leaves,
  156 predictions, 90,270 feature values, and all four outer source separations.
  Replay uses zero new fits or calls. Earlier sealed results and the final fifty
  reservation remain preserved.
- Detailed report: `docs/calitree_m2_conflict_regrouping_v4.md`.
