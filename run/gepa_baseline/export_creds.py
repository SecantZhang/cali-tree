#!/usr/bin/env python3
"""Export gateway credentials for the isolated .venv-gepa process to consume.

Runs in the main venv (reuses vejudge.lm_engine.load_creds' full resolution order: manual
override -> env vars -> .env-raw). Writes a SECRET, gitignored, mode-600 local file. Never
logs or prints the token. The isolated GEPA process reads this file and never needs
`vejudge` importable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from vejudge.lm_engine import load_creds

OUTPUT = Path(__file__).resolve().parent / ".creds.json"


def main() -> int:
    creds = load_creds()
    payload = {
        "base_url": creds.base_url,
        "mirror_url": creds.mirror_url,
        "endpoints": creds.endpoints,
        "token": creds.token,
    }
    OUTPUT.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(OUTPUT, 0o600)
    print(f"wrote credentials to {OUTPUT} (mode 600, gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
