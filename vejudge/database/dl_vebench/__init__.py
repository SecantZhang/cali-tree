"""VE-Bench DB loader — public text-driven video-editing quality dataset.

Ships as ``label.txt`` (``filename|human_MOS|edit_prompt``) + ``train_samples/edited`` and
``train_samples/src`` videos sharing a basename. A separate calibration track from peanut
(appearance/content editing, not assembly), anchored on a single ``edit_quality`` human MOS.
"""

from .loader import VeBenchLoader, materialize_vebench_labels

__all__ = ["VeBenchLoader", "materialize_vebench_labels"]
