"""Stage execution with immutable pins, explicit predecessor reuse and provenance."""

from copy import deepcopy
import time
from uuid import uuid4

from ..decomposition.artifacts import digest

LEAF_STAGES = ("optimization", "compilation", "instruction_decomposition", "evidence_checks", "aggregation", "validation")
MERGE_STAGES = ("synthesis", "refinement", *LEAF_STAGES[1:])


class StageRunner:
    def __init__(self, stages, *, pins, reuse, load, save, checkpoint, options=None,
                 progress=None, usage=None, should_stop=None):
        self.stages, self.load, self.save, self.checkpoint = stages, load, save, checkpoint
        self.options, self.progress = options or {}, progress
        self.usage, self.should_stop = usage or (lambda: {}), should_stop
        self.pins, self.reuse, self.records = {}, {}, {}
        for collection, references in ((self.pins, pins), (self.reuse, reuse)):
            for stage, reference in (references or {}).items():
                if stage not in stages:
                    raise ValueError(f"Unknown stage {stage}")
                row = load(reference)
                if row.get("version") != "calitree-stage-v1" or row.get("stage") != stage:
                    raise ValueError(f"Invalid artifact for stage {stage}")
                collection[stage] = (reference, row)
        self.start = self.options.get("run_from")
        self.end = self.options.get("run_until") or stages[-1]
        if self.start and self.start not in stages or self.end not in stages:
            raise ValueError("Unknown CaliTree execution stage")
        if self.start and stages.index(self.start) > stages.index(self.end):
            raise ValueError("run_from must precede run_until")
        if self.options.get("action") == "fresh":
            if {"evidence_checks", "aggregation", "validation"} & set(self.pins):
                raise ValueError("Unfreeze evidence checks, aggregation and validation before fresh evaluation")
            self.start, self.end = "evidence_checks", "validation"
        if self.options.get("action") == "metrics":
            if "validation" in self.pins:
                raise ValueError("Unfreeze validation before recomputing metrics")
            self.start, self.end = "validation", "validation"
        if self.start:
            self.options.setdefault("execution_id", uuid4().hex)
        # A downstream pin cannot be checked safely if its unpinned predecessors
        # will change in this action. Reject before any model call.
        if self.start:
            first = stages.index(self.start)
            for pinned in self.pins:
                if stages.index(pinned) > first and any(
                    name not in self.pins for name in stages[first:stages.index(pinned)]
                ):
                    raise ValueError(f"Unfreeze dependent stage {pinned} before rerunning its predecessors")

    def available(self, stage):
        item = self.pins.get(stage) or self.reuse.get(stage)
        return item[1] if item else None

    def check_pins(self, bindings):
        for stage, expected in bindings.items():
            if stage in self.pins:
                actual = self.pins[stage][1].get("binding", {})
                if actual != expected:
                    raise ValueError(f"Pinned {stage} is incompatible with current prompt, instructions or evidence; unfreeze it")

    def includes(self, stage):
        return self.stages.index(stage) <= self.stages.index(self.end)

    def run(self, stage, inputs, binding, compute):
        if self.should_stop and self.should_stop():
            raise InterruptedError("CaliTree stage execution stopped")
        identity = digest(inputs)
        reference = None
        cached = self.pins.get(stage)
        source = "pinned" if cached else "computed"
        forced = self.start is not None and self.stages.index(stage) >= self.stages.index(self.start)
        if cached:
            reference, row = cached
            if row["binding"] != binding:
                raise ValueError(f"Pinned {stage} is incompatible; unfreeze it")
        else:
            candidate = self.reuse.get(stage)
            if not forced and candidate and candidate[1]["input_digest"] == identity and candidate[1]["binding"] == binding:
                reference, row = candidate
                source = "cached"
            else:
                key = "calitree:stage:" + digest([stage, identity, binding, self.options.get("execution_id") if forced else None])
                if self.checkpoint.has(key):
                    reference = self.checkpoint.get(key)
                    row = self.load(reference)
                    source = "checkpoint"
                else:
                    if self.start and self.stages.index(stage) < self.stages.index(self.start):
                        raise ValueError(f"Completed predecessor {stage} is missing or changed; run from that stage first")
                    if self.progress:
                        self.progress(stage, {"state": "running"})
                    before, started = self.usage(), time.perf_counter()
                    try:
                        data = compute()
                    except Exception as error:
                        if self.progress: self.progress(stage, {"state": "error", "error": str(error)})
                        raise RuntimeError(f"Stage {stage} failed: {error}") from error
                    after = self.usage()
                    row = {"version": "calitree-stage-v1", "stage": stage,
                           "input_digest": identity, "inputs": deepcopy(inputs), "binding": deepcopy(binding), "data": data,
                           "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                           "usage": {key: after.get(key, 0) - value for key, value in before.items()}}
                    reference = self.save(stage, row)
                    self.checkpoint.put(key, reference)
        record = {"state": "complete", "source": source, "artifact_ref": reference,
                  "stale_inputs": row["input_digest"] != identity,
                  "binding": row["binding"], "elapsed_ms": row["elapsed_ms"],
                  "original_usage": row["usage"], "usage": row["usage"] if source == "computed" else {}}
        self.records[stage] = record
        if self.progress:
            self.progress(stage, record)
        return deepcopy(row["data"])
