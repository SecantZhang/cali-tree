"""Read-only, path-confined media streaming — for the Source/Eval secondary tabs' video
playback.

Nothing else in this codebase serves raw file bytes over HTTP, so this route is the one
place a client-supplied filesystem path is ever trusted enough to read from disk. It's
kept safe by resolving the path and rejecting anything that doesn't fall under one of the
known data roots — never by trusting the caller's string as-is.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from .... import config

router = APIRouter(prefix="/api/media", tags=["media"])

# Only paths already known to originate from this app's own loaders (`output_video_path`,
# `asset_filepaths`, etc. — see dl_peanut_eval/curate.py) ever reach this route from the
# frontend, but the check below doesn't rely on that — it independently confines every
# request to these roots regardless of where the path claims to have come from.
ALLOWED_ROOTS = (config.RENDERED_ROOT, config.DATA_ROOT)


@router.get("")
def get_media(path: str = Query(...)) -> FileResponse:
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}") from e

    if not any(resolved.is_relative_to(root.resolve()) for root in ALLOWED_ROOTS):
        raise HTTPException(status_code=404, detail="Not found")
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    return FileResponse(resolved)
