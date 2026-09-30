"""GEPA 0.1.4 JSON-lines RPC worker. All model calls belong to the parent."""

import contextlib
from importlib.metadata import version
import json
import sys


def run(request):
    if version("gepa") != "0.1.4":
        raise RuntimeError("CaliTree requires gepa==0.1.4 in the isolated interpreter")
    import gepa
    from gepa.core.adapter import EvaluationBatch
    from gepa.utils.stop_condition import MaxCandidateProposalsStopper

    wire = sys.stdout

    def rpc(event, **payload):
        wire.write(json.dumps({"event": event, **payload}) + "\n")
        wire.flush()
        line = sys.stdin.readline()
        if not line:
            raise RuntimeError("Parent closed the GEPA RPC channel")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["result"]

    class Adapter:
        propose_new_texts = None

        def evaluate(self, batch, candidate, capture_traces=False):
            rows = rpc("evaluate", ids=[item["id"] for item in batch],
                       prompt=candidate["system_prompt"])
            return EvaluationBatch(outputs=rows, scores=[row["score"] for row in rows],
                                   trajectories=rows if capture_traces else None)

        def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
            records = [{"Inputs": row["inputs"], "Generated Outputs": row["output"],
                        "Feedback": row["feedback"]} for row in eval_batch.trajectories or []]
            return {key: records for key in components_to_update}

    def reflect(messages):
        return rpc("reflect", messages=messages)

    with contextlib.redirect_stdout(sys.stderr):
        result = gepa.optimize(
            seed_candidate={"system_prompt": request["prompt"]},
            trainset=[{"id": key} for key in request["ids"]],
            valset=[{"id": key} for key in request["ids"]],
            adapter=Adapter(), reflection_lm=reflect,
            candidate_selection_strategy="current_best", skip_perfect_score=False,
            reflection_minibatch_size=min(3, len(request["ids"])),
            use_merge=False, stop_callbacks=MaxCandidateProposalsStopper(request["max_steps"]),
            seed=request["seed"], display_progress_bar=False, cache_evaluation=False,
            raise_on_exception=True,
        )
    return {"event": "done", "candidates": result.candidates,
            "parents": result.parents, "best_index": result.best_idx,
            "num_candidates": result.num_candidates}


if __name__ == "__main__":
    try:
        result = run(json.loads(sys.stdin.readline()))
    except Exception as error:
        result = {"event": "error", "error": f"{type(error).__name__}: {error}"}
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
    sys.exit(1 if result["event"] == "error" else 0)
