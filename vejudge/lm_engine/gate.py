"""Guard for real (billable) gateway calls.

Real calls cost budget, so they must be explicitly authorized: pass ``--live`` on the
CLIs (or set ``VEJUDGE_ALLOW_LIVE=1``). Everything else — unit tests (mocked), dry-runs,
item matching — never trips this guard.
"""

from __future__ import annotations

import os
from typing import Optional


class LiveCallNotAllowed(RuntimeError):
    """Raised when a real gateway call is attempted without authorization."""


def live_allowed(explicit: Optional[bool] = None) -> bool:
    """True if real calls are authorized (explicit flag wins, else env var)."""
    if explicit is not None:
        return explicit
    return os.environ.get("VEJUDGE_ALLOW_LIVE", "").strip().lower() in {"1", "true", "yes"}


def require_live(explicit: Optional[bool] = None, *, context: str = "this operation") -> None:
    if not live_allowed(explicit):
        raise LiveCallNotAllowed(
            f"{context} would make real gateway calls (costs budget). "
            "Re-run with --live (or set VEJUDGE_ALLOW_LIVE=1) to authorize, "
            "or use --dry-run to estimate without calling."
        )
