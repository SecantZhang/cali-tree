"""Existing held-out and additive root selection policies."""

from typing import Any, Optional

from .base import RootSelector
from ..context import BuildContext, RootSelection
from ..evaluation import balanced_accuracy
from ..node import CaliTreeNode


class ValidatedRootSelector(RootSelector):
    def select(self, context: BuildContext, *, accepted_merges: int) -> RootSelection:
        initial_prompt = context.initial_prompt
        warm_prompt = context.warm_prompt
        initial_accuracy = context.initial_accuracy
        warm_accuracy = context.warm_accuracy
        external_validation_ids = context.validation_ids
        external_validation_samples = context.validation_samples
        external_validation_targets = context.validation_targets
        nodes = context.nodes
        global_prompt = warm_prompt
        global_source = "textgrad"
        global_selection: dict[str, Any] = {
            "selected": global_source,
            "criterion": "fit_accuracy_no_internal_validation",
            "initial_fit_accuracy": initial_accuracy,
            "textgrad_fit_accuracy": warm_accuracy,
        }
        if external_validation_ids:
            initial_validation_accuracy, _correct, initial_validation_results = context.services.validate(
                initial_prompt,
                external_validation_ids,
                external_validation_samples,
                external_validation_targets,
            )
            warm_validation_accuracy, _correct, warm_validation_results = context.services.validate(
                warm_prompt,
                external_validation_ids,
                external_validation_samples,
                external_validation_targets,
            )
            initial_validation_balanced = balanced_accuracy(
                external_validation_ids,
                external_validation_targets,
                initial_validation_results,
            )
            warm_validation_balanced = balanced_accuracy(
                external_validation_ids,
                external_validation_targets,
                warm_validation_results,
            )
            # A rewritten prompt must demonstrate balanced validation improvement.
            # Exact ties keep the fixed rubric, preventing fit-only gains from silently
            # trading away minority-label recall on unseen cases.
            if (
                warm_validation_balanced
                > initial_validation_balanced + context.settings.global_min_validation_gain
            ):
                global_prompt = warm_prompt
                global_source = "textgrad"
            else:
                global_prompt = initial_prompt
                global_source = "initial"
            global_selection = {
                "selected": global_source,
                "criterion": "internal_balanced_accuracy",
                "minimum_gain": context.settings.global_min_validation_gain,
                "initial_fit_accuracy": initial_accuracy,
                "textgrad_fit_accuracy": warm_accuracy,
                "initial_validation_accuracy": initial_validation_accuracy,
                "textgrad_validation_accuracy": warm_validation_accuracy,
                "initial_validation_balanced_accuracy": initial_validation_balanced,
                "textgrad_validation_balanced_accuracy": warm_validation_balanced,
            }
            context.timeline.append({
                "kind": "global_selection",
                "node_id": f"global:{global_source}",
                **global_selection,
            })
        accumulated_root_id: Optional[str] = None
        if context.settings.specialization_mode == "additive":
            # The root is the accumulation of validated deltas — the widest-coverage accepted
            # merge. Every accepted merge already cleared the no-regression-vs-base guard, so
            # this node is validated >= the flat base on its guard set. With no accepted merge
            # the root falls back to the base rubric, so the root is never worse than flat.
            accepted_parents = [
                node for node in nodes.values()
                if node.status in {"accepted", "partial"}
            ]
            if external_validation_ids:
                baseline_validation_accuracy = (
                    warm_validation_accuracy
                    if global_source == "textgrad"
                    else initial_validation_accuracy
                )
                baseline_validation_balanced = (
                    warm_validation_balanced
                    if global_source == "textgrad"
                    else initial_validation_balanced
                )
                root_candidates: list[CaliTreeNode] = []
                for node in accepted_parents:
                    candidate_accuracy, _correct, candidate_results = context.services.validate(
                        node.prompt,
                        external_validation_ids,
                        external_validation_samples,
                        external_validation_targets,
                    )
                    candidate_balanced = balanced_accuracy(
                        external_validation_ids,
                        external_validation_targets,
                        candidate_results,
                    )
                    node.generalization_accuracy = candidate_balanced
                    node.routing_eligible = bool(
                        candidate_accuracy >= baseline_validation_accuracy
                        and candidate_balanced
                        > baseline_validation_balanced + context.settings.global_min_validation_gain
                    )
                    context.timeline.append({
                        "kind": "accumulated_root_validation",
                        "node_id": node.id,
                        "accuracy": candidate_accuracy,
                        "balanced_accuracy": candidate_balanced,
                        "baseline_accuracy": baseline_validation_accuracy,
                        "baseline_balanced_accuracy": baseline_validation_balanced,
                        "routing_eligible": node.routing_eligible,
                    })
                    if node.routing_eligible:
                        root_candidates.append(node)
                accepted_parents = root_candidates
            if accepted_parents:
                if context.settings.root_objective == "balanced":
                    # Prefer the accumulated node with the best held-out balanced accuracy
                    # (each merge's generalization guard already measured it), so the root
                    # cannot trade the minority `partial` class for a wider `no`-heavy merge.
                    best = max(
                        accepted_parents,
                        key=lambda node: (
                            node.generalization_accuracy
                            if node.generalization_accuracy is not None
                            else -1.0,
                            len(node.covered_ids),
                            node.validation_accuracy,
                            node.id,
                        ),
                    )
                else:
                    best = max(
                        accepted_parents,
                        key=lambda node: (
                            len(node.covered_ids), node.validation_accuracy, node.id
                        ),
                    )
                global_prompt = best.prompt
                global_source = "accumulated"
                accumulated_root_id = best.id
            else:
                # Keep the flat prompt already selected on the full validation split. A
                # locally accepted merge remains useful evidence, but cannot become the
                # root (or intercept a route) until it improves the complete held-out set.
                accumulated_root_id = None
                flat_prompt_source = global_source
                global_source = "base"
                global_selection["base_prompt_source"] = flat_prompt_source
                if external_validation_ids:
                    global_selection["base_validation_accuracy"] = (
                        warm_validation_accuracy
                        if flat_prompt_source == "textgrad"
                        else initial_validation_accuracy
                    )
                else:
                    global_selection["base_fit_accuracy"] = warm_accuracy
            global_selection = {
                **global_selection,
                "selected": global_source,
                "criterion": "widest_validated_delta_accumulation",
                "accumulated_node": accumulated_root_id,
                "accepted_merges": accepted_merges,
            }
            context.timeline.append({
                "kind": "additive_root",
                "node_id": f"global:{global_source}",
                "selected": global_source,
                "accumulated_node": accumulated_root_id,
            })
        return RootSelection(global_prompt, global_source, accumulated_root_id, global_selection)
