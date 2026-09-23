import pytest

from vejudge.checkpoint import CheckpointStore
from vejudge.interface.server.registry import NodeRunContext
from vejudge.logging.exp_logger import make_exp_run


@pytest.fixture
def make_ctx(tmp_path):
    """Factory for a NodeRunContext backed by a real (tmp_path) ExperimentRun."""

    def _make(node_id="n1", params=None, inputs=None, dry_run=True, allow_live=False):
        run_dir = tmp_path / node_id
        run = make_exp_run(run_dir=run_dir)
        checkpoint = CheckpointStore(run_dir / "judge_results.jsonl")
        return NodeRunContext(
            node_id=node_id,
            params=params or {},
            inputs=inputs or {},
            run=run,
            checkpoint=checkpoint,
            dry_run=dry_run,
            allow_live=allow_live,
        )

    return _make
