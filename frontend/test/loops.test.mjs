import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fundamentalCycles, cycleClosures } from '../src/loops.js';

test('triangle yields one fundamental cycle', () => {
  // 0-1, 1-2, 2-0
  const edges = [
    { u: 0, v: 1, value: 5 },
    { u: 1, v: 2, value: -3 },
    { u: 2, v: 0, value: -2 },
  ];
  const cycles = fundamentalCycles(3, edges);
  assert.equal(cycles.length, 1);
  assert.equal(cycles[0].steps.length, 3);
});

test('square with diagonal yields two independent cycles', () => {
  const edges = [
    { u: 0, v: 1, value: 0 },
    { u: 1, v: 2, value: 0 },
    { u: 2, v: 3, value: 0 },
    { u: 3, v: 0, value: 0 },
    { u: 0, v: 2, value: 0 },
  ];
  const cycles = fundamentalCycles(4, edges);
  assert.equal(cycles.length, 2); // m - n + 1 = 5 - 4 + 1
});

test('tree network has no cycles', () => {
  const edges = [
    { u: 0, v: 1, value: 4 },
    { u: 0, v: 2, value: 2 },
    { u: 2, v: 3, value: -1 },
  ];
  assert.deepEqual(fundamentalCycles(4, edges), []);
});

test('disconnected graph returns no cycles', () => {
  const edges = [{ u: 0, v: 1, value: 1 }];
  assert.deepEqual(fundamentalCycles(3, edges), []);
});

test('signed closure is zero on gradients derived from elevations', () => {
  const stations = [{ name: 'A' }, { name: 'B' }, { name: 'C' }, { name: 'D' }];
  const elevations = [1000, 1012, 980, 995];
  const observations = [
    { start: 'A', end: 'B' },
    { start: 'B', end: 'C' },
    { start: 'C', end: 'D' },
    { start: 'D', end: 'A' },
    { start: 'A', end: 'C' },
  ];
  const closures = cycleClosures(stations, observations, elevations);
  assert.equal(closures.length, 2);
  for (const c of closures) assert.equal(c.closure, 0);
});

test('closure is signed: reversed traversal flips sign', () => {
  // Hand-built cycle 0->1 (edge 0), 1->2 (edge 1), 2->0 (edge 2) where the
  // stored orientation of edge 2 is 0->2, so traversal 2->0 must negate it.
  const edges = [
    { u: 0, v: 1, value: 10 },
    { u: 1, v: 2, value: 20 },
    { u: 0, v: 2, value: 25 },
  ];
  const cycles = fundamentalCycles(3, edges);
  assert.equal(cycles.length, 1);
  const sum = cycles[0].steps.reduce((acc, [a, b, k]) => {
    const e = edges[k];
    return acc + (e.u === a && e.v === b ? e.value : -e.value);
  }, 0);
  // 0->1: 10, 1->2: 20, 2->0: -25  => 5
  assert.equal(sum, 5);
});
