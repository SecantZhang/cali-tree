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
HARD_STOP_DELAY_S = 3.0

# A single combined response body whose keys are the union of every M1-M6 schema PLUS the
# D1 (judge-agent debate turn)/D2 (human-proxy debate turn) schemas, so it validates cleanly
# (per vejudge/core/judge/validate.py's required-field/score-range/non-empty-rationale
# checks) no matter which metric or debate role a test graph exercises.
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
    # D1 (judge-agent debate turn) / D2 (human-proxy debate turn) fields.
    "revised": False,
    "agrees_with_judge": True,
    # A real taxonomy key (see d2_human_proxy_debate.FAILURE_MODE_TAXONOMY) so the debate
    # yields a non-empty failure_mode_summary — the de-leaked optimized_prompt is built
    # purely from flagged tendencies, so without this it would be "" and the calibrated
    # judge would get no addendum for the sandwich E2E to assert on.
    "cited_failure_modes": ["audio_neglect"],
    "semantic_summary": {
        "principle": "Evaluate audiovisual coherence across the complete edit.",
        "applies_when": "Visual inserts and spoken content must reinforce one another.",
        "evidence_to_check": ["Check whether each visual cut matches the concurrent narration."],
        "scoring_guidance": "Weigh concrete audiovisual alignment rather than surface polish.",
    },
}

MOCK_SEMANTIC_SUMMARY = {
    "principle": "Evaluate audiovisual coherence across the complete edit.",
    "applies_when": "Visual inserts and spoken content must reinforce one another.",
    "evidence_to_check": ["Check whether each visual cut matches the concurrent narration."],
    "scoring_guidance": "Weigh concrete audiovisual alignment rather than surface polish.",
    "counter_consideration": "",
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
        request = json.loads(self.rfile.read(length) or b"{}")
        messages = request.get("messages") or []
        system = str((messages[0] if messages else {}).get("content") or "")
        content = MOCK_SEMANTIC_SUMMARY if "distill an adversarial" in system else MOCK_JUDGE_CONTENT
        # The stop/resume spec selects this otherwise-unusual temperature to hold a real
        # HTTP request open long enough to prove Stop kills the run worker rather than
        # waiting for the response. Other E2E calls retain the fast default.
        delay = HARD_STOP_DELAY_S if request.get("temperature") == 9.9 else RESPONSE_DELAY_S
        time.sleep(delay)

        body = json.dumps({
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Expected when hard Stop kills the client process during the deliberate delay.
            pass


def main(argv: Optional[list[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    port = int(args[0]) if args else 0
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(server.server_port, flush=True)  # the orchestrator reads this line to learn the port
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
