#!/usr/bin/env python3
"""Smoke checks for deployed Meal Planner backend."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def fetch_json(url: str) -> tuple[int, dict]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"detail": body}
        return exc.code, payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Meal Planner backend endpoints")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL without trailing slash",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    health_status, health_body = fetch_json(f"{base_url}/api/health")
    if health_status != 200 or health_body.get("status") != "ok":
        print(f"FAIL /api/health status={health_status} body={health_body}")
        return 1

    ready_status, ready_body = fetch_json(f"{base_url}/api/ready")
    if ready_status not in {200, 503}:
        print(f"FAIL /api/ready unexpected status={ready_status}")
        return 1

    print("OK /api/health")
    print(f"OK /api/ready status={ready_status} payload={ready_body}")
    return 0 if ready_body.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
