"""JSON-safe contracts shared by decomposition, area judges, and calibration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

UnitType = Literal["shot", "edit_boundary", "sequence", "audio_event"]


@dataclass
class ArtifactRef:
    artifact_id: str
    kind: str
    path: str
    sha256: str
    media_type: Optional[str] = None
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ArtifactRef":
        return cls(**value)


@dataclass
class EvaluationUnit:
    unit_id: str
    unit_type: UnitType
    start_seconds: float
    end_seconds: float
    parent_unit_id: Optional[str] = None
    confidence: float = 1.0
    provenance: list[str] = field(default_factory=list)
    applicable_rubrics: list[str] = field(default_factory=list)
    artifacts: list[ArtifactRef] = field(default_factory=list)
    measurements: dict[str, Any] = field(default_factory=dict)
    selected_for_judging: Optional[bool] = None

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvaluationUnit":
        data = dict(value)
        data["artifacts"] = [
            artifact if isinstance(artifact, ArtifactRef) else ArtifactRef.from_dict(artifact)
            for artifact in data.get("artifacts", [])
        ]
        return cls(**data)


@dataclass
class EvidenceManifest:
    item_id: str
    cache_key: str
    evidence_hash: str
    source_video_path: str
    source_video_sha256: str
    preprocessing_config_hash: str
    preprocessor_version: str
    video_metadata: dict[str, Any] = field(default_factory=dict)
    timeline_provenance: dict[str, Any] = field(default_factory=dict)
    units: list[EvaluationUnit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["units"] = [unit.to_dict() for unit in self.units]
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvidenceManifest":
        data = dict(value)
        data["units"] = [
            unit if isinstance(unit, EvaluationUnit) else EvaluationUnit.from_dict(unit)
            for unit in data.get("units", [])
        ]
        return cls(**data)


@dataclass
class EvidenceBundle:
    schema_version: str
    preprocessing_config: dict[str, Any]
    preprocessing_config_hash: str
    preprocessor_version: str
    manifests: dict[str, EvidenceManifest] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "preprocessing_config": self.preprocessing_config,
            "preprocessing_config_hash": self.preprocessing_config_hash,
            "preprocessor_version": self.preprocessor_version,
            "manifests": {
                item_id: manifest.to_dict() for item_id, manifest in self.manifests.items()
            },
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvidenceBundle":
        return cls(
            schema_version=value["schema_version"],
            preprocessing_config=dict(value.get("preprocessing_config") or {}),
            preprocessing_config_hash=value["preprocessing_config_hash"],
            preprocessor_version=value["preprocessor_version"],
            manifests={
                item_id: (
                    manifest
                    if isinstance(manifest, EvidenceManifest)
                    else EvidenceManifest.from_dict(manifest)
                )
                for item_id, manifest in (value.get("manifests") or {}).items()
            },
        )
