"""Load Pluto gateway credentials.

Resolution order (highest precedence first):
1. **Manual override** — entered via the interface's Settings modal, persisted to
   ``config.CREDENTIALS_FILE`` (a local gitignored JSON file) so it survives backend
   restarts without needing shell/env-var access. Explicit UI input beats ambient config.
2. Standard environment variables (``CHAT_GPT_API_KEY``/``OPENAI_COMPAT_BASE_URL``, etc.),
   so CI / other machines can inject creds the usual way.
3. The ``.env-raw`` blurb shipped in the repo root (a human-readable file, NOT
   key=value), parsed with regexes.

The token is never logged, and never echoed back by any API response.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import config

_TOKEN_RE = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b")
_URL_RE = re.compile(r"https?://[^\s\"']+")

CredsSource = str  # "manual" | "env" | "file"

# Keyed by resolved credentials-file path so tests can pass a distinct tmp_path without
# colliding with (or being polluted by) whatever's cached for the real default path.
_manual_cache: dict[str, Optional["PlutoCreds"]] = {}


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


def _manual_creds_path(credentials_file: Optional[Path] = None) -> Path:
    return Path(credentials_file) if credentials_file else config.CREDENTIALS_FILE


def _load_manual_from_disk(path: Path) -> Optional[PlutoCreds]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    token = str(data.get("token") or "").strip()
    base_url = str(data.get("base_url") or "").strip()
    mirror_url = str(data.get("mirror_url") or "").strip() or None
    if not token or not base_url:
        return None
    return PlutoCreds(token=token, base_url=base_url, mirror_url=mirror_url)


def _get_manual_creds(credentials_file: Optional[Path] = None) -> Optional[PlutoCreds]:
    path = _manual_creds_path(credentials_file)
    key = str(path)
    if key not in _manual_cache:
        _manual_cache[key] = _load_manual_from_disk(path)
    return _manual_cache[key]


def save_manual_creds(
    token: str,
    base_url: str,
    mirror_url: Optional[str] = None,
    *,
    credentials_file: Optional[Path] = None,
) -> PlutoCreds:
    """Persist a manual credentials override, effective immediately (no restart needed)."""
    token = token.strip()
    base_url = base_url.strip()
    mirror_url = (mirror_url or "").strip() or None
    if not token:
        raise ValueError("token must not be empty")
    if not base_url:
        raise ValueError("base_url must not be empty")

    path = _manual_creds_path(credentials_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"token": token, "base_url": base_url, "mirror_url": mirror_url}),
        encoding="utf-8",
    )
    creds = PlutoCreds(token=token, base_url=base_url, mirror_url=mirror_url)
    _manual_cache[str(path)] = creds
    return creds


def clear_manual_creds(*, credentials_file: Optional[Path] = None) -> None:
    """Remove the manual override, reverting to env vars / .env-raw."""
    path = _manual_creds_path(credentials_file)
    path.unlink(missing_ok=True)
    _manual_cache[str(path)] = None


def load_creds_with_source(
    env_raw_path: Optional[Path] = None, *, credentials_file: Optional[Path] = None
) -> tuple[PlutoCreds, CredsSource]:
    """Return credentials plus which source they came from: manual > env > file."""
    manual = _get_manual_creds(credentials_file)
    if manual is not None:
        return manual, "manual"

    token, base, mirror = _from_env()
    source: Optional[CredsSource] = "env" if (token and base) else None

    if not (token and base):
        path = Path(env_raw_path) if env_raw_path else config.ENV_RAW_PATH
        if path.is_file():
            raw_token, raw_base, raw_mirror = _parse_env_raw(
                path.read_text(encoding="utf-8", errors="replace")
            )
            if not token and raw_token:
                token = raw_token
                source = "file"
            if not base and raw_base:
                base = raw_base
                source = source or "file"
            mirror = mirror or raw_mirror

    if not token:
        raise RuntimeError(
            "No API token found. Set CHAT_GPT_API_KEY, provide a .env-raw at "
            f"{config.ENV_RAW_PATH}, or enter one in the interface's Settings modal."
        )
    if not base:
        raise RuntimeError(
            "No base URL found. Set OPENAI_COMPAT_BASE_URL, provide a .env-raw with "
            "a Primary Endpoint URL, or enter one in the interface's Settings modal."
        )

    # Tokens sometimes come prefixed with 'Bearer '.
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return PlutoCreds(token=token, base_url=base, mirror_url=mirror), (source or "env")


def load_creds(env_raw_path: Optional[Path] = None) -> PlutoCreds:
    """Return credentials, preferring a manual override, then env vars, then .env-raw."""
    creds, _source = load_creds_with_source(env_raw_path)
    return creds
