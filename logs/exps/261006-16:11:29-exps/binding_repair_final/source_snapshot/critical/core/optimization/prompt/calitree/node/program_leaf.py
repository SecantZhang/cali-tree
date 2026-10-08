"""Program-aware leaves with a separate portable bundle and direct execution."""
from critical.core.decision.artifacts import export_program, restore_program, program_ref
from critical.core.optimization.program.models import ProgramSearchContext
from critical.core.optimization.program.evaluation import validate_partitions

VERSION = "calitree-program-leaves-v1"


class ProgramLeafController:
    def __init__(self, optimizer):
        self.optimizer = optimizer

    def build(self, seed, fit, selection=(), *, groups=None):
        validate_partitions(fit, selection)
        if not fit:
            raise ValueError("Need nonempty fit cases")
        if groups is not None and set(groups) != {c.id for c in fit}:
            raise ValueError("Leaf grouping must cover every fit case exactly")
        grouped = {}
        for case in fit:
            group = str(groups[case.id]) if groups is not None else "shared"
            grouped.setdefault(group, []).append(case)
        executor = self.optimizer.evaluator.executor
        bundle = {"version": VERSION, "programs": {}, "nodes": {}, "seed": export_program(seed),
                  "executor_identity": executor.checker.identity, "max_checks": executor.max_checks}
        for group, cases in sorted(grouped.items()):
            node_id = "leaf:" + group
            result = self.optimizer.optimize(seed, ProgramSearchContext(tuple(cases), tuple(selection), node_id))
            ref = program_ref(result.program)
            bundle["programs"][ref] = export_program(result.program)
            bundle["nodes"][node_id] = {"id": node_id, "program_ref": ref,
                                        "scope_ids": [c.id for c in cases], "result": result.to_dict()}
        validate_program_leaves(bundle)
        return bundle


def validate_program_leaves(bundle):
    if bundle.get("version") != VERSION or not bundle.get("nodes"):
        raise ValueError("Invalid program leaf bundle")
    restore_program(bundle["seed"])
    for ref, value in bundle["programs"].items():
        if program_ref(restore_program(value)) != ref:
            raise ValueError("Program key mismatch")
    for node_id, node in bundle["nodes"].items():
        if node_id != node["id"] or node["program_ref"] not in bundle["programs"]:
            raise ValueError("Unresolved program leaf")
        if node["result"]["program_ref"] != node["program_ref"]:
            raise ValueError("Leaf result binding mismatch")
        restore_program(node["result"])
    return bundle


def judge_program_leaf(bundle, node_id, plan, evidence, executor, *, repeat="inference/0"):
    validate_program_leaves(bundle)
    if bundle["executor_identity"] != executor.checker.identity or bundle["max_checks"] != executor.max_checks:
        raise ValueError("Inference executor differs from the saved leaf execution contract")
    ref = bundle["nodes"][node_id]["program_ref"]
    return executor.execute(restore_program(bundle["programs"][ref]), plan, evidence, repeat=repeat)
