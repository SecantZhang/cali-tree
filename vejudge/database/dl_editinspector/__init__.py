"""Read-only adapter for the public EditInspector benchmark."""

from .loader import (
    EDITINSPECTOR_REVISION,
    EditInspectorLoader,
    accuracy_level_label,
)

__all__ = [
    "EDITINSPECTOR_REVISION",
    "EditInspectorLoader",
    "accuracy_level_label",
]
