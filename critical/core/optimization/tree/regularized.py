"""Class-balanced shallow trees with independent support and rubric fallback.

Greedy Gini splitting uses class-balanced case weights; support constraints and
reported class distributions use ordinary case weights. A guarded leaf may retain
the fixed reducer instead of overwriting it on sparse correction evidence.
"""
from collections import Counter
from copy import deepcopy
import math

from .base import DecisionProgram
from .semantic import LABELS, ROLES, STATES, case_weights, condition_role, encode_conditions, feature_names


def fraction_feature_names():
    return feature_names() + [f"{role}:{state}_fraction" for role in ROLES for state in STATES[:-1]]


def encode_fractions(conditions, statuses):
    features = encode_conditions(conditions, statuses)
    buckets = {role: [] for role in ROLES}
    for condition in conditions:
        buckets[condition_role(condition["requirement"])].append(statuses[condition["id"]])
    return features + [values.count(state) / len(values) if values else 0.0
                       for values in buckets.values() for state in STATES[:-1]]


def rubric_prediction(names, values):
    """Derive the existing rubric from observed states, never from metadata."""
    features = dict(zip(names, values))
    if any(features.get(f"{role}:unknown", 0) for role in ROLES):
        return "unresolved"
    if any(features.get(f"{role}:absent", 0) for role in ROLES):
        return "no"
    if any(features.get(f"{role}:partial", 0) for role in ROLES):
        return "partial"
    if any(features.get(f"{role}:complete", 0) for role in ROLES):
        return "yes"
    return "unresolved"


