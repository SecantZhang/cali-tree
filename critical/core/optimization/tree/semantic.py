"""Small CART programs over explicit shared semantic roles.

The role mapper is a fixed, auditable scaffold, not a learned concept ontology.
No instruction entities, condition IDs, rationales, labels, or category IDs enter
features. Learned programs compose the observations; they do not re-observe images.
"""
from collections import Counter
from copy import deepcopy
import math
import re

from .base import DecisionProgram

LABELS = ("no", "partial", "yes")
STATES = ("complete", "partial", "absent", "unknown", "not_applicable")
ROLES = ("requested_change", "target_binding", "preservation")
SCHEMA_VERSION = "calitree-semantic-roles-v1"
ROLE_PATTERNS = {
    "preservation": (
        r"^preserv\w*\b", r"\brest of (?:the )?(?:source )?scene\b",
        r"\b(?:scene|all other|background).{0,100}\bpreserv\w*\b",
        r"\boverall scene\b", r"\ball other (?:scene|visible|aspects|elements)\b",
    ),
    "target_binding": (
        r"^identify\b", r"\bcorrectly identified\b",
        r"^the .+ being moved is .+ not a different\b",
        r"\bremain present and identifiable\b",
    ),
}


def condition_role(requirement):
    """Assign from requirement text only; preserve mixed checks for an audit."""
    if not isinstance(requirement, str) or not requirement.strip():
        raise ValueError("A requirement needs nonempty text")
    for role, patterns in ROLE_PATTERNS.items():
        if any(re.search(pattern, requirement.lower()) for pattern in patterns):
            return role
    return "requested_change"


def schema_manifest(kind="roles"):
    if kind not in {"pooled", "roles"}:
        raise ValueError("Unknown feature schema")
    return {"version": SCHEMA_VERSION, "kind": kind,
            "role_patterns": deepcopy(ROLE_PATTERNS), "states": list(STATES),
            "feature_definition": "Per-role presence of each observed state; NA only for an empty role",
            "learned_ontology": False}


def feature_names(kind="roles"):
    schema_manifest(kind)
    return [f"{role}:{state}" for role in (("all_checks",) if kind == "pooled" else ROLES)
            for state in STATES]


def encode_conditions(conditions, statuses, kind="roles"):
    """Return binary state-presence features, retaining unknown separately.

    A missing/failed check is not an observation and must not be imputed here.
    The experiment separately gates incomplete and unknown draws for matched coverage.
    """
    names = feature_names(kind)
    ids = [c["id"] for c in conditions]
    if not ids or len(set(ids)) != len(ids) or set(statuses) != set(ids):
        raise ValueError("Need exactly one status per distinct condition")
    roles = ("all_checks",) if kind == "pooled" else ROLES
    buckets = {role: [] for role in roles}
    for condition in conditions:
        status = statuses[condition["id"]]
        if status not in STATES[:-1]:
            raise ValueError("Invalid observation state")
        role = "all_checks" if kind == "pooled" else condition_role(condition["requirement"])
        buckets[role].append(status)
    values = {f"{role}:{state}": float(state in (states or ["not_applicable"]))
              for role, states in buckets.items() for state in STATES}
    return [values[name] for name in names]


def fixed_prediction(statuses):
    if not statuses or any(s not in STATES[:3] for s in statuses):
        return "unresolved"
    return "no" if "absent" in statuses else "partial" if "partial" in statuses else "yes"


def case_weights(rows):
    counts = Counter(row["case_id"] for row in rows)
    return [1 / counts[row["case_id"]] for row in rows]


