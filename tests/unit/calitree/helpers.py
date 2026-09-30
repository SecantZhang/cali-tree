"""Exercise production extraction/synthesis and emit readable decision comparisons."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

from critical.checkpoint import CheckpointStore
from critical.core.judge.parse import parse_json_object
from critical.core.optimization.prompt.calitree import (
    BuildContext, CaliTreeBuilder, CaliTreeServices, CaliTreeSettings,
)
from critical.interface.node_calibration.calitree_nodes import _CaliTreeRuntime


class LiveCaliTreeExperiment:
    def __init__(self, engine, work_dir: Path, report_dir: Path):
        self.report_dir = report_dir
        self.calls = []
        self.individual_judging = False
        self.engine = RecordingEngine(engine, self.calls)
        ctx = SimpleNamespace(
            node_id="simple-calitree", checkpoint=CheckpointStore(work_dir / "checkpoint.jsonl"),
        )
        # Extraction and synthesis use the existing production templates, parser,
        # response fallback, cache, and usage accounting. No TextGrad or images needed.
        self.runtime = _CaliTreeRuntime(
            ctx, judge_engine=self.engine, optimizer_engine=self.engine, embedding_model="unused",
            optimizer_budget=8192,
        )

    def judge_many(self, prompt, samples):
        if self.individual_judging and len(samples) > 1:
            # Match the production runtime's one-case-per-generation behavior.
            # Concurrency only reduces latency; cases never share a model prompt.
            with ThreadPoolExecutor(max_workers=min(4, len(samples))) as executor:
                judgments = list(executor.map(
                    lambda item: self._judge_batch(prompt, {item[0]: item[1]})[item[0]],
                    samples.items(),
                ))
            return dict(zip(samples, judgments))
        return self._judge_batch(prompt, samples)

    def _judge_batch(self, prompt, samples):
        user = (
            "Apply the rubric independently to each object below. These are complete, "
            "text-only evidence records; do not require images or infer missing requirements. "
            "Return one JSON object mapping each supplied ID to its judgment object "
            "with fields label and rationale.\n\nObjects:\n"
            + json.dumps(samples, sort_keys=True)
        )
        result = self.engine.generate(user, system=prompt)
        predictions = parse_json_object(str(result.get("content") or ""))
        assert set(predictions) == set(samples), "Model must return exactly the supplied case IDs"
        for key, value in predictions.items():
            assert isinstance(value, dict), f"{key}: expected a judgment object"
            assert set(value) == {"label", "rationale"}, f"{key}: output contract changed"
            assert value["label"] in {"no", "partial", "yes"}, f"{key}: invalid label"
            assert isinstance(value["rationale"], str), f"{key}: rationale must be text"
        return predictions

    def context(self, prompt, samples, targets, validation_samples, validation_targets):
        services = CaliTreeServices(
            judge=lambda text, sample: self.judge_many(text, {"case": sample})["case"],
            judge_many=self.judge_many,
            optimize=lambda text, _feedback: text,
            extract_components=self.runtime.extract,
            embed=lambda _texts: (_ for _ in ()).throw(AssertionError("No embeddings in merge test")),
            merge_prompts=self.runtime.merge,
        )
        # Reuse validated defaults, but disable refinement so a bad synthesized
        # merge cannot be repaired before the experiment measures its quality.
        builder = CaliTreeBuilder(
            judge=services.judge, judge_many=services.judge_many, optimize=services.optimize,
            extract_components=services.extract_components, embed=services.embed,
            merge_prompts=services.merge_prompts, max_steps=0,
        )
        settings = CaliTreeSettings(**{
            field.name: getattr(builder, field.name) for field in fields(CaliTreeSettings)
        })
        return BuildContext(
            services=services, settings=settings, optimize_cases=builder._optimize_for_cases,
            initial_prompt=prompt, warm_prompt=prompt, samples=samples, targets=targets,
            validation_samples=validation_samples, validation_targets=validation_targets,
            timeline=[],
        )

    @staticmethod
    def labels(predictions):
        return {key: value["label"] for key, value in predictions.items()}

    def report(self, name, *, prompts, samples=None, targets=None, comparisons=None, **details):
        report = {
            "model": self.engine.model, "engine": self.engine.name,
            "prompt_version": self.runtime.prompt_version,
            "judge_mode": "individual" if self.individual_judging else "batched",
            "prompts": prompts, "samples": samples or {}, "targets": targets or {},
            "comparisons": comparisons or {}, **details,
            "model_calls": self.calls, "runtime_usage": self.runtime.usage,
        }
        json_path = self.report_dir / f"{name}.json"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        lines = [f"# {name.replace('_', ' ').title()}", "", f"Model: {self.engine.model}", ""]
        for title, prompt in prompts.items():
            lines.extend([f"## {title}", "", "```text", prompt, "```", ""])
        if comparisons:
            columns = ["Case", "Evidence", "Expected", *comparisons]
            lines.extend(["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"])
            for key, sample in samples.items():
                cells = [key, json.dumps(sample), targets[key], *[
                    values[key]["label"] for values in comparisons.values()
                ]]
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
        if details:
            lines.extend(["## Details", "", "```json", json.dumps(details, indent=2), "```", ""])
        markdown = "\n".join(lines)
        (self.report_dir / f"{name}.md").write_text(markdown)
        print("\n" + markdown + f"\nFull report: {json_path}")

    def save_trace(self, test_name):
        destination = self.report_dir / f"{test_name}_model_calls.json"
        destination.write_text(json.dumps({
            "model": self.engine.model, "prompt_version": self.runtime.prompt_version,
            "judge_mode": "individual" if self.individual_judging else "batched",
            "calls": self.calls,
        }, indent=2) + "\n")


class RecordingEngine:
    """Keep exact model inputs and responses, including decomposition and synthesis."""

    def __init__(self, engine, calls):
        self.engine = engine
        self.calls = calls
        self.model = engine.model
        self.name = engine.name

    @property
    def temperature(self):
        return getattr(self.engine, "temperature", None)

    @property
    def max_tokens(self):
        return getattr(self.engine, "max_tokens", None)

    def generate(self, prompt, **kwargs):
        try:
            response = self.engine.generate(prompt, **kwargs)
        except Exception as exc:
            self.calls.append({"prompt": prompt, **kwargs, "error_type": type(exc).__name__})
            raise
        self.calls.append({"prompt": prompt, **kwargs, "response": response})
        return response