class RegularizedSemanticTree(DecisionProgram):
    """Greedy CART, followed by loss pruning; not globally optimal tree search.

Guarded corrections need at least two distinct source/instruction groups whose
targets support changing the rubric to the proposed label. Repeat draws do not
increase that count. Class-balanced loss, rubric-change penalty, and leaf penalty
are separate from the ordinary case-mass support constraint.
"""
    version = "calitree-regularized-cart-v1"

    def __init__(self, names, *, max_depth=2, min_cases_leaf=2, guarded=False,
                 prior_penalty=0.05, leaf_penalty=0.005, min_correction_groups=2):
        allowed = set(fraction_feature_names())
        if not names or len(set(names)) != len(names) or not set(names) <= allowed:
            raise ValueError("Need declared semantic features")
        if not set(feature_names()) <= set(names):
            raise ValueError("Need the complete role-state schema")
        if max_depth not in (1, 2, 3) or min_cases_leaf < 1 or min_correction_groups < 2:
            raise ValueError("Invalid depth or independent support")
        if any(not math.isfinite(v) or v < 0 for v in (prior_penalty, leaf_penalty)):
            raise ValueError("Invalid regularization penalty")
        self.names = list(names)
        self.max_depth, self.min_cases_leaf = max_depth, min_cases_leaf
        self.guarded = bool(guarded)
        self.prior_penalty = prior_penalty if guarded else 0.0
        self.leaf_penalty, self.min_correction_groups = leaf_penalty, min_correction_groups
        self.tree = None

    def _validate_features(self, values):
        if len(values) != len(self.names):
            raise ValueError("Wrong feature schema length")
        for name, value in zip(self.names, values):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Expected finite semantic features in [0, 1]")
            if not name.endswith("_fraction") and value not in (0, 1):
                raise ValueError("State-presence features must be binary")
        if rubric_prediction(self.names, values) == "unresolved":
            raise ValueError("Unknown or missing observations must remain unresolved outside the tree")

    def fit(self, rows):
        if not rows:
            raise ValueError("No training observations")
        labels, case_groups = {}, {}
        for row in rows:
            self._validate_features(row["features"])
            if row["target"] not in LABELS or not row["case_id"] or not row.get("group"):
                raise ValueError("Invalid training label or independent group")
            key = row["case_id"]
            if key in labels and labels[key] != row["target"]:
                raise ValueError("One case cannot have inconsistent targets")
            if key in case_groups and case_groups[key] != row["group"]:
                raise ValueError("One case cannot have inconsistent source groups")
            labels[key] = row["target"]
            case_groups[key] = row["group"]
        ordinary = case_weights(rows)
        totals = Counter(labels.values())
        objective = [w / (len(totals) * totals[r["target"]]) for r, w in zip(rows, ordinary)]
        total_cases = len(labels)
        fixed = [rubric_prediction(self.names, r["features"]) for r in rows]

        def supports(indices):
            return (sum(ordinary[i] for i in indices) >= self.min_cases_leaf - 1e-9
                    and len({rows[i]["group"] for i in indices}) >= self.min_cases_leaf)

        def gini(indices):
            mass = sum(objective[i] for i in indices)
            counts = [sum(objective[i] for i in indices if rows[i]["target"] == label) for label in LABELS]
            return mass - sum(c * c for c in counts) / mass

        def make_leaf(indices):
            counts = {label: sum(ordinary[i] for i in indices if rows[i]["target"] == label) for label in LABELS}
            mass = sum(counts.values())
            groups = {label: len({rows[i]["group"] for i in indices
                                 if rows[i]["target"] == label and fixed[i] != label}) for label in LABELS}
            options = (["fixed"] if self.guarded else []) + [label for label in LABELS
                       if counts[label] and (not self.guarded or groups[label] >= self.min_correction_groups)]
            def cost(action):
                return sum(objective[i] * ((fixed[i] if action == "fixed" else action) != rows[i]["target"])
                           + self.prior_penalty * ordinary[i] / total_cases
                           * ((fixed[i] if action == "fixed" else action) != fixed[i]) for i in indices)
            costs = {action: cost(action) for action in options}
            minimum = min(costs.values())
            # Preserve deterministic tie order despite fractional case weights.
            action = next(action for action in options if costs[action] <= minimum + 1e-12)
            node = {"leaf": True, "action": action, "case_support": len({rows[i]["case_id"] for i in indices}),
                    "group_support": len({rows[i]["group"] for i in indices}), "case_mass": mass,
                    "class_distribution": {k: v / mass for k, v in counts.items()},
                    "correction_group_support": groups}
            return node, cost(action) + self.leaf_penalty

        def grow(indices, depth):
            leaf, leaf_cost = make_leaf(indices)
            if depth == self.max_depth:
                return leaf, leaf_cost
            parent_impurity, best = gini(indices), None
            for feature, name in enumerate(self.names):
                values = sorted({rows[i]["features"][feature] for i in indices})
                for a, b in zip(values, values[1:]):
                    threshold = (a + b) / 2
                    left = [i for i in indices if rows[i]["features"][feature] <= threshold]
                    right = [i for i in indices if rows[i]["features"][feature] > threshold]
                    if not supports(left) or not supports(right):
                        continue
                    gain = parent_impurity - gini(left) - gini(right)
                    if gain > 1e-12 and (best is None or gain > best[0] + 1e-12):
                        best = (gain, name, threshold, left, right)
            if best is None:
                return leaf, leaf_cost
            _, name, threshold, left, right = best
            lnode, lcost = grow(left, depth + 1)
            rnode, rcost = grow(right, depth + 1)
            if lcost + rcost >= leaf_cost - 1e-12:
                return leaf, leaf_cost
            return {**leaf, "leaf": False, "feature": name, "threshold": threshold,
                    "left": lnode, "right": rnode}, lcost + rcost

        self.tree, _ = grow(list(range(len(rows))), 0)
        return self

    def decision(self, features):
        self._validate_features(features)
        if self.tree is None:
            raise ValueError("Fit or restore the program first")
        values = dict(zip(self.names, features))
        node, path = self.tree, []
        while not node["leaf"]:
            left = values[node["feature"]] <= node["threshold"]
            path.append({"feature": node["feature"], "value": values[node["feature"]],
                         "threshold": node["threshold"], "left": left})
            node = node["left"] if left else node["right"]
        return {"label": rubric_prediction(self.names, features) if node["action"] == "fixed" else node["action"],
                "action": node["action"], "path": path, "case_support": node["case_support"],
                "group_support": node["group_support"], "class_distribution": deepcopy(node["class_distribution"])}

    def predict(self, features):
        return self.decision(features)["label"]

    def to_dict(self):
        if self.tree is None:
            raise ValueError("No fitted program")
        return {"version": self.version, "feature_names": self.names, "tree": deepcopy(self.tree),
                "max_depth": self.max_depth, "min_cases_leaf": self.min_cases_leaf,
                "guarded": self.guarded, "prior_penalty": self.prior_penalty,
                "leaf_penalty": self.leaf_penalty, "min_correction_groups": self.min_correction_groups,
                "fit_loss": "equal class weight, equal case weight within class",
                "probabilities_calibrated": False}

    @classmethod
    def from_dict(cls, artifact):
        if artifact.get("version") != cls.version:
            raise ValueError("Unsupported program version")
        model = cls(artifact["feature_names"], **{key: artifact[key] for key in (
            "max_depth", "min_cases_leaf", "guarded", "prior_penalty", "leaf_penalty", "min_correction_groups")})
        def validate(node, depth):
            if depth > model.max_depth or type(node.get("leaf")) is not bool:
                raise ValueError("Invalid tree structure")
            if node.get("action") not in LABELS + (("fixed",) if model.guarded else ()):
                raise ValueError("Invalid leaf action")
            distribution = node.get("class_distribution", {})
            if set(distribution) != set(LABELS) or any(not math.isfinite(v) or not 0 <= v <= 1
                                                      for v in distribution.values()) or not math.isclose(sum(distribution.values()), 1):
                raise ValueError("Invalid class distribution")
            if min(node.get("case_support", 0), node.get("group_support", 0), node.get("case_mass", 0)) <= 0:
                raise ValueError("Invalid support")
            if model.guarded and node["leaf"] and node["action"] != "fixed" and node.get(
                    "correction_group_support", {}).get(node["action"], 0) < model.min_correction_groups:
                raise ValueError("Unsupported correction")
            if not node["leaf"]:
                if node.get("feature") not in model.names or not 0 < node.get("threshold", -1) < 1:
                    raise ValueError("Invalid split")
                if not node["feature"].endswith("_fraction") and node["threshold"] != .5:
                    raise ValueError("Invalid binary split")
                for child in (node["left"], node["right"]):
                    if child["case_mass"] < model.min_cases_leaf - 1e-9 or child["group_support"] < model.min_cases_leaf:
                        raise ValueError("Insufficient independent split support")
                    validate(child, depth + 1)
        validate(artifact["tree"], 0)
        model.tree = deepcopy(artifact["tree"])
        return model

    def rule_text(self):
        def render(node, indent=""):
            if node["leaf"]:
                action = "use fixed rubric" if node["action"] == "fixed" else f"predict {node['action']}"
                return f"{indent}{action} (support={node['group_support']} groups)\n"
            return (f"{indent}if {node['feature']} <= {node['threshold']:.6g}:\n"
                    + render(node["left"], indent + "  ") + f"{indent}else:\n"
                    + render(node["right"], indent + "  "))
        return render(self.to_dict()["tree"])
