"""Media preprocessing and sampling (templates only in v1).

The peanut benchmark feeds whole rendered videos (Strategy A) to the video judges, so
no preprocessing is required yet. This package holds the abstract base for frame /
keyframe / clip sampling strategies to be added later.
"""
"""Media preprocessing implementations."""

from .edit_decomposition import (
    PREPROCESSOR_VERSION,
    EditDecompositionConfig,
    EditDecompositionPreprocessor,
    VideoDependencyError,
)

__all__ = [
    "PREPROCESSOR_VERSION",
    "EditDecompositionConfig",
    "EditDecompositionPreprocessor",
    "VideoDependencyError",
]
