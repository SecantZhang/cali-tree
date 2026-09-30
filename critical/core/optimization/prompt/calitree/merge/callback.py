"""Adapter for the existing merge_prompts callback."""

from .base import MergeAlgorithm, MergeProposal, MultiMergeAlgorithm
from ..context import BuildContext
from ..node import CaliTreeNode


class CallbackMergeAlgorithm(MergeAlgorithm):
    def propose(
        self, left: CaliTreeNode, right: CaliTreeNode, context: BuildContext,
    ) -> MergeProposal:
        merged = context.services.merge_prompts(left.prompt, right.prompt)
        prompt = str(merged.get("prompt") or "")
        conflict = bool(merged.get("conflict") or not prompt.strip())
        return MergeProposal(
            prompt, conflict,
            str(merged.get("conflict_reason") or "incompatible criteria") if conflict else "",
        )


class CallbackMultiMergeAlgorithm(MultiMergeAlgorithm):
    def propose_many(self, children, context):
        from copy import deepcopy
        if context.services.merge_many_prompts is None:
            raise ValueError("Joint merging requires merge_many_prompts")
        payload = []
        for node in children:
            snap = context.artifacts.get(node.id, {})
            policy = (context.executor.policies.get(snap.get("policy_ref"), {})
                      if context.executor else {})
            payload.append({"id": node.id, "prompt": node.prompt,
                            "policy": deepcopy(policy.get("payload", {}))})
        result = context.services.merge_many_prompts(payload)
        text = str(result.get("prompt") or "")
        return MergeProposal(text, bool(result.get("conflict") or not text.strip()),
                             str(result.get("conflict_reason") or ""))


class ConcatenateMergeAlgorithm(MultiMergeAlgorithm):
    """A transparent baseline; compilation and acceptance still check the result."""

    def propose_many(self, children, context):
        return MergeProposal("\n\n".join(dict.fromkeys(node.prompt for node in children)))
