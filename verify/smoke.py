"""API smoke test for the closed leveling network.

Runs against a live API (default http://api:8000) using only the standard
library:

  * posts a network that contains an independent loop with real misclosure,
  * checks every correction obeys its limit and the back-delta identity,
  * independently sums back-deltas around the loop and requires closure 0,
  * verifies minimax/total objectives and lexicographic tie-break,
  * posts the same network with all limits zero and expects feasible=false,
    empty elevations/corrections and an "insufficient allowance" message.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("API_BASE", "http://api:8000").rstrip("/")
WEB_BASE = os.environ.get("WEB_BASE", "").rstrip("/")


def post(path: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def get(url: str) -> int:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status


def network(*, tight: bool) -> dict:
    lim = 0 if tight else 3
    return {
        "stations": [
            {"name": "A", "benchmark": True},
            {"name": "B", "benchmark": False},
            {"name": "C", "benchmark": False},
            {"name": "D", "benchmark": False},
            {"name": "E", "benchmark": False},
        ],
        "benchmark_height": 1000,
        "observations": [
            {"start": "A", "end": "B", "delta": 125, "limit": lim},
            {"start": "B", "end": "A", "delta": -124, "limit": lim},
            {"start": "B", "end": "C", "delta": -230, "limit": lim},
            {"start": "C", "end": "B", "delta": 231, "limit": lim},
            {"start": "C", "end": "D", "delta": 87, "limit": lim},
            {"start": "D", "end": "E", "delta": -56, "limit": lim},
            {"start": "E", "end": "A", "delta": 75, "limit": lim},
        ],
    }


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)
    print(f"  ok: {msg}")


def main() -> int:
    failures = 0

    print("health")
    check(get(f"{API_BASE}/health") == 200, "GET /health -> 200")
    if WEB_BASE:
        check(get(f"{WEB_BASE}/") == 200, "web root -> 200")

    print("feasible closure network")
    try:
        status, body = post("/api/adjust", network(tight=False))
        check(status == 200, f"POST /api/adjust -> {status}")
        check(body["feasible"] is True, "response is feasible")

        H = {e["name"]: e["elevation"] for e in body["elevations"]}
        check(H["A"] == 1000, "benchmark A pinned to 1000")
        check(list(H.keys()) == ["A", "B", "C", "D", "E"],
              "elevations returned in station entry order")

        for i, c in enumerate(body["corrections"]):
            check(c["within_limit"] is True,
                  f"obs {i + 1} correction within limit ({c['correction']})")
            check(c["back_delta"] == c["delta"] + c["correction"],
                  f"obs {i + 1} back_delta = delta + correction")
            check(c["back_delta"] == H[c["end"]] - H[c["start"]],
                  f"obs {i + 1} back_delta matches returned elevations")

        # Independent loop closure: A->B->C->D->E->A.
        loop = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "A")]
        closure = sum(H[v] - H[u] for u, v in loop)
        check(closure == 0, f"independent loop A-B-C-D-E-A closes (got {closure})")

        # Hand-computed optimum for this network: the two run-pairs each
        # carry a unit misclosure, so minimax = 1, total abs = 2, and the
        # lexicographic tie-break puts corrections on the earliest edges.
        check(body["max_abs_correction"] == 1,
              f"minimax objective is 1 (got {body['max_abs_correction']})")
        check(body["total_abs_correction"] == 2,
              f"total abs objective is 2 (got {body['total_abs_correction']})")
        check([H[n] for n in "ABCDE"] == [1000, 1124, 894, 981, 925],
              f"lexicographic elevations (got {[H[n] for n in 'ABCDE']})")
        check([c["correction"] for c in body["corrections"]] == [-1, 0, 0, -1, 0, 0, 0],
              "corrections on earliest edges under tie-break")
    except AssertionError as e:
        failures += 1
        print(f"FAIL: {e}")

    print("infeasible network (all limits zero)")
    try:
        status, body = post("/api/adjust", network(tight=True))
        check(status == 200, f"POST /api/adjust -> {status} (feasibility in body)")
        check(body["feasible"] is False, "feasible=false when allowances insufficient")
        check(body["elevations"] == [], "old elevations cleared (empty list)")
        check(body["corrections"] == [], "old corrections cleared (empty list)")
        check("允许改正量" in body["message"], "message states allowances are insufficient")
    except AssertionError as e:
        failures += 1
        print(f"FAIL: {e}")

    if failures:
        print(f"SMOKE FAILED: {failures} check group(s) failed")
        return 1
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
