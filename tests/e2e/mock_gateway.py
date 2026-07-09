"""Minimal OpenAI-compatible mock gateway for the E2E suite (stdlib only, no pip deps).

Stands in for the real Pluto gateway so the "full pipeline" Playwright spec exercises the
real Judge Node HTTP code path (real request, real parsing/validation/checkpointing) at
zero cost. Mirrors ``vejudge/lm_engine/openai_compat.py``'s exact request/response shape:
POST ``/chat/completions`` -> ``{choices: [{message: {content}}], usage: {...}}``.
"""

from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

# A small, deliberate delay on every response — real gateways aren't instant either, and
# it gives specs that need to observe a run "still in flight" (e.g. clicking Stop mid-run)
# a reliable window, at a cost (a few hundred ms per test) too small to matter for the
# rest of the suite.
RESPONSE_DELAY_S = 0.2

# A single combined response body whose keys are the union of every M1-M6 schema, so it
# validates cleanly (per vejudge/core/judge/validate.py's required-field/score-range/
# non-empty-rationale checks) no matter which metric a test graph selects.
MOCK_JUDGE_CONTENT = {
    "score_1_to_5": 3,
    "fully_complete": True,
    "fully_aligned": True,
    "missing_aspects": [],
    "missing_visual_aspects": [],
    "issues": [],
    "failure": False,
    "severity": "none",
    "evidence": [],
    "reasoning_lines": [
        "Mock gateway response for E2E testing.",
        "This is not a real judge call.",
        "Score is fixed at 3/5 for determinism.",
    ],
    "voiceover_visual_match": {"score_1_to_5": 3, "issues": [], "reasoning": "mock"},
    "voiceover_continuity": {"score_1_to_5": 3, "issues": [], "reasoning": "mock"},
    "visual_continuity": {"score_1_to_5": 3, "issues": [], "reasoning": "mock"},
    "overall_av_sync_score": 3,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass  # quiet — the E2E orchestrator captures stdout/stderr itself

    def do_POST(self) -> None:
        if self.path != "/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)  # request body is ignored — always returns the same content
        time.sleep(RESPONSE_DELAY_S)

        body = json.dumps({
            "choices": [{"message": {"content": json.dumps(MOCK_JUDGE_CONTENT)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv: Optional[list[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    port = int(args[0]) if args else 0
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(server.server_port, flush=True)  # the orchestrator reads this line to learn the port
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
