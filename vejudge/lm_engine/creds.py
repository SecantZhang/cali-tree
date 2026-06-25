"""Load Pluto gateway credentials.

Primary source is the ``.env-raw`` blurb shipped in the repo root (a human-readable
file, NOT key=value), parsed with regexes. Standard environment variables take
precedence when set, so CI / other machines can inject creds the usual way.

The token is never logged.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import config

_TOKEN_RE = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b")
_URL_RE = re.compile(r"https?://[^\s\"']+")


@dataclass
class PlutoCreds:
    token: str
    base_url: str
    mirror_url: Optional[str] = None
    # When set (e.g. by a health check), overrides the default base→mirror order.
    preferred: Optional[list[str]] = None

    @property
    def endpoints(self) -> list[str]:
        if self.preferred:
            return [u.rstrip("/") for u in self.preferred if u]
        urls = [self.base_url]
        if self.mirror_url and self.mirror_url != self.base_url:
            urls.append(self.mirror_url)
        return [u.rstrip("/") for u in urls if u]

    @property
    def default_endpoints(self) -> list[str]:
        """The base→mirror order, ignoring any health-based preference."""
        urls = [self.base_url]
        if self.mirror_url and self.mirror_url != self.base_url:
            urls.append(self.mirror_url)
        return [u.rstrip("/") for u in urls if u]


def _from_env() -> tuple[str, str, Optional[str]]:
    token = (
        os.environ.get("CHAT_GPT_API_KEY", "").strip()
        or os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
    )
    base = (
        os.environ.get("OPENAI_COMPAT_BASE_URL", "").strip()
        or os.environ.get("LLM_PROXY_BASE_URL", "").strip()
    )
    mirror = os.environ.get("LLM_PROXY_MIRROR_URL", "").strip() or None
    return token, base, mirror


def _parse_env_raw(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract (token, primary_url, mirror_url) from the .env-raw blurb."""
    token_m = _TOKEN_RE.search(text)
    token = token_m.group(0) if token_m else None

    primary: Optional[str] = None
    mirror: Optional[str] = None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        low = line.lower()
        # The URL usually sits on the line after the "... Endpoint" header.
        if "primary" in low and "endpoint" in low:
            primary = _first_url(lines[i : i + 3])
        elif "mirror" in low and "endpoint" in low:
            mirror = _first_url(lines[i : i + 3])

    if primary is None:
        # Fall back to first/second URL anywhere in the file.
        urls = _URL_RE.findall(text)
        if urls:
            primary = urls[0]
            if len(urls) > 1:
                mirror = mirror or urls[1]
    return token, primary, mirror


def _first_url(lines: list[str]) -> Optional[str]:
    for ln in lines:
        m = _URL_RE.search(ln)
        if m:
            return m.group(0)
    return None


def load_creds(env_raw_path: Optional[Path] = None) -> PlutoCreds:
    """Return credentials, preferring real env vars, then the .env-raw file."""
    token, base, mirror = _from_env()

    if not (token and base):
        path = Path(env_raw_path) if env_raw_path else config.ENV_RAW_PATH
        if path.is_file():
            raw_token, raw_base, raw_mirror = _parse_env_raw(
                path.read_text(encoding="utf-8", errors="replace")
            )
            token = token or (raw_token or "")
            base = base or (raw_base or "")
            mirror = mirror or raw_mirror

    if not token:
        raise RuntimeError(
            "No API token found. Set CHAT_GPT_API_KEY or provide a .env-raw at "
            f"{config.ENV_RAW_PATH}."
        )
    if not base:
        raise RuntimeError(
            "No base URL found. Set OPENAI_COMPAT_BASE_URL or provide a .env-raw with "
            "a Primary Endpoint URL."
        )

    # Tokens sometimes come prefixed with 'Bearer '.
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return PlutoCreds(token=token, base_url=base, mirror_url=mirror)
