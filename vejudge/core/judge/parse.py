"""Turn judge model text into a dict (strip ``` fences, json.loads).

Copied from the original evaluation framework so the package is self-contained.
"""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)
