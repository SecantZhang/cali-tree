"""Provider-scoped credentials. Official APIs are the default.

Manual settings override environment variables for the same provider only. Old
unscoped credentials and .env-raw are read only with VEJUDGE_PROVIDER=legacy (or
an explicitly supplied env_raw_path). They can never override a direct API key.
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from dotenv import dotenv_values
from .. import config

DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}
KEY_VARS = {"openai": ("OPENAI_API_KEY",), "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
_TOKEN_RE = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b")
_URL_RE = re.compile(r"https?://[^\s\"']+")
CredsSource = str
_manual_lock = threading.RLock()


@dataclass
class ProviderCreds:
    token: str = field(repr=False)
    base_url: str
    mirror_url: Optional[str] = None
    preferred: Optional[list[str]] = None
    provider: str = "compatible"

    @property
    def endpoints(self) -> list[str]:
        return [u.rstrip("/") for u in self.preferred if u] if self.preferred else self.default_endpoints

    @property
    def default_endpoints(self) -> list[str]:
        urls = [self.base_url]
        if self.mirror_url and self.mirror_url != self.base_url:
            urls.append(self.mirror_url)
        return [u.rstrip("/") for u in urls if u]


# Kept for older integrations constructing credentials explicitly.
PlutoCreds = ProviderCreds


def _env_values() -> dict:
    # Read without mutating process globals; shell variables always win.
    return {**dotenv_values(config.PROJECT_ROOT / ".env"), **os.environ}


def resolve_provider(*, provider=None, engine=None, model=None, env_raw_path=None) -> str:
    selected = provider or ("legacy" if env_raw_path else _env_values().get("VEJUDGE_PROVIDER"))
    if not selected:
        if engine:
            selected = {"gpt": "openai", "gemini": "gemini"}.get(engine.lower())
            if not selected:
                raise RuntimeError(f"Direct provider support is available for gpt and gemini, not {engine!r}.")
        elif model:
            name = model.lower().removeprefix("models/")
            if name.startswith("gemini-"):
                selected = "gemini"
            elif name.startswith(("gpt-", "o1", "o3", "o4", "text-embedding-", "chatgpt-")):
                selected = "openai"
            else:
                raise RuntimeError(f"Cannot infer provider for model {model!r}; set VEJUDGE_PROVIDER.")
        else:
            selected = "openai"
    selected = {"gpt": "openai", "google": "gemini"}.get(str(selected).lower(), str(selected).lower())
    if selected not in (*DEFAULT_URLS, "legacy"):
        raise ValueError("provider must be openai, gemini, or legacy")
    return selected


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


def _read_manual(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        if "providers" in data:
            return data["providers"] if isinstance(data["providers"], dict) else {}
        # The old global override is legacy-only; never attach it to a provider.
        return {"legacy": data}
    except (ValueError, OSError):
        return {}


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base_url must be an HTTP(S) API base URL without credentials, query, or fragment")


def save_manual_creds(token: str, base_url: str = "", mirror_url: Optional[str] = None,
                      *, credentials_file: Optional[Path] = None, provider: str = "openai") -> ProviderCreds:
    provider = resolve_provider(provider=provider)
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    base_url = base_url.strip() or DEFAULT_URLS.get(provider, "")
    if not token:
        raise ValueError("token must not be empty")
    if not base_url:
        raise ValueError("base_url must not be empty")
    _validate_url(base_url)
    mirror_url = (mirror_url or "").strip() or None
    if mirror_url:
        if provider != "legacy":
            raise ValueError("Mirror endpoints are supported only in explicit legacy mode")
        _validate_url(mirror_url)
    path = _manual_creds_path(credentials_file)
    with _manual_lock:
        data = _read_manual(path)
        data[provider] = {"token": token, "base_url": base_url, "mirror_url": mirror_url}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"providers": data}, handle)
        temporary.chmod(0o600)
        temporary.replace(path)
    return ProviderCreds(token, base_url, mirror_url, provider=provider)


def clear_manual_creds(*, credentials_file: Optional[Path] = None, provider: str = "openai") -> None:
    provider = resolve_provider(provider=provider)
    path = _manual_creds_path(credentials_file)
    with _manual_lock:
        data = _read_manual(path)
        data.pop(provider, None)
        if not data:
            path.unlink(missing_ok=True)
        else:
            temporary = path.with_suffix(".tmp")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"providers": data}, handle)
            temporary.chmod(0o600)
            temporary.replace(path)


def load_creds_with_source(env_raw_path: Optional[Path] = None, *, credentials_file: Optional[Path] = None,
                           provider=None, engine=None, model=None) -> tuple[ProviderCreds, CredsSource]:
    provider = resolve_provider(provider=provider, engine=engine, model=model, env_raw_path=env_raw_path)
    manual = _read_manual(_manual_creds_path(credentials_file)).get(provider) or {}
    if isinstance(manual, dict) and manual.get("token") and manual.get("base_url"):
        return ProviderCreds(manual["token"], manual["base_url"], manual.get("mirror_url"), provider=provider), "manual"
    env = _env_values()
    if provider != "legacy":
        token = next((str(env.get(k) or "").strip() for k in KEY_VARS[provider] if str(env.get(k) or "").strip()), "")
        base = str(env.get(provider.upper() + "_BASE_URL") or DEFAULT_URLS[provider]).strip()
        if not token:
            raise RuntimeError(f"No {provider} API key configured. Set {' or '.join(KEY_VARS[provider])} in the environment/.env, or save it in Settings → API Credentials.")
        _validate_url(base)
        return ProviderCreds(token.removeprefix("Bearer ").strip(), base, provider=provider), "env"

    token = str(env.get("CHAT_GPT_API_KEY") or env.get("AZURE_OPENAI_API_KEY") or "").strip()
    base = str(env.get("OPENAI_COMPAT_BASE_URL") or env.get("LLM_PROXY_BASE_URL") or "").strip()
    mirror = str(env.get("LLM_PROXY_MIRROR_URL") or "").strip() or None
    source = "env"
    if not (token and base):
        path = Path(env_raw_path) if env_raw_path else config.ENV_RAW_PATH
        if path.is_file():
            raw_token, raw_base, raw_mirror = _parse_env_raw(path.read_text(encoding="utf-8"))
            token, base, mirror = token or raw_token, base or raw_base, mirror or raw_mirror
            source = "file"
    if not token or not base:
        raise RuntimeError("Legacy mode needs CHAT_GPT_API_KEY and OPENAI_COMPAT_BASE_URL, or an explicit .env-raw file")
    return ProviderCreds(token.removeprefix("Bearer ").strip(), base, mirror, provider="legacy"), source


def load_creds(env_raw_path: Optional[Path] = None, *, provider=None, engine=None, model=None) -> ProviderCreds:
    return load_creds_with_source(env_raw_path, provider=provider, engine=engine, model=model)[0]
