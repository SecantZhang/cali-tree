"""Repeated evaluation with label-independent, single-slot transport recovery."""
from copy import deepcopy
from .metrics import RobustEvaluator, summarize

class RecoveryEvaluator(RobustEvaluator):
    """One recovery check per report, selected without looking at the label or answers."""
    def evaluate(self,program,case,reference_label,*,repeats,namespace,final=False):
        raw=super().evaluate(program,case,reference_label,repeats=repeats,namespace=namespace,final=final)
        effective=deepcopy(raw['traces']);attempt=None
        # Choose the first transport failure in saved execution order, regardless of target.
        for draw,t in enumerate(raw['traces']):
            for index,o in enumerate(t['observations']):
                if o['event']=='transport_failure':
                    attempt={'draw':draw,'check_id':o['check_id'],'original_execution_ref':o['execution_ref'],
                        'slot':f'{namespace}/transport_recovery/{draw}', 'limit':1,'selection':'first_transport_failure_in_order'}
                    effective[draw]=self.executor.recover_transport(program,case.evidence,t,index,
                        repeat=attempt['slot'],final=final)
                    break
            if attempt:break
        report=summarize(program,effective,reference_label,self.policy)
        report.update(raw_measurements=raw,transport_recovery=attempt,
            mean_attempted_calls=(sum(len(o.get('attempts',[o])) for t in effective for o in t['observations'] if o['queried'])/repeats))
        return report
