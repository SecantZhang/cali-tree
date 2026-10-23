"""Serve the frozen semantic verifier with new correction regions opt-in.

The verification-only arm improved or preserved accuracy in every tested bank.
The correction arm remains available for research but added false acceptances
on forward inputs. Both modes reuse the same frozen policy and regular call.
"""
from .regular_aware_judge_v35 import RegularAwareJudge


class _PolicyMode:
    def __init__(self, policy, corrections):
        self.policy, self.corrections = policy, corrections

    def resolve(self, program, record, regular):
        return self.policy.resolve(program, record, regular, corrections=self.corrections)


class VerifiedSemanticJudge(RegularAwareJudge):
    """Use verified existing routes; leave new correction regions off by default.

    Always obtains the regular judgment, including on previously covered inputs.
    Unlike the original EvidenceCoveredJudge, this is not a call-saving gate.
    """
    def __init__(self, calls, policy, *, enable_corrections=False, **kwargs):
        if type(enable_corrections) is not bool:
            raise ValueError('enable_corrections must be a Boolean')
        self.gate, self.enable_corrections = policy, enable_corrections
        super().__init__(calls, _PolicyMode(policy, enable_corrections), **kwargs)
