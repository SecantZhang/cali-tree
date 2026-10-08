"""Construct proposal feedback exclusively from training results."""


def training_feedback(cases, report):
    by_id = {c.id: c for c in cases}
    feedback = []
    for row in report["cases"]:
        case = by_id[row["case_id"]]
        if any(d["label"] != case.target for d in row["draws"]) or len({d["label"] for d in row["draws"]}) > 1:
            feedback.append({"instruction": case.plan.instruction, "target": case.target,
                             "plan": case.plan.to_dict(), "draws": row["draws"]})
    # Correct cases protect against a repair that merely inverts the class boundary.
    controls = [{"instruction": by_id[r["case_id"]].plan.instruction,
                 "target": by_id[r["case_id"]].target, "draws": r["draws"]}
                for r in report["cases"] if all(d["label"] == by_id[r["case_id"]].target for d in r["draws"])]
    return {"failures": feedback, "correct_controls": controls}
