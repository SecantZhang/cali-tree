"""Conservative selection policy, distinct from parent merge acceptance."""
from .base import AcceptancePolicy


def rank(report):
    return (report["balanced_accuracy"] - .1 * report["flip_rate"], report["macro_f1"],
            -report["predicate_count"], -report["mean_completion_tokens"])


class GuardedAcceptance(AcceptancePolicy):
    def assess(self, baseline, candidate):
        if candidate["coverage"] + 1e-12 < baseline["coverage"]:
            return False, "coverage regression"
        for label, value in baseline["recall"].items():
            if value is not None and (candidate["recall"][label] is None or candidate["recall"][label] + 1e-12 < value):
                return False, f"{label} recall regression"
        if rank(candidate) <= rank(baseline):
            return False, "no measured improvement"
        return True, "improved guarded objective"
