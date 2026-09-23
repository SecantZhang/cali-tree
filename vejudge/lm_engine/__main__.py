"""``vejudge-smoke`` — one tiny call to validate the gateway, token, failover, logging.

Examples:
    vejudge-smoke --text "reply with the single word OK"
    vejudge-smoke --engine gemini --video /path/to/clip.mp4 --text "Describe this in one line"
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import get_engine, require_live
from .gate import LiveCallNotAllowed
from ..logging.llm_history import LLMHistoryWriter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VEJudge lm_engine smoke test")
    parser.add_argument("--engine", default="gpt", help="gpt | gemini | qwen")
    parser.add_argument("--text", default="Reply with the single word OK.")
    parser.add_argument("--video", default=None, help="optional video path to attach")
    parser.add_argument("--model", default=None, help="override model id")
    parser.add_argument(
        "--live",
        action="store_true",
        help="authorize the real (billable) gateway call",
    )
    args = parser.parse_args(argv)

    try:
        require_live(args.live, context="The smoke test")
    except LiveCallNotAllowed as e:
        print(f"Refused: {e}", file=sys.stderr)
        return 2

    history_path = Path(tempfile.gettempdir()) / "vejudge-smoke-llm-histories.log"
    history = LLMHistoryWriter(history_path)

    engine = get_engine(args.engine, history=history, model=args.model)
    media = [{"type": "video", "path": args.video}] if args.video else None

    print(f"engine={engine.name} model={engine.model} endpoints={engine.creds.endpoints}")
    try:
        out = engine.generate(args.text, media_inputs=media)
    except Exception as e:  # noqa: BLE001
        print(f"FAILED: {e}", file=sys.stderr)
        print(f"(history written to {history_path})", file=sys.stderr)
        return 1

    print("--- response ---")
    print(out.get("content"))
    print("--- tokens ---")
    print(
        f"prompt={out['promptTokens']} completion={out['completionTokens']} "
        f"total={out['totalTokens']}"
    )
    print(f"(history appended to {history_path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
