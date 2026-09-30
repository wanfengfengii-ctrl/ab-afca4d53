"""Semantic validation beyond field-level schema checks."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from .models import ObservationIn


class NetworkValidationError(ValueError):
    """The network as entered cannot define a unique adjustment."""


def validate_network(
    names: list[str],
    benchmark_index: int,
    observations: Iterable[ObservationIn],
) -> None:
    """Check that every station is connected (undirected) to the benchmark.

    Leveling observations are links between stations; a station with no path
    to the datum would have an arbitrary, meaningless elevation in the
    solution, so we reject such drafts with an explicit message.
    """
    observations = list(observations)
    index = {name: i for i, name in enumerate(names)}
    adjacency: dict[int, list[int]] = {i: [] for i in range(len(names))}
    for o in observations:
        u, v = index[o.start], index[o.end]
        adjacency[u].append(v)
        adjacency[v].append(u)

    seen = {benchmark_index}
    queue = deque([benchmark_index])
    while queue:
        u = queue.popleft()
        for v in adjacency[u]:
            if v not in seen:
                seen.add(v)
                queue.append(v)

    unreachable = [names[i] for i in range(len(names)) if i not in seen]
    if unreachable:
        raise NetworkValidationError(
            "测站 "
            + "、".join(unreachable)
            + " 与基准测站之间没有任何观测路径相连，无法确定其高程；"
            "请补充连接观测或删除该测站。"
        )
