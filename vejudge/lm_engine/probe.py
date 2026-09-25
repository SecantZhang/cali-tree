"""Probe the gateway's concurrency / rate-limit behavior with cheap text calls.

Fires increasing batches of tiny concurrent requests, reporting success/429/error
counts and latency per level, plus any rate-limit-ish response headers. Use this to
pick a safe ``--concurrency`` default before running the (expensive) video benchmark.

Real calls -> requires --live. Each call is ~a few tokens, so the whole probe is cents.

    python -m vejudge.lm_engine.probe --live
    python -m vejudge.lm_engine.probe --live --levels 1,2,4,8,16,32
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

import requests

from .creds import load_creds
from .provider_api import chat_request
from .gate import LiveCallNotAllowed, require_live

_RL_HINTS = ("ratelimit", "rate-limit", "retry", "remaining", "reset", "limit")


def _is_rate_header(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in _RL_HINTS)


def _one_call(base: str, token: str, model: str, timeout: int, provider: Optional[str] = None) -> dict[str, Any]:
    url, payload, headers, _ = chat_request(
        base, token, model, [{"role": "user", "content": "Reply with OK"}], 32, 1, provider
    )
    t0 = time.time()
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        latency = time.time() - t0
        return {
            "status": resp.status_code,
            "latency": latency,
            "ok": resp.status_code < 400,
            "rate_limited": resp.status_code == 429,
            "headers": {k: v for k, v in resp.headers.items() if _is_rate_header(k)},
        }
    except requests.RequestException as e:
        return {
            "status": None,
            "latency": time.time() - t0,
            "ok": False,
            "rate_limited": False,
            "error": f"{type(e).__name__}: {e}",
            "headers": {},
        }


def _run_level(url: str, token: str, model: str, n: int, timeout: int, provider: Optional[str] = None) -> dict[str, Any]:
    t0 = time.time()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(_one_call, url, token, model, timeout, provider) for _ in range(n)]
        for f in as_completed(futs):
            results.append(f.result())
    wall = time.time() - t0

    lats = [r["latency"] for r in results if r["ok"]]
    ok = sum(1 for r in results if r["ok"])
    return {
        "concurrency": n,
        "ok": ok,
        "rate_limited": sum(1 for r in results if r.get("rate_limited")),
        "errors": sum(1 for r in results if not r["ok"] and not r.get("rate_limited")),
        "wall_s": round(wall, 2),
        "throughput_rps": round(n / wall, 2) if wall else None,
        "lat_p50": round(statistics.median(lats), 2) if lats else None,
        "lat_max": round(max(lats), 2) if lats else None,
        "sample_error": next((r.get("error") for r in results if r.get("error")), None),
    }


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Probe gateway concurrency / rate limits")
    p.add_argument("--levels", default="1,2,4,8,16", help="comma list of concurrency levels")
    p.add_argument("--model", default=None, help="model id (default: text default)")
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--live", action="store_true", help="authorize the real calls")
    args = p.parse_args(argv)

    try:
        require_live(args.live, context="The probe")
    except LiveCallNotAllowed as e:
        print(f"Refused: {e}", file=sys.stderr)
        return 2

    from .. import config

    model = args.model or config.DEFAULT_TEXT_MODEL
    creds = load_creds(model=model)
    url = creds.endpoints[0]
    levels = [int(x) for x in args.levels.split(",") if x.strip()]

    print(f"Probing {url}\n  model={model}  levels={levels}\n")

    # One warm-up call to surface any rate-limit headers the gateway advertises.
    warm = _one_call(url, creds.token, model, args.timeout, creds.provider)
    print(f"warm-up: status={warm['status']} latency={warm['latency']:.2f}s")
    if warm.get("headers"):
        print("  rate-limit headers:")
        for k, v in warm["headers"].items():
            print(f"    {k}: {v}")
    else:
        print("  (no rate-limit headers advertised)")
    print()

    print(f"{'conc':>5} {'ok':>4} {'429':>4} {'err':>4} {'wall_s':>7} "
          f"{'rps':>6} {'p50':>6} {'max':>6}")
    prev_p50: Optional[float] = None
    for n in levels:
        r = _run_level(url, creds.token, model, n, args.timeout, creds.provider)
        print(f"{r['concurrency']:>5} {r['ok']:>4} {r['rate_limited']:>4} "
              f"{r['errors']:>4} {r['wall_s']:>7} {str(r['throughput_rps']):>6} "
              f"{str(r['lat_p50']):>6} {str(r['lat_max']):>6}")
        if r["sample_error"]:
            print(f"      e.g. {r['sample_error']}")
        # Stop early once the gateway pushes back or latency balloons.
        if r["rate_limited"] or r["errors"] >= max(1, n // 2):
            print("\nStopping: gateway pushed back (429s/errors) at this level.")
            break
        if prev_p50 and r["lat_p50"] and r["lat_p50"] > 4 * prev_p50:
            print("\nStopping: per-call latency degrading sharply (saturation).")
            break
        prev_p50 = r["lat_p50"]

    print("\nPick a benchmark --concurrency at or below the highest clean level above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
