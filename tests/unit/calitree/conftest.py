"""Live calls are opt-in; normal unit-suite runs skip these experiments."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from critical import config
from critical.lm_engine import get_engine, load_creds, require_live
from .helpers import LiveCaliTreeExperiment


def pytest_addoption(parser):
    group = parser.getgroup("calitree experiments")
    group.addoption("--calitree-aurora-output-panels", action="store_true",
                    help="Extract the known AURORA source/output composites before judging.")
    group.addoption("--calitree-live", action="store_true",
                    help="Run the small CaliTree experiments against a real model.")
    group.addoption("--calitree-model", default=config.DEFAULT_TEXT_MODEL,
                    help="Model used for decomposition, synthesis, and decision comparisons.")
    group.addoption("--calitree-engine", choices=["gpt", "gemini"], default="gpt")
    group.addoption("--calitree-max-tokens", type=int, default=2048,
                    help="Maximum output tokens per call; use 4096 for the harder examples.")
    group.addoption("--calitree-report-dir", default=None,
                    help="Report directory; defaults to .cache/calitree-tests/<UTC timestamp>.")
    group.addoption("--calitree-vision-review", action="store_true",
                    help="Audit instruction plans and independently review image observations.")
    group.addoption("--calitree-vision-grounded", action="store_true",
                    help="Bind target/reference objects from SOURCE before inspecting EDITED.")
    group.addoption("--calitree-vision-intent", action="store_true",
                    help="Separate target selectors, requested operations and permitted effects before grounded checks.")
    group.addoption("--calitree-vision-inventory", action="store_true",
                    help="Describe each image without the instruction before intent/grounded comparison.")
    group.addoption("--calitree-vision-baseline-dir", default=None,
                    help="Reuse matching frozen direct baselines/checkpoints for a development ablation.")


@pytest.fixture(scope="session")
def calitree_report_dir(request):
    destination = request.config.getoption("--calitree-report-dir")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = Path(destination) if destination else config.PROJECT_ROOT / ".cache" / "calitree-tests" / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


@pytest.fixture
def experiment(request, tmp_path):
    if not request.config.getoption("--calitree-live"):
        pytest.skip("Real-model test: opt in with --calitree-live")
    require_live(explicit=True, context="CaliTree component experiments")
    kind = request.config.getoption("--calitree-engine")
    engine = get_engine(
        kind, model=request.config.getoption("--calitree-model"),
        creds=load_creds(engine=kind), temperature=0,
        max_tokens=request.config.getoption("--calitree-max-tokens"), timeout=60,
    )
    instance = LiveCaliTreeExperiment(
        engine, tmp_path, request.getfixturevalue("calitree_report_dir"),
    )
    try:
        yield instance
    finally:
        instance.save_trace(request.node.name)


@pytest.fixture
def hard_experiment(experiment):
    # Complex comparisons use production-style independent model calls to avoid
    # cross-case interference in one long batched response.
    experiment.individual_judging = True
    return experiment
