// Basic-cycle-basis closure checks for an undirected leveling network.
//
// A spanning tree is built from station 0; every non-tree edge defines one
// fundamental cycle.  For a perfectly adjusted network, the signed sum of
// the back-computed height differences around each such cycle must be 0.

/**
 * @typedef {Object} Edge
 * @property {number} u     start station index
 * @property {number} v     end station index
 * @property {number} value signed back-computed difference along u -> v
 */

/**
 * @param {number} stationCount
 * @param {Edge[]} edges
 * @returns {{ steps: [number, number, number][], edgeIndex: number }[]}
 *   each cycle is a list of directed steps [from, to, edgeIndex]; empty list
 *   is returned when the graph is disconnected (caller validates earlier).
 */
export function fundamentalCycles(stationCount, edges) {
  const adj = Array.from({ length: stationCount }, () => []);
  edges.forEach((e, idx) => {
    adj[e.u].push({ to: e.v, idx });
    adj[e.v].push({ to: e.u, idx });
  });

  const parent = new Array(stationCount).fill(-1);
  const parentEdge = new Array(stationCount).fill(-1);
  const depth = new Array(stationCount).fill(-1);
  const stack = [0];
  depth[0] = 0;
  const treeEdges = new Set();

  while (stack.length) {
    const x = stack.pop();
    for (const { to, idx } of adj[x]) {
      if (depth[to] !== -1) continue;
      depth[to] = depth[x] + 1;
      parent[to] = x;
      parentEdge[to] = idx;
      treeEdges.add(idx);
      stack.push(to);
    }
  }

  if (depth.some((d) => d === -1)) return []; // disconnected graph

  const lca = (a, b) => {
    while (depth[a] > depth[b]) a = parent[a];
    while (depth[b] > depth[a]) b = parent[b];
    while (a !== b) {
      a = parent[a];
      b = parent[b];
    }
    return a;
  };

  const cycles = [];
  edges.forEach((e, idx) => {
    if (treeEdges.has(idx)) return;
    const w = lca(e.u, e.v);
    // Cycle direction: travel the extra edge u -> v, then tree path v -> u.
    const steps = [[e.u, e.v, idx]];
    let cur = e.v;
    while (cur !== w) {
      steps.push([cur, parent[cur], parentEdge[cur]]);
      cur = parent[cur];
    }
    const tail = []; // u up to LCA, collected then reversed (LCA -> u)
    cur = e.u;
    while (cur !== w) {
      tail.push([parent[cur], cur, parentEdge[cur]]);
      cur = parent[cur];
    }
    steps.push(...tail);
    cycles.push({ steps, edgeIndex: idx });
  });
  return cycles;
}

/**
 * Signed closure (mm) of every fundamental cycle.
 * @returns {{ closure: number, steps: [number,number,number][] }[]}
 */
export function cycleClosures(stations, observations, elevations) {
  const byName = new Map(stations.map((s, i) => [s.name, i]));
  const edges = observations.map((o) => ({
    u: byName.get(o.start),
    v: byName.get(o.end),
    value: elevations[byName.get(o.end)] - elevations[byName.get(o.start)],
  }));
  return fundamentalCycles(stations.length, edges).map(({ steps }) => ({
    closure: steps.reduce((sum, [a, b, k]) => {
      const e = edges[k];
      return sum + (e.u === a && e.v === b ? e.value : -e.value);
    }, 0),
    steps,
  }));
}
