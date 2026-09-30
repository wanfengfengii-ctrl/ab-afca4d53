"""Tests for the lexicographic integer adjustment."""

from __future__ import annotations

from app.optimizer import Observation, adjust


def test_consistent_network_needs_no_correction():
    # Chain BM(0) -> B(10) -> C(20), all observations already consistent.
    obs = [
        Observation(0, 1, 10, 5),
        Observation(1, 2, 10, 5),
        Observation(0, 2, 20, 5),
    ]
    r = adjust(["BM", "B", "C"], obs, 0, 0)
    assert r.feasible
    assert r.elevations == [0, 10, 20]
    assert r.corrections == [0, 0, 0]
    assert r.back_deltas == [10, 10, 20]
    assert r.max_abs_correction == 0
    assert r.total_abs_correction == 0


def test_loop_misclosure_lexicographically_earliest_edge():
    # Triangle with signed correction sum forced to -1.  The -1 can sit on
    # any one edge; objectives 1 (max abs) and 2 (sum abs) are identical for
    # all three, so objective 3 must pick the lexicographically smallest
    # elevation tuple in station entry order -> correction on the first edge.
    obs = [
        Observation(0, 1, 0, 5),   # BM -> B
        Observation(1, 2, 0, 5),   # B  -> C
        Observation(2, 0, 1, 5),   # C  -> BM
    ]
    r = adjust(["BM", "B", "C"], obs, 0, 0)
    assert r.feasible
    assert r.max_abs_correction == 1
    assert r.total_abs_correction == 1
    assert r.elevations == [0, -1, -1]
    assert r.corrections == [-1, 0, 0]


def test_minimax_then_total_with_parallel_observations():
    # BM -> B measured three times: 0, 0, 9 (mm).  Integer h must make
    # corrections h, h, h-9 within limits.
    obs = [
        Observation(0, 1, 0, 10),
        Observation(0, 1, 0, 10),
        Observation(0, 1, 9, 10),
    ]
    r = adjust(["BM", "B"], obs, 0, 0)
    assert r.feasible
    # Minimax allows h in {4, 5} (worst = 5 in both); the total objective
    # prefers h = 4: |4|+|4|+|-5| = 13 against 5+5+4 = 14.
    assert r.elevations == [0, 4]
    assert r.corrections == [4, 4, -5]
    assert r.max_abs_correction == 5
    assert r.total_abs_correction == 13


def test_infeasible_when_limits_too_tight():
    # Two contradictory observations between the same stations, no slack.
    obs = [
        Observation(0, 1, 0, 0),
        Observation(0, 1, 5, 0),
    ]
    r = adjust(["BM", "B"], obs, 0, 100)
    assert not r.feasible
    assert r.elevations == []
    assert r.reason and "允许改正量" in r.reason


def test_loop_with_misclosure_two_distributes_over_edges():
    # BM -> B -> C -> BM loop, measured closure forces signed sum -2.
    obs = [
        Observation(0, 1, 0, 5),
        Observation(1, 2, 0, 5),
        Observation(2, 0, 2, 5),
    ]
    r = adjust(["BM", "B", "C", "D"], obs + [Observation(0, 3, 7, 0)], 0, 0)
    assert r.feasible
    # Max abs correction must be 1 (spread over two edges), never 2.
    assert r.max_abs_correction == 1
    assert r.corrections[:3].count(-1) == 2
    # Tight-limit side observation pins D exactly.
    assert r.elevations[3] == 7
    # Every correction obeys its limit and back-delta identity holds.
    for o, c, b in zip(obs + [Observation(0, 3, 7, 0)], r.corrections, r.back_deltas):
        assert abs(c) <= o.limit
        assert b == o.delta + c
        assert b == r.elevations[o.end] - r.elevations[o.start]
