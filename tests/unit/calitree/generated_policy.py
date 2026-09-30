"""Compatibility imports: generated-policy implementation lives in core."""

from critical.core.optimization.prompt.calitree.decomposition import (
    CompiledPolicy as GeneratedPolicy, ModelRubricCompiler as RubricCompiler,
    parse_policy, load_templates,
)
from critical.core.optimization.prompt.calitree.decomposition.policy import (
    COUNTS, STATUSES, LABELS, OPERATORS, evaluate_expression, validate_expression,
)

COMPILE_POLICY = load_templates().compile_policy
