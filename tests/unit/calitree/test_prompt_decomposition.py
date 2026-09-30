"""Does decomposition preserve decisions on a tiny two-requirement rubric?"""

from .cases import ORIGINAL_PROMPT, SAMPLES, TARGETS


def test_prompt_decomposition_preserves_decisions(experiment):
    components = experiment.runtime.extract(ORIGINAL_PROMPT)
    # Recomposition is an experiment: CaliTree normally embeds these components
    # for clustering and continues judging with the original optimized prompt.
    decomposed_prompt = "\n\n".join(
        heading + ":\n" + "\n".join(components[kind])
        for kind, heading in (
            ("criteria", "Requirements"), ("priorities", "Decision priorities"),
            ("constraints", "Output constraints"),
        )
    )
    original = experiment.judge_many(ORIGINAL_PROMPT, SAMPLES)
    decomposed = experiment.judge_many(decomposed_prompt, SAMPLES)
    experiment.report(
        "prompt_decomposition", prompts={"Original prompt": ORIGINAL_PROMPT,
                                         "Recomposed decision components": decomposed_prompt},
        samples=SAMPLES, targets=TARGETS,
        comparisons={"Original": original, "Decomposed": decomposed},
        components=components,
    )
    assert all(components[kind] for kind in ("criteria", "priorities", "constraints"))
    assert experiment.labels(original) == TARGETS, "Original rubric failed the simple truth table"
    assert experiment.labels(decomposed) == TARGETS, "Decomposition lost or changed a decision rule"
    assert experiment.labels(original) == experiment.labels(decomposed)
