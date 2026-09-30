"""Least-squares-free integer leveling-network adjustment.

The network is adjusted by choosing integer elevations ``H_i`` for every
station so that, for every directed observation ``u -> v`` with measured
height difference ``d`` (integer millimetres), the correction

        c = H_v - H_u - d

satisfies ``|c| <= limit`` (the observation's maximum allowed correction).

When several adjustments are feasible we select one lexicographically:

1. minimum maximum absolute correction  ``max |c|``,
2. minimum total absolute correction    ``sum |c|``  (given 1),
3. lexicographically smallest elevation tuple expanded in the order the
   stations were entered                        (given 1 and 2),

with the benchmark station pinned to its given datum elevation.

Each level is an integer linear program solved with CBC (bundled with
PuLP); a level is only solved after the previous objective has been fixed
to its optimum, which avoids the numerical risk of large composite weights.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pulp


@dataclass(frozen=True)
class Observation:
    start: int          # index of the start station
    end: int            # index of the end station
    delta: int          # measured height difference, mm
    limit: int          # maximum allowed absolute correction, mm


@dataclass(frozen=True)
class AdjustmentResult:
    feasible: bool
    elevations: list[int]
    corrections: list[int]      # aligned with the input observations
    back_deltas: list[int]      # recomputed H_end - H_start, mm
    max_abs_correction: int
    total_abs_correction: int
    reason: str | None = None


def _new_solver() -> pulp.LpSolver:
    # Prefer a system-installed CBC (the Docker image ships coinor-cbc at
    # /usr/bin/cbc); fall back to the binary bundled with PuLP for local runs.
    system_cbc = "/usr/bin/cbc"
    if os.path.isfile(system_cbc) and os.access(system_cbc, os.X_OK):
        return pulp.COIN_CMD(path=system_cbc, msg=0)
    return pulp.PULP_CBC_CMD(msg=0)


def adjust(
    elevations: list[int],
    observations: list[Observation],
    benchmark_index: int,
    benchmark_height: int,
) -> AdjustmentResult:
    """Solve the leveling adjustment described in the module docstring.

    ``elevations`` only supplies station ordering; its numeric values are
    ignored except for the benchmark entry, which is fixed.
    """
    n = len(elevations)
    m = len(observations)

    # Elevations are bounded integers.  The bound is generous but finite so
    # the MILP stays well-defined even on a disconnected, unconstrained
    # component; datum + limits pin every component that matters.  With at
    # most 10 stations no feasible network needs elevations outside this.
    span = max([abs(benchmark_height)] + [abs(o.delta) + o.limit for o in observations])
    bound = span + 1_000_000

    prob = pulp.LpProblem("leveling", pulp.LpMinimize)
    h = [
        pulp.LpVariable(f"h_{i}", lowBound=-bound, upBound=bound, cat="Integer")
        for i in range(n)
    ]

    pos = [pulp.LpVariable(f"p_{k}", lowBound=0, cat="Integer") for k in range(m)]
    neg = [pulp.LpVariable(f"n_{k}", lowBound=0, cat="Integer") for k in range(m)]
    c = [pos[k] - neg[k] for k in range(m)]

    prob += h[benchmark_index] == benchmark_height, "datum"

    for k, o in enumerate(observations):
        # c_k = H_end - H_start - measured delta
        prob += c[k] == h[o.end] - h[o.start] - o.delta, f"corr_{k}"
        prob += c[k] <= o.limit, f"lim_hi_{k}"
        prob += c[k] >= -o.limit, f"lim_lo_{k}"

    worst = pulp.LpVariable("worst", lowBound=0, cat="Integer")
    for k in range(m):
        prob += worst >= pos[k] + neg[k], f"worst_hi_{k}"

    # ---- Level 1: minimize the maximum absolute correction ---------------
    prob.objective = pulp.lpSum([worst])
    status = prob.solve(_new_solver())
    if status != 1:  # pulp.constants.LpStatusOptimal
        return AdjustmentResult(
            feasible=False,
            elevations=[],
            corrections=[],
            back_deltas=[],
            max_abs_correction=0,
            total_abs_correction=0,
            reason=(
                "无可行配平：在各观测允许改正量内无法同时满足，"
                "请放宽一条或多条观测的最大允许改正量。"
            ),
        )

    w_star = int(round(pulp.value(worst)))
    prob += worst <= w_star, "fix_worst"

    # ---- Level 2: minimize the sum of absolute corrections ----------------
    total = pulp.lpSum(pos[k] + neg[k] for k in range(m))
    prob.objective = total
    prob.solve(_new_solver())
    t_star = int(round(pulp.value(total)))
    prob += total <= t_star, "fix_total"

    # ---- Level 3: lexicographically smallest elevation tuple --------------
    # Variables not yet pinned shift freely, so we resolve one station at a
    # time, each time fixing every earlier station to its chosen value.
    chosen: list[int] = []
    for i in range(n):
        if i == benchmark_index:
            chosen.append(benchmark_height)
            continue
        prob.objective = pulp.lpSum([h[i]])
        prob.solve(_new_solver())
        val = int(round(pulp.value(h[i])))
        prob += h[i] == val, f"fix_h_{i}"
        chosen.append(val)

    corrections = [
        chosen[o.end] - chosen[o.start] - o.delta for o in observations
    ]
    back_deltas = [chosen[o.end] - chosen[o.start] for o in observations]

    return AdjustmentResult(
        feasible=True,
        elevations=chosen,
        corrections=corrections,
        back_deltas=back_deltas,
        max_abs_correction=max((abs(c) for c in corrections), default=0),
        total_abs_correction=sum(abs(c) for c in corrections),
    )
