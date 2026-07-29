"""Official TextGrad 0.1.8 adapter over VEJudge's logged/gated LMEngine."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Optional


def make_textgrad_engine(
    engine: Any, *, usage_cb: Optional[Callable[[dict[str, Any]], None]] = None
) -> Any:
    try:
        from textgrad.engine import EngineLM
    except ImportError as exc:
        raise RuntimeError(
            "Cali-Tree requires textgrad==0.1.8; install with pip install -e '.[calitree]'"
        ) from exc

    class VEJudgeTextGradEngine(EngineLM):
        model_string = str(engine.model)

        def generate(self, prompt: Any, system_prompt: Optional[str] = None, **_kwargs: Any) -> str:
            result = engine.generate(str(prompt), system=system_prompt)
            if usage_cb:
                usage_cb(result)
            return str(result.get("content") or "")

        def __call__(
            self, prompt: Any, system_prompt: Optional[str] = None, **kwargs: Any
        ) -> str:
            return self.generate(prompt, system_prompt=system_prompt, **kwargs)

    return VEJudgeTextGradEngine()


def textgrad_update(
    prompt: str,
    feedback: str,
    *,
    engine: Any,
    usage_cb: Optional[Callable[[dict[str, Any]], None]] = None,
    log_dir: Optional[str | Path] = None,
) -> str:
    """Run one official TextualGradientDescent update from externally grounded feedback."""
    if log_dir is not None:
        # textgrad 0.1.8 creates its own JSONL handler at import time. Point that side log
        # inside the run-scoped experiment directory instead of the process working tree.
        os.environ["TEXTGRAD_LOG_DIR"] = str(log_dir)
    try:
        import textgrad as tg
    except ImportError as exc:
        raise RuntimeError(
            "Cali-Tree requires textgrad==0.1.8; install with pip install -e '.[calitree]'"
        ) from exc
    variable = tg.Variable(
        prompt,
        requires_grad=True,
        role_description=(
            "general ImagenHub Semantic Consistency image-editing rubric that must "
            "classify no/partial/yes and preserve the JSON output contract"
        ),
    )
    gradient = tg.Variable(
        feedback,
        requires_grad=False,
        role_description="grounded calibration feedback",
    )
    variable.gradients.add(gradient)
    optimizer = tg.TGD(
        parameters=[variable],
        engine=make_textgrad_engine(engine, usage_cb=usage_cb),
        constraints=[
            "Return a reusable rubric, never item identifiers or memorized image details.",
            "Preserve labels no, partial, yes and JSON fields label and rationale.",
            (
                "When the rubric uses rubric_version sc-v3, preserve rubric_scores and its "
                "requested_change, subject_identity, spatial_relation, and scene_continuity "
                "fields exactly; refine decision guidance without deleting the decomposition."
            ),
            (
                "Optimize only Semantic Consistency: standalone perceptual quality must not "
                "change the label unless conditions or source content become unrecognizable."
            ),
            (
                "Never infer a human label from instruction wording, editor identity, item "
                "order, or any other target-leaking shortcut."
            ),
        ],
    )
    optimizer.step()
    return str(variable.value)
