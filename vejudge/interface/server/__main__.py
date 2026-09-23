"""``vejudge-interface`` — launch the FastAPI backend for the node-graph interface.

Binds to localhost by default: this API has no auth and is meant for local use only
(see interface.md's non-goals). It makes the same billable-call gate the CLI enforces
(dry-run by default; a real Judge Node run still requires ``--live``/``allow_live``).
"""

from __future__ import annotations

import argparse
from typing import Optional


def main(argv: Optional[list[str]] = None) -> int:
    import uvicorn

    p = argparse.ArgumentParser(description="VEJudge interface backend (FastAPI + uvicorn)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true", help="autoreload on source changes (dev)")
    args = p.parse_args(argv)

    uvicorn.run(
        "vejudge.interface.server.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
