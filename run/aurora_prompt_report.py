#!/usr/bin/env python3
"""Generate a standalone HTML browser for an AURORA prompt-repair run."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from vejudge.experiments.prompt_repair_report import write_html_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="Compatible experiment run directory")
    parser.add_argument("--output", type=Path, help="Output HTML path (default: RUN_DIR/report.html)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    output = write_html_report(args.run_dir, args.output)
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
