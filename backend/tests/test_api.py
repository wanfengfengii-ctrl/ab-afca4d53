"""API-level tests using FastAPI's in-process test client."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


def station(name: str, benchmark: bool = False) -> dict:
    return {"name": name, "benchmark": benchmark}


def obs(start: str, end: str, delta: int, limit: int = 5) -> dict:
    return {"start": start, "end": end, "delta": delta, "limit": limit}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def _loop_payload() -> dict:
    # 5 stations, 7 observations (minimum counts).  Triangle A-B-C carries a
    # unit loop misclosure; D and E are pinned exactly off A through direct
    # and reverse (往返) observations with zero allowed correction.
    return {
        "stations": [
            station("A", True),
            station("B"),
            station("C"),
            station("D"),
            station("E"),
        ],
        "benchmark_height": 1000,
        "observations": [
            obs("A", "B", 0),
            obs("B", "C", 0),
            obs("C", "A", 1),
            obs("A", "D", 10, limit=0),
            obs("D", "E", -3, limit=0),
            obs("A", "E", 7, limit=0),
            obs("D", "A", -10, limit=0),
        ],
    }


def test_adjust_feasible_returns_elevations_and_back_deltas(client: TestClient) -> None:
    r = client.post("/api/adjust", json=_loop_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["feasible"] is True
    by_name = {e["name"]: e["elevation"] for e in body["elevations"]}
    assert by_name["A"] == 1000
    assert by_name["D"] == 1010
    assert by_name["E"] == 1007

    for c in body["corrections"]:
        assert c["within_limit"] is True
        assert abs(c["correction"]) <= 5
        # back-computed identity: back_delta == measured + correction
        assert c["back_delta"] == c["delta"] + c["correction"]
        assert c["back_delta"] == by_name[c["end"]] - by_name[c["start"]]

    assert body["max_abs_correction"] == 1
    assert body["total_abs_correction"] == 1
    # the single unit correction lands on the earliest edge (A -> B)
    first = body["corrections"][0]
    assert (first["start"], first["end"], first["correction"]) == ("A", "B", -1)


def test_adjust_infeasible_clears_results(client: TestClient) -> None:
    payload = _loop_payload()
    # Tighten every limit to zero: the unit loop misclosure cannot be fixed.
    for o in payload["observations"]:
        o["limit"] = 0
    r = client.post("/api/adjust", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["feasible"] is False
    assert body["elevations"] == []
    assert body["corrections"] == []
    assert body["max_abs_correction"] == 0
    assert "允许改正量" in body["message"]


def test_duplicate_station_names_rejected(client: TestClient) -> None:
    payload = _loop_payload()
    payload["stations"][1]["name"] = "A"
    r = client.post("/api/adjust", json=payload)
    assert r.status_code == 422
    assert "唯一" in r.text


def test_unknown_observation_endpoint_rejected(client: TestClient) -> None:
    payload = _loop_payload()
    payload["observations"][0]["end"] = "Z"
    r = client.post("/api/adjust", json=payload)
    assert r.status_code == 422
    assert "测站列表" in r.text


def test_disconnected_station_rejected(client: TestClient) -> None:
    payload = _loop_payload()
    # Remove the two observations touching E, leaving it isolated, and add a
    # redundant A-D observation so the count (7) still passes.
    payload["observations"] = [
        o for o in payload["observations"] if o["start"] != "E" and o["end"] != "E"
    ]
    payload["observations"].append(obs("A", "D", 10, limit=0))
    payload["observations"].append(obs("D", "A", -10, limit=0))
    assert len(payload["observations"]) == 7
    r = client.post("/api/adjust", json=payload)
    assert r.status_code == 422
    assert "E" in r.json()["detail"]
    assert "观测路径" in r.json()["detail"]


def test_counts_out_of_range_rejected(client: TestClient) -> None:
    payload = _loop_payload()
    payload["stations"] = payload["stations"][:4]  # 4 stations (< 5)
    r = client.post("/api/adjust", json=payload)
    assert r.status_code == 422

    payload = _loop_payload()
    payload["observations"] = payload["observations"][:6]  # 6 obs (< 7)
    r = client.post("/api/adjust", json=payload)
    assert r.status_code == 422


def test_benchmark_required(client: TestClient) -> None:
    payload = _loop_payload()
    payload["stations"][0]["benchmark"] = False
    r = client.post("/api/adjust", json=payload)
    assert r.status_code == 422
    assert "基准" in r.text
