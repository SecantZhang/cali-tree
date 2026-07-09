"""GET/POST/DELETE /api/settings/credentials — manual LM-gateway credentials override.

Entered via the interface's Settings modal, persisted to a local gitignored JSON file
(``vejudge.lm_engine.creds.save_manual_creds``) so it survives backend restarts without
needing shell/env-var access. Never echoes the token back — only ``configured``/``source``/
``base_url`` cross the wire in either direction.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ....lm_engine import creds
from ..schemas import CredentialsIn, CredentialsStatusOut

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _status() -> CredentialsStatusOut:
    try:
        resolved, source = creds.load_creds_with_source()
    except RuntimeError:
        return CredentialsStatusOut(configured=False, source="none", base_url=None)
    return CredentialsStatusOut(configured=True, source=source, base_url=resolved.base_url)


@router.get("/credentials", response_model=CredentialsStatusOut)
def get_credentials_status() -> CredentialsStatusOut:
    return _status()


@router.post("/credentials", response_model=CredentialsStatusOut)
def set_credentials(body: CredentialsIn) -> CredentialsStatusOut:
    try:
        creds.save_manual_creds(body.token, body.base_url, body.mirror_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _status()


@router.delete("/credentials", response_model=CredentialsStatusOut)
def delete_credentials() -> CredentialsStatusOut:
    creds.clear_manual_creds()
    return _status()
