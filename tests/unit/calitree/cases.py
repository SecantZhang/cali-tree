"""Two requirements and their complete four-case truth table."""

COLOR_RULE = "The object's color must be red."
SHAPE_RULE = "The object's shape must be circular."
PRIORITIES = [
    "Return yes when all listed requirements are satisfied.",
    "Return partial when some, but not all, listed requirements are satisfied.",
    "Return no when none of the listed requirements are satisfied.",
]
CONSTRAINTS = [
    "Return JSON with exactly the fields label and rationale.",
    "The label must be no, partial, or yes.",
]


def rubric(*requirements):
    return "\n".join([
        "Judge only the explicitly listed requirements using the supplied object evidence.",
        "Requirements:", *requirements,
        "Decision priorities:", *PRIORITIES,
        "Output constraints:", *CONSTRAINTS,
    ])


ORIGINAL_PROMPT = rubric(COLOR_RULE, SHAPE_RULE)
COLOR_PROMPT = rubric(COLOR_RULE)
SHAPE_PROMPT = rubric(SHAPE_RULE)
CONFLICT_PROMPT = rubric("The object's color must be blue.")

# IDs carry no label hints; targets are never sent to the model.
SAMPLES = {
    "c1": {"color": "red", "shape": "circular"},
    "c2": {"color": "red", "shape": "square"},
    "c3": {"color": "blue", "shape": "circular"},
    "c4": {"color": "blue", "shape": "square"},
}
TARGETS = {"c1": "yes", "c2": "partial", "c3": "partial", "c4": "no"}
COLOR_TARGETS = {"c1": "yes", "c2": "yes", "c3": "no", "c4": "no"}
SHAPE_TARGETS = {"c1": "yes", "c2": "no", "c3": "yes", "c4": "no"}

VALIDATION_SAMPLES = {
    "v1": {"color": "red", "shape": "circular", "material": "wood"},
    "v2": {"color": "red", "shape": "triangular", "material": "metal"},
    "v3": {"color": "green", "shape": "circular", "material": "wood"},
    "v4": {"color": "green", "shape": "triangular", "material": "metal"},
}
VALIDATION_TARGETS = {"v1": "yes", "v2": "partial", "v3": "partial", "v4": "no"}
