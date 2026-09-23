"""Server-test process context helpers.

Production uses a clean ``spawn`` worker. Unit route tests intentionally use ``fork`` on
POSIX so their existing monkeypatched config paths and fake transports are inherited by
the child; lifecycle-specific tests still instantiate their own spawn registry.
"""

from __future__ import annotations

import multiprocessing

import pytest

from vejudge.interface.server.run_registry import REGISTRY


@pytest.fixture(autouse=True)
def _inherit_route_test_monkeypatches_in_workers():
    if "fork" not in multiprocessing.get_all_start_methods():
        yield
        return
    previous = REGISTRY._mp
    REGISTRY._mp = multiprocessing.get_context("fork")
    try:
        yield
    finally:
        REGISTRY._mp = previous
