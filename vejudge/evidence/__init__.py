"""Versioned, cached evidence artifacts for edit-aware video judging."""

from .schema import ArtifactRef, EvaluationUnit, EvidenceBundle, EvidenceManifest
from .store import EvidenceStore, LocalEvidenceStore

__all__ = [
    "ArtifactRef",
    "EvaluationUnit",
    "EvidenceBundle",
    "EvidenceManifest",
    "EvidenceStore",
    "LocalEvidenceStore",
]
