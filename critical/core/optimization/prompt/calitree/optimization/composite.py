"""Measured candidate selection and bounded TextGrad/GEPA optimizer plans."""

from dataclasses import replace

from .base import LeafOptimizer, PromptOptimizer
from .gepa import BudgetExhausted, GepaSearch
from ..context import OptimizationResult
from ..decomposition.artifacts import digest
from ..evaluation import balanced_accuracy

PLANS = ("textgrad", "gepa", "textgrad_then_gepa", "gepa_then_textgrad", "best_of_both", "evaluate_only")


class OptimizerPlan(LeafOptimizer):
    def __init__(self, plan="textgrad", *, gepa_python=None, seed=44):
        if plan not in PLANS:
            raise ValueError(f"Unknown optimizer plan {plan!r}")
        self.plan = plan
        self.gepa = GepaSearch(gepa_python, seed)

    def optimize(self, prompt, ids, context):
        if not ids:
            raise ValueError("Cannot optimize an empty leaf group")
        steps = context.settings.max_steps
        combined = self.plan in {"textgrad_then_gepa", "gepa_then_textgrad", "best_of_both"}
        if combined and steps < 2:
            raise ValueError("Combined optimizer plans require max_steps >= 2")
        identity = digest([self.plan, self.gepa.seed, prompt, sorted(ids), context.samples,
                           context.targets, context.executor.identity if context.executor else {}, steps,
                           context.services.optimizer_identity])
        checkpoint_key = "modular:optimization:" + identity
        if context.checkpoint is not None and context.checkpoint.has(checkpoint_key):
            return OptimizationResult(**context.checkpoint.get(checkpoint_key))
        history, candidates, stage_history = [], [], []
        usage = context.services.optimizer_usage or (lambda: {})
        initial_usage = usage()
        used = 0
        stop = "step_limit"

        def evaluate(candidate, stage="gepa"):
            accuracy, correct, results = context.services.validate(candidate, ids, context.samples, context.targets)
            result = OptimizationResult(candidate, accuracy, correct, results, 0)
            rank = (balanced_accuracy(ids, context.targets, results), accuracy)
            history.append({"stage": stage, "prompt": candidate, "accuracy": accuracy,
                            "balanced_accuracy": rank[0]})
            candidates.append((rank, result))
            if context.services.on_candidate:
                context.services.on_candidate(dict(history[-1]))
            return result

        def best():
            return max(candidates, key=lambda row: row[0])[1]  # stable ties retain earlier candidate

        seed_result = evaluate(prompt, "seed")
        if self.plan == "evaluate_only" or steps == 0 or seed_result.accuracy == 1:
            stop = "evaluate_only" if self.plan == "evaluate_only" else "success" if seed_result.accuracy == 1 else "step_limit"
            stages = []
        elif combined:
            names = ["gepa", "textgrad"] if self.plan == "gepa_then_textgrad" else ["textgrad", "gepa"]
            stages = list(zip(names, [steps // 2, steps - steps // 2]))
        else:
            stages = [(self.plan, steps)]
        lineage = []
        for name, allowance in stages:
            stage_usage, stage_steps = usage(), used
            stage_report = {"stage": name, "allowance": allowance}
            stage_history.append(stage_report)
            current = seed_result if self.plan == "best_of_both" else best()
            if current.accuracy == 1:
                stop = "success"
                stage_report.update(steps=0, stop_reason="success", usage={})
                continue
            try:
                stop = "step_limit"
                if name == "gepa":
                    before = len(history)
                    report = self.gepa.search(current.prompt, ids, context, allowance, evaluate)
                    lineage.append({"stage": name, **report})
                    used += min(allowance, report["proposals"])
                    for candidate in report["candidates"]:
                        text = candidate["system_prompt"]
                        if not any(row["prompt"] == text for row in history[before:]):
                            evaluate(text, name)
                else:
                    for _ in range(allowance):
                        available = context.services.budget_available
                        if available is not None and not available():
                            raise BudgetExhausted("Optimizer budget exhausted")
                        if current.accuracy == 1:
                            stop = "success"
                            break
                        mistakes = [key for key in ids if key not in current.correct_ids]
                        if context.services.format_feedback is not None:
                            feedback = context.services.format_feedback(mistakes, context.samples,
                                                                        context.targets, current.predictions)
                        else:
                            feedback = "\n".join(f"Instruction: {(context.samples[k].get('input') or {}).get('instruction', '')}\n"
                                                 f"Predicted: {current.predictions[k].get('label')}\nTarget: {context.targets[k]}"
                                                 for k in mistakes)
                        rewritten = context.services.optimize(current.prompt, feedback)
                        used += 1
                        if rewritten == current.prompt:
                            stop = "no_improvement"
                            break
                        evaluate(rewritten, name)
                        current = best()
            except BudgetExhausted as error:
                if name == "gepa":
                    used += min(allowance, error.proposals)
                    lineage.append({"stage": name, "events": error.events,
                                    "proposals": error.proposals, "stop_reason": "budget_exhausted"})
                stop = "budget_exhausted"
                break
            finally:
                if best().accuracy == 1:
                    stop = "success"
                end_usage = usage()
                stage_report.update(steps=used - stage_steps, stop_reason=stop,
                                    usage={key: end_usage.get(key, 0) - value
                                           for key, value in stage_usage.items()})
        if best().accuracy == 1 and stop != "evaluate_only":
            stop = "success"
        end_usage = usage()
        selected = replace(best(), steps=used, report={"plan": self.plan, "history": history,
                           "lineage": lineage, "stages": stage_history, "stop_reason": stop,
                           "allowance": steps, "usage": {key: end_usage.get(key, 0) - value
                                                          for key, value in initial_usage.items()}})
        if context.checkpoint is not None:
            from dataclasses import asdict
            context.checkpoint.put(checkpoint_key, asdict(selected))
        return selected


class SelectedPromptOptimizer(PromptOptimizer):
    """Adapt bounded candidate selection for warm-start and merge refinement."""

    def __init__(self, settings, executor, checkpoint=None):
        self.settings, self.executor, self.checkpoint = settings, executor, checkpoint

    def optimize(self, prompt, ids, samples, targets, *, services, max_steps):
        from ..context import BuildContext
        context = BuildContext(services, replace(self.settings, max_steps=max_steps), None,
                               prompt, samples, targets, {}, {}, [],
                               executor=self.executor, checkpoint=self.checkpoint)
        return OptimizerPlan().optimize(prompt, ids, context)
