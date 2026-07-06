"""FastAPI app factory for the VEJudge interface backend.

CORS is enabled for any localhost/127.0.0.1 origin — the backend and frontend run as two
separate local processes (dev server, prod preview, or the E2E suite's own preview
instance, each on its own port), and this API has no auth and is local-only by design
(see interface.md), so restricting by loopback origin rather than one hardcoded port is
both more correct and no less safe.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import datasets, graphs, nodes, runs, settings, workflows, ws

# Matches http://localhost:<any port> and http://127.0.0.1:<any port>.
LOCAL_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1):\d+$"


def create_app() -> FastAPI:
    app = FastAPI(title="VEJudge Interface API")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=LOCAL_ORIGIN_REGEX,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(nodes.router)
    app.include_router(graphs.router)
    app.include_router(workflows.router)
    app.include_router(runs.router)
    app.include_router(ws.router)
    app.include_router(datasets.router)
    app.include_router(settings.router)
    return app
