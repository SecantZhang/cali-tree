"""Subprocess transport for GEPA, with host-owned evaluations and reflection."""

from collections import Counter
import json
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import tempfile
from threading import Thread


class BudgetExhausted(RuntimeError):
    def __init__(self, message, *, proposals=0, events=None):
        super().__init__(message)
        self.proposals, self.events = proposals, events or []


def resolve_gepa_python(configured=None):
    root = next((p for p in [*Path(__file__).resolve().parents, Path.cwd(), *Path.cwd().parents]
                 if (p / "pyproject.toml").exists()), Path.cwd())
    candidate = Path(configured).expanduser() if configured else root / ".venv-gepa" / "bin" / "python"
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise ValueError("GEPA interpreter unavailable; set gepa_python or run run/setup_calitree_gepa.sh")
    # Validate before fit judging can incur any model calls. Never install implicitly.
    checked = subprocess.run([str(candidate.absolute()), "-I", "-c",
        "import sys; from importlib.metadata import version; import gepa; "
        "assert sys.version_info >= (3, 10) and version('gepa') == '0.1.4'"],
        capture_output=True, text=True, timeout=15)
    if checked.returncode:
        raise ValueError("GEPA interpreter requires Python >= 3.10 and gepa==0.1.4; run run/setup_calitree_gepa.sh")
    return str(candidate.absolute())  # resolving a venv symlink loses its environment


class GepaSearch:
    def __init__(self, python=None, seed=44, timeout=300):
        self.python, self.seed, self.timeout = python, seed, timeout

    def search(self, prompt, ids, context, max_steps, evaluate):
        python = resolve_gepa_python(self.python)
        if context.services.reflect is None:
            raise ValueError("GEPA requires a reflection callback")
        counts = Counter(context.targets[key] for key in ids)
        allowed = set(ids)
        env = {key: value for key, value in os.environ.items()
               if key in {"PATH", "SYSTEMROOT", "TMPDIR", "LANG"}}
        events = []
        with tempfile.TemporaryFile(mode="w+") as errors:
            process = subprocess.Popen([python, "-I", "-u", str(Path(__file__).with_name("gepa_worker.py"))],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=errors, text=True, env=env)
            queue = Queue()

            def read():
                for line in process.stdout:
                    queue.put(line)
                queue.put(None)

            reader = Thread(target=read, daemon=True)
            reader.start()

            def send(value):
                process.stdin.write(json.dumps(value) + "\n")
                process.stdin.flush()

            try:
                send({"prompt": prompt, "ids": ids, "max_steps": max_steps, "seed": self.seed})
                while True:
                    try:
                        line = queue.get(timeout=self.timeout)
                    except Empty as error:
                        raise RuntimeError("GEPA RPC timed out") from error
                    if line is None:
                        errors.seek(0)
                        raise RuntimeError("GEPA worker exited without a result: " + errors.read()[-1000:])
                    message = json.loads(line)
                    event = message.get("event")
                    if event == "done":
                        return {**message, "events": events,
                                "proposals": sum(e["event"] == "reflect" for e in events)}
                    if event == "error":
                        raise RuntimeError(message["error"])
                    available = context.services.budget_available
                    if available is not None and not available():
                        raise BudgetExhausted("Optimizer budget exhausted",
                            proposals=sum(row["event"] == "reflect" for row in events), events=events)
                    events.append({"event": event})
                    if event == "evaluate":
                        batch = message["ids"]
                        if not batch or any(key not in allowed for key in batch):
                            raise ValueError("GEPA requested cases outside its fit group")
                        result = evaluate(message["prompt"])
                        rows = []
                        for key in batch:
                            output = result.predictions[key]
                            # The full-set average equals balanced accuracy.
                            weight = len(ids) / (len(counts) * counts[context.targets[key]])
                            rows.append({"score": weight if key in result.correct_ids else 0.0,
                                         "inputs": {"instruction": (context.samples[key].get("instruction") or
                                                       (context.samples[key].get("input") or {}).get("instruction", ""))},
                                         "output": {k: output.get(k) for k in ("label", "rationale")},
                                         "feedback": f"Target label: {context.targets[key]}. Revise reusable decision boundaries; "
                                                     "never copy item identifiers or prescribe this case's answer."})
                        send({"result": rows})
                    elif event == "reflect":
                        send({"result": context.services.reflect(message["messages"])})
                    else:
                        raise ValueError(f"Unknown GEPA event {event!r}")
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                process.stdin.close()
                reader.join(timeout=1)
                process.stdout.close()


def gepa_leaf_optimizer(*, python=None, seed=44):
    """Construct a native GEPA optimizer without importing GEPA in the host process."""
    from .composite import OptimizerPlan
    return OptimizerPlan("gepa", gepa_python=python, seed=seed)
