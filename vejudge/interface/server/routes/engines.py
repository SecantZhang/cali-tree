"""POST /api/engines/health-check — probe the LM gateway endpoints for the LM Engine Node's
secondary tab "Test this engine" button.

Wraps ``vejudge.lm_engine.health.healthy_order`` (the same probe the CLI ``run/
check_endpoints.sh`` uses), which sends one tiny real chat-completion per endpoint. That's a
billable call, so it's gated behind ``allow_live`` via the same ``require_live`` path the
Judge nodes use — refuse with a 400 (no call made) when it's not set. Credentials come from
``load_creds()`` (the interface's saved manual creds, or env), never from the request.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ....lm_engine import LiveCallNotAllowed, load_creds, require_live
from ....lm_engine import health
from ..schemas import EndpointHealthOut, EngineHealthCheckIn, EngineHealthCheckOut

router = APIRouter(prefix="/api/engines", tags=["engines"])


@router.post("/health-check", response_model=EngineHealthCheckOut)
def health_check(body: EngineHealthCheckIn) -> EngineHealthCheckOut:
    try:
        require_live(body.allow_live, context="An engine health check")
    except LiveCallNotAllowed as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        creds = load_creds()
    except RuntimeError as e:
        # No credentials configured at all — a clear 400 rather than a 500 stack trace.
        raise HTTPException(status_code=400, detail=str(e)) from e

    _ordered, results = health.healthy_order(creds, model=body.model)
    return EngineHealthCheckOut(
        endpoints=[EndpointHealthOut(**r) for r in results]
    )
