"""Opt-in HTTP load probe for care-chat v2; never runs as part of pytest.

Example (PowerShell, use a disposable conversation on a test deployment):
  $env:CARE_CHAT_LOAD_TOKEN = '<test user's bearer token>'
  .\.venv\Scripts\python.exe scripts/load_care_chat.py --base-url http://localhost:8000 `
    --conversation-id <uuid> --mode latest --requests 500 --concurrency 20 --rps 50

The token is read from the named environment variable, never a command-line
argument or log. ``send`` writes persistent messages and additionally requires
--allow-write. The caller must clean up their test conversation afterwards.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
from collections import Counter
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base-url", required=True, help="Explicit test server origin, e.g. http://localhost:8000"
    )
    parser.add_argument(
        "--conversation-id", required=True, type=UUID, help="Existing disposable test conversation"
    )
    parser.add_argument(
        "--token-env",
        default="CARE_CHAT_LOAD_TOKEN",
        help="Environment variable containing bearer token",
    )
    parser.add_argument("--mode", choices=("latest", "poll", "send"), default="latest")
    parser.add_argument("--requests", type=positive_int, default=100)
    parser.add_argument("--concurrency", type=positive_int, default=10)
    parser.add_argument("--rps", type=positive_float, help="Optional aggregate request-rate cap")
    parser.add_argument("--timeout", type=positive_float, default=10)
    parser.add_argument("--limit", type=positive_int, default=50)
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Explicitly allow send mode to create test messages",
    )
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        parser.error(
            "--base-url must be an HTTP(S) origin without credentials, path, query, or fragment"
        )
    if args.mode == "send" and not args.allow_write:
        parser.error("send mode requires --allow-write and a disposable test conversation")
    if args.limit > 100:
        parser.error("--limit cannot exceed 100")
    if not os.getenv(args.token_env, "").strip():
        parser.error("the environment variable selected by --token-env must contain a bearer token")
    return args


def percentile(samples: list[float], percent: int) -> float:
    ordered = sorted(samples)
    index = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
    return round(ordered[index] * 1000, 2) if ordered else 0


async def probe(args: argparse.Namespace) -> tuple[dict, int]:
    token = os.environ[args.token_env].strip()
    path = f"/api/v2/conversations/{args.conversation_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(args.timeout)
    limits = httpx.Limits(
        max_connections=args.concurrency, max_keepalive_connections=args.concurrency
    )
    # Do not follow redirects to avoid forwarding credentials to another origin.
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        headers=headers,
        timeout=timeout,
        limits=limits,
        follow_redirects=False,
    ) as client:
        try:
            preflight = await client.get(path, params={"limit": args.limit})
            if preflight.status_code != 200:
                return {"error": "preflight_failed", "status": preflight.status_code}, 2
            initial_cursor = preflight.json()["sync_cursor"]
            if not initial_cursor:
                return {"error": "preflight_missing_sync_cursor"}, 2
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return {"error": "preflight_failed", "error_type": type(exc).__name__}, 2

        durations: list[float] = []
        statuses: Counter[str] = Counter()
        errors: Counter[str] = Counter()
        next_index = 0
        successful = 0
        run_id = uuid4().hex[:12]
        started = time.perf_counter()

        async def worker() -> None:
            nonlocal next_index, successful
            cursor = initial_cursor
            while next_index < args.requests:
                index = next_index
                next_index += 1
                if args.rps:
                    delay = started + index / args.rps - time.perf_counter()
                    if delay > 0:
                        await asyncio.sleep(delay)
                request_started = time.perf_counter()
                try:
                    if args.mode == "send":
                        response = await client.post(
                            path,
                            json={
                                "client_message_id": str(uuid4()),
                                "body": f"Care-chat load test {run_id} message {index}",
                            },
                        )
                    else:
                        params = {"limit": args.limit}
                        if args.mode == "poll":
                            params["after"] = cursor
                        response = await client.get(path, params=params)
                    statuses[str(response.status_code)] += 1
                    expected = (200, 201) if args.mode == "send" else (200,)
                    if response.status_code not in expected:
                        errors["http_error"] += 1
                        continue
                    data = response.json()
                    if args.mode == "send":
                        if not isinstance(data.get("seq"), int) or not data.get("id"):
                            errors["invalid_contract"] += 1
                            continue
                    elif not isinstance(data.get("items"), list) or not data.get("sync_cursor"):
                        errors["invalid_contract"] += 1
                        continue
                    elif args.mode == "poll":
                        # Advance only from an actual incremental read, never a send ACK.
                        cursor = data["sync_cursor"]
                    successful += 1
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    # Exception strings/response bodies can contain URLs or private data.
                    errors[type(exc).__name__] += 1
                finally:
                    durations.append(time.perf_counter() - request_started)

        await asyncio.gather(*[worker() for _ in range(min(args.concurrency, args.requests))])
        elapsed = time.perf_counter() - started
        error_count = args.requests - successful
        result = {
            "mode": args.mode,
            "requests": args.requests,
            "concurrency": args.concurrency,
            "configured_rps_cap": args.rps,
            "duration_seconds": round(elapsed, 3),
            "achieved_rps": round(args.requests / elapsed, 2),
            "successful_rps": round(successful / elapsed, 2),
            "latency_ms": {
                "p50": percentile(durations, 50),
                "p95": percentile(durations, 95),
                "p99": percentile(durations, 99),
                "max": round(max(durations, default=0) * 1000, 2),
            },
            "successful": successful,
            "errors": error_count,
            "error_rate": round(error_count / args.requests, 6),
            "status_counts": dict(statuses),
            "error_types": dict(errors),
            "writes_persisted": args.mode == "send",
        }
        return result, 2 if error_count else 0


def main() -> int:
    args = parse_args()
    try:
        result, exit_code = asyncio.run(probe(args))
    except KeyboardInterrupt:
        print(json.dumps({"error": "interrupted"}))
        return 130
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
