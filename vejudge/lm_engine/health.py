"""Endpoint health checking + working-endpoint selection.

The gateway has a primary and a mirror endpoint. If the primary is down, trying it first
on every call wastes retries/backoff before failing over. This module probes each endpoint
with one tiny request and reorders so a *working* endpoint is tried first (via
``PlutoCreds.preferred``); failover in ``openai_compat.chat_completion`` remains the safety net.

    python -m vejudge.lm_engine.health --live        # report endpoint health
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Optional

import requests

from .. import config
from .creds import PlutoCreds, load_creds
from .gate import LiveCallNotAllowed, require_live


def check_endpoint(
    base_url: str, token: str, *, model: Optional[str] = None, timeout: int = 20
) -> dict[str, Any]:
    """Probe one endpoint with a minimal chat completion. Returns a status dict."""
    model = model or config.DEFAULT_TEXT_MODEL
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": f"Bearer {token}",
    }
    t0 = time.time()
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        ok = r.status_code < 400
        return {
            "url": base_url.rstrip("/"),
            "ok": ok,
            "status": r.status_code,
            "latency": round(time.time() - t0, 2),
            "error": None if ok else r.text[:200],
        }
    except requests.RequestException as e:
        return {
            "url": base_url.rstrip("/"),
            "ok": False,
            "status": None,
            "latency": round(time.time() - t0, 2),
            "error": f"{type(e).__name__}: {e}",
        }


def healthy_order(
    creds: PlutoCreds, *, model: Optional[str] = None, timeout: int = 20
) -> tuple[list[str], list[dict[str, Any]]]:
    """Probe all (default-order) endpoints; return (endpoints healthy-first, results).

    Healthy endpoints keep their relative order; unhealthy ones are kept as last resort
    (so a wholly-down gateway still gets attempted rather than yielding an empty list).
    """
    results = [
        check_endpoint(ep, creds.token, model=model, timeout=timeout)
        for ep in creds.default_endpoints
    ]
    healthy = [r["url"] for r in results if r["ok"]]
    unhealthy = [r["url"] for r in results if not r["ok"]]
    return (healthy + unhealthy, results)


def reorder_creds_by_health(
    creds: PlutoCreds,
    *,
    model: Optional[str] = None,
    timeout: int = 20,
    logger: Any = None,
) -> list[dict[str, Any]]:
    """Set ``creds.preferred`` to a working-endpoint-first order. Returns probe results."""
    ordered, results = healthy_order(creds, model=model, timeout=timeout)
    creds.preferred = ordered
    if logger is not None:
        for r in results:
            logger.info(
                "endpoint %s: %s (status=%s, %.2fs)%s",
                r["url"], "OK" if r["ok"] else "DOWN", r["status"], r["latency"],
                "" if r["ok"] else f" — {r['error']}",
            )
        healthy = [r for r in results if r["ok"]]
        if not healthy:
            logger.warning("No healthy endpoint found; will try all in default order.")
        elif results and not results[0]["ok"]:
            logger.warning("Primary endpoint down; switched to %s", ordered[0])
    return results


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Check VEJudge gateway endpoint health")
    p.add_argument("--model", default=None, help="model to ping (default: text default)")
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--live", action="store_true", help="authorize the real probe calls")
    args = p.parse_args(argv)

    try:
        require_live(args.live, context="The health check")
    except LiveCallNotAllowed as e:
        print(f"Refused: {e}", file=sys.stderr)
        return 2

    creds = load_creds()
    _, results = healthy_order(creds, model=args.model, timeout=args.timeout)
    print(f"{'endpoint':<60} {'status':>7} {'latency':>8}  health")
    for r in results:
        host = r["url"].replace("https://", "")
        print(f"{host:<60} {str(r['status']):>7} {str(r['latency'])+'s':>8}  "
              f"{'OK' if r['ok'] else 'DOWN'}")
        if not r["ok"]:
            print(f"    {r['error']}")
    healthy = [r for r in results if r["ok"]]
    if not healthy:
        print("\nNo endpoint is responding.", file=sys.stderr)
        return 1
    print(f"\nWorking endpoint(s), in preferred order: "
          f"{', '.join(r['url'] for r in results if r['ok'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
