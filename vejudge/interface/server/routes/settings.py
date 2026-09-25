"""GET/POST/DELETE /api/settings/credentials — provider-scoped API credentials.

Entered via the interface's Settings modal, persisted to a local gitignored JSON file
(``vejudge.lm_engine.creds.save_manual_creds``) so it survives backend restarts without
needing shell/env-var access. Never echoes the token back — only ``configured``/``source``/
``base_url`` are returned.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ....lm_engine import creds
from ..schemas import CredentialsIn, CredentialsStatusOut

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _status(provider: str = "openai") -> CredentialsStatusOut:
    try:
        resolved, source = creds.load_creds_with_source(provider=provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError:
        return CredentialsStatusOut(configured=False, source="none", base_url=None)
    return CredentialsStatusOut(configured=True, source=source, base_url=resolved.base_url)


@router.get("/credentials", response_model=CredentialsStatusOut)
def get_credentials_status(provider: str = "openai") -> CredentialsStatusOut:
    return _status(provider)


@router.post("/credentials", response_model=CredentialsStatusOut)
def set_credentials(body: CredentialsIn) -> CredentialsStatusOut:
    try:
        creds.save_manual_creds(body.token, body.base_url, body.mirror_url, provider=body.provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _status(body.provider)


@router.delete("/credentials", response_model=CredentialsStatusOut)
def delete_credentials(provider: str = "openai") -> CredentialsStatusOut:
    try:
        creds.clear_manual_creds(provider=provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _status(provider)
