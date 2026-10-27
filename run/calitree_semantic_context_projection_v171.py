"""Match new-selector fitting indicators to the executable V112 review mask.

The frozen parent keeps its original native fitting views/predictions. Only a
new downstream selector's copy is normalized, avoiding a serving mismatch when
it is allowed to supersede an earlier expert.
"""
import numpy as np

from critical.core.calibration.local_warranted_rubric_v97 import SPECS as LOCAL
from run.calitree_source_excluded_calibration_v89 import baseline_predictions


def project_context(d, arrays, names):
    columns = [d['names'].index(n) for n in names]
    actual = np.asarray(arrays['full'][:, columns], dtype=np.float32) > np.float32(.5)
    fitting = np.asarray(arrays['T'][:, columns], dtype=np.float32) > np.float32(.5)
    _, locked = baseline_predictions(arrays['folder'], d['old_names'], d['raw'], d['semantic'],
        arrays['oof'], d['regular'], d['sol'], d['valid'])
    review = d['valid'] & arrays['genuine'] & ~locked & (arrays['oof'].max(axis=1) < .8)
    local_columns = [i for i, n in enumerate(names) if n in LOCAL]
    previous = fitting.copy()
    for j in local_columns:
        fitting[~review, j] = False
    return actual, fitting, {'prior_fitting_locked': locked, 'fitting_review': review,
        'changed_fitting_rows': int(np.sum(np.any(previous != fitting, axis=1))),
        'changed_fitting_indicators': int(np.sum(previous != fitting))}