class SharedDecisionTree(DecisionProgram):
    """Portable classifier with minimum leaf support measured in case mass.

    Each case has total weight one regardless of repeat count. Class weights are
    deliberately not applied: they would invalidate the case-mass support bound.
    """
    version = "calitree-shared-cart-v1"

    def __init__(self, names, *, max_depth=2, min_cases_leaf=2):
        if max_depth not in {1, 2, 3} or min_cases_leaf < 1:
            raise ValueError("Use depth 1-3 and positive case support")
        self.names = list(names)
        if not self.names or len(set(self.names)) != len(self.names):
            raise ValueError("Need distinct feature names")
        self.max_depth, self.min_cases_leaf = max_depth, min_cases_leaf
        self.tree = None

    def fit(self, rows):
        from sklearn.tree import DecisionTreeClassifier
        if not rows:
            raise ValueError("No training observations")
        for row in rows:
            self._validate_features(row["features"])
            if row["target"] not in LABELS or not row["case_id"]:
                raise ValueError("Invalid training record")
        weights = case_weights(rows)
        cases = len({row["case_id"] for row in rows})
        model = DecisionTreeClassifier(
            max_depth=self.max_depth, random_state=44,
            # Floating accumulation of fractional repeat weights can otherwise
            # reject a split whose children meet the support bound exactly.
            min_weight_fraction_leaf=max(0, min(0.5, self.min_cases_leaf / cases) - 1e-12),
        ).fit([row["features"] for row in rows], [row["target"] for row in rows],
              sample_weight=weights)
        paths = model.decision_path([row["features"] for row in rows])

        def export(index):
            selected = [i for i in range(len(rows)) if paths[i, index]]
            counts = {label: sum(weights[i] for i in selected if rows[i]["target"] == label)
                      for label in LABELS}
            label = max(LABELS, key=lambda name: (counts[name], -LABELS.index(name)))
            total = sum(counts.values())
            result = {"label": label, "case_support": len({rows[i]["case_id"] for i in selected}),
                      "case_mass": total, "class_distribution": {k: v / total for k, v in counts.items()},
                      "class_mass": counts, "leaf": True}
            left, right = model.tree_.children_left[index], model.tree_.children_right[index]
            # Too few independent cases must produce a stump, even if the library
            # can split with the capped min_weight_fraction_leaf parameter.
            if left != right and cases >= 2 * self.min_cases_leaf:
                children = [export(left), export(right)]
                if all(child["case_support"] >= self.min_cases_leaf and
                       child["case_mass"] >= self.min_cases_leaf - 1e-9
                       for child in children):
                    result.update(leaf=False, feature=self.names[model.tree_.feature[index]],
                                  threshold=float(model.tree_.threshold[index]),
                                  left=children[0], right=children[1])
            return result

        self.tree = export(0)
        return self

    def _validate_features(self, values):
        if len(values) != len(self.names) or any(
            not isinstance(x, (int, float)) or not math.isfinite(x) or x not in {0, 1}
            for x in values
        ):
            raise ValueError("Expected a complete binary schema feature vector")

    def decision(self, features):
        self._validate_features(features)
        if self.tree is None:
            raise ValueError("Fit or restore the program first")
        values = dict(zip(self.names, features))
        node, path = self.tree, []
        while not node["leaf"]:
            matched = values[node["feature"]] <= node["threshold"]
            path.append({"feature": node["feature"], "value": values[node["feature"]],
                         "threshold": node["threshold"], "left": matched})
            node = node["left"] if matched else node["right"]
        return {"label": node["label"], "path": path,
                "case_support": node["case_support"],
                "class_distribution": deepcopy(node["class_distribution"])}

    def predict(self, features):
        return self.decision(features)["label"]

    def to_dict(self):
        if self.tree is None:
            raise ValueError("No fitted program")
        return {"version": self.version, "feature_names": self.names,
                "max_depth": self.max_depth, "min_cases_leaf": self.min_cases_leaf,
                "tree": deepcopy(self.tree), "probabilities_calibrated": False}

    @classmethod
    def from_dict(cls, value):
        if value.get("version") != cls.version:
            raise ValueError("Unsupported program version")
        program = cls(value["feature_names"], max_depth=value["max_depth"],
                      min_cases_leaf=value["min_cases_leaf"])

        def validate(node, depth):
            if depth > program.max_depth or type(node.get("leaf")) is not bool:
                raise ValueError("Invalid tree structure")
            if node.get("label") not in LABELS or node.get("case_support", 0) < 1:
                raise ValueError("Invalid leaf support or label")
            probs = node.get("class_distribution", {})
            if set(probs) != set(LABELS) or any(not math.isfinite(x) or not 0 <= x <= 1 for x in probs.values()) or not math.isclose(sum(probs.values()), 1):
                raise ValueError("Invalid class distribution")
            if not node["leaf"]:
                if node.get("feature") not in program.names or node.get("threshold") != 0.5:
                    raise ValueError("Invalid split")
                validate(node["left"], depth + 1)
                validate(node["right"], depth + 1)
        validate(value["tree"], 0)
        program.tree = deepcopy(value["tree"])
        return program

    def rule_text(self):
        def render(node, indent=""):
            if node["leaf"]:
                return f"{indent}predict {node['label']} (support={node['case_support']} cases)\n"
            return (f"{indent}if {node['feature']} == 0:\n" + render(node["left"], indent + "  ")
                    + f"{indent}else:\n" + render(node["right"], indent + "  "))
        return render(self.to_dict()["tree"])
