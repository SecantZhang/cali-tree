"""Training references and image roles for supervised visual calibration."""

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path

from PIL import Image

from .vision_models import nonempty_text


def source_pixels(path):
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        return hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()


@dataclass(frozen=True)
class VisualReference:
    """One annotated training pair; annotations never describe the query."""

    id: str
    instruction: str
    condition_requirements: tuple[str, ...]
    source_image: Path
    edited_image: Path
    human_label: str
    human_mean_score: float

    def __post_init__(self):
        nonempty_text(self.id, "Reference ID")
        nonempty_text(self.instruction, "Reference instruction")
        if isinstance(self.condition_requirements, (str, bytes)):
            raise ValueError("Reference requirements must be a sequence, not text")
        requirements = tuple(self.condition_requirements)
        if not requirements or any(not isinstance(r, str) or not r.strip() for r in requirements):
            raise ValueError("Reference condition requirements must be nonempty")
        score = self.human_mean_score
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 2:
            raise ValueError("Reference human mean score must be finite and within 0-2")
        expected = "no" if score < 0.5 else "partial" if score < 1.5 else "yes"
        if self.human_label != expected:
            raise ValueError("Reference label differs from its human mean-score bin")
        object.__setattr__(self, "condition_requirements", requirements)
        for field in ("source_image", "edited_image"):
            path = Path(getattr(self, field)).expanduser().resolve()
            if not path.is_file():
                raise ValueError(f"Missing reference {field}")
            object.__setattr__(self, field, path)

    @property
    def document(self):
        return self.instruction + "\n" + "\n".join(self.condition_requirements)


class VisualReferenceBank:
    """Fit retrieval on training text only; choose one distinct source per class."""

    def __init__(self, references):
        self.references = tuple(references)
        if any(not isinstance(r, VisualReference) for r in self.references):
            raise ValueError("Expected VisualReference training examples")
        ids = [r.id for r in self.references]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate training reference IDs")
        if {r.human_label for r in self.references} != {"no", "partial", "yes"}:
            raise ValueError("Visual calibration requires examples of all three classes")
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=5000, sublinear_tf=True)
        self.vectors = self.vectorizer.fit_transform([r.document for r in self.references])
        self.source_groups = tuple(source_pixels(r.source_image) for r in self.references)
        self.image_hashes = tuple((hashlib.sha256(r.source_image.read_bytes()).hexdigest(),
                                   hashlib.sha256(r.edited_image.read_bytes()).hexdigest()) for r in self.references)

    def select(self, plan, query_source):
        hashes = tuple((hashlib.sha256(r.source_image.read_bytes()).hexdigest(),
                        hashlib.sha256(r.edited_image.read_bytes()).hexdigest()) for r in self.references)
        if hashes != self.image_hashes:
            raise ValueError("Training reference images changed; rebuild the annotated reference bank")
        document = plan.instruction + "\n" + "\n".join(c.requirement for c in plan.conditions)
        similarity = (self.vectors @ self.vectorizer.transform([document]).T).toarray().ravel()
        # Exclude the complete query source group, including differently encoded copies.
        seen = {source_pixels(query_source)}
        chosen = []
        for label in ("no", "partial", "yes"):
            candidates = sorted((i for i, r in enumerate(self.references) if r.human_label == label),
                                key=lambda i: (-similarity[i], self.references[i].id))
            index = next((i for i in candidates if self.source_groups[i] not in seen), None)
            if index is None:
                raise ValueError("Not enough distinct training sources outside the query source")
            chosen.append(index)
            seen.add(self.source_groups[index])
        return tuple(self.references[i] for i in sorted(chosen, key=lambda i: self.references[i].id))


def visual_grade_input(policy, plan, query_media, references=()):
    """Keep role labels adjacent to images, with positions counting images only."""
    if len(query_media) != 2 or any(m.get("type") != "image" or not m.get("path") for m in query_media):
        raise ValueError("Expected a SOURCE/EDITED query image pair")
    examples, media = [], []
    for index, reference in enumerate(references, 1):
        first = len(media) + 1
        examples.append({"id": f"r{index}", "instruction": reference.instruction,
                         "human_label": reference.human_label, "human_mean_score": reference.human_mean_score,
                         "source_image_position": first, "edited_image_position": first + 1})
        media.extend([{"type": "image", "path": str(reference.source_image)},
                      {"type": "image", "path": str(reference.edited_image)}])
    first = len(media) + 1
    media.extend(query_media)
    payload = {"rubric_units": policy.to_dict()["units"],
               "query": {"instruction": plan.instruction, "condition_plan": plan.to_dict()["conditions"],
                         "source_image_position": first, "edited_image_position": first + 1},
               "calibration_examples": examples}
    markers = {}
    for reference in examples:
        for role in ("source", "edited"):
            position = reference[f"{role}_image_position"]
            markers[position] = (f'Image {position}: REFERENCE {reference["id"]} {role.upper()}. '
                                 f'Reference editing instruction: {reference["instruction"]}. '
                                 f'Reference human label: {reference["human_label"]}. This is not the QUERY.')
    for role in ("source", "edited"):
        position = payload["query"][f"{role}_image_position"]
        markers[position] = (f'Image {position}: QUERY {role.upper()}. QUERY editing instruction: {plan.instruction}. '
                             'Evaluate only this QUERY pair; no human annotation is supplied.')
    blocks = []
    for position, image in enumerate(media, 1):
        blocks.extend([{"type": "text", "text": markers[position]}, image])
    return payload, blocks


def parse_visual_grade(value, payload):
    fields = {"label", "rationale", "condition_findings", "rubric_unit_ids", "reference_ids", "rubric_conflicts"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("response fields")
    if value["label"] not in ("no", "partial", "yes") or not isinstance(value["rationale"], str) or not value["rationale"].strip():
        raise ValueError("label/rationale")
    findings = value["condition_findings"]
    if not isinstance(findings, list) or any(not isinstance(f, dict) for f in findings):
        raise ValueError("findings")
    expected = {c["id"] for c in payload["query"]["condition_plan"]}
    if any(not isinstance(f.get("condition_id"), str) for f in findings) or sorted(f["condition_id"] for f in findings) != sorted(expected):
        raise ValueError("condition coverage")
    for finding in findings:
        if set(finding) != {"condition_id", "source_observation", "edited_observation", "fulfillment"} or finding["fulfillment"] not in ("complete", "partial", "absent", "unknown"):
            raise ValueError("finding fields")
        if any(not isinstance(finding[f], str) or not finding[f].strip() for f in ("source_observation", "edited_observation")):
            raise ValueError("observations")
    for field, allowed in (("rubric_unit_ids", {u["id"] for u in payload["rubric_units"]}),
                           ("reference_ids", {r["id"] for r in payload["calibration_examples"]})):
        if not isinstance(value[field], list) or any(not isinstance(i, str) or i not in allowed for i in value[field]):
            raise ValueError("citation IDs")
    if not value["rubric_unit_ids"] or (payload["calibration_examples"] and not value["reference_ids"]):
        raise ValueError("required citations")
    if not isinstance(value["rubric_conflicts"], list) or any(not isinstance(s, str) or not s.strip() for s in value["rubric_conflicts"]):
        raise ValueError("conflicts")
    return value
