# Frozen v14 research candidates

Three independently fitted training-cohort candidates and their direct-fitting
controls. No model was selected from the historical evaluation results. These are
research artifacts, not an automatically promoted production default.

An additional semantic audit found that these policies can predict Yes on
interpreted incidental-only changes with a missing endpoint. Most training
interpretations contain one requirement, so compound-request behavior is largely
untested. The audit preserves original labels and policies: these are conflicts
between predicted labels and extracted evidence, not adjudicated label errors.

The approved reserved-fifty evaluation is complete. Merged policies scored 26/50,
26/50 and 25/50 and made identical predictions to their direct-fitting controls.
Partial recall remains 23.5–29.4%. The smaller policies are not production-promoted;
see the [final results](../../docs/experiments/calitree_frozen_final_v14.json).

Each policy contains only the v8 feature contract, predicate descriptions, Boolean
tree and output labels. Training IDs, fitting labels and lineage are not inference
inputs. The manifest records the upstream Luna/compiler-v3 profile; it does not
claim compatibility was tested with arbitrary extraction models.

```python
import json
from pathlib import Path
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor

policy = json.loads(Path("examples/calitree_supported_children_v14/merge_split1.json").read_text())
judge = PortableRuleExecutor(policy)
predictions = judge.predict_records(bound_v8_feature_records)
```

The executor validates the artifact hash and closed feature contract. It does not
perform model calls or fit rules. Fresh images require the separately specified
instruction compiler, physical observation and semantic interpretation stages.
Prediction -1 means unresolved; 0/1/2 mean No/Partial/Yes. Missing observations must
not be dropped from evaluation denominators.

See [the design and measured limitations](../../docs/calitree_regularized_children.md).
