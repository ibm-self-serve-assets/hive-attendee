import assert from 'node:assert/strict';
import { test } from 'node:test';
import { addRequest, nextEligible, TRAVEL_SECONDS, type Counts, type NodeIndex } from './gatheringModel';
test('all twelve assignments unlock in order; no early bottom row or far circle', () => {
  let counts: Counts = [0, 0, 0, 0];
  for (let step = 0; step < 12; step++) {
    const eligible = Math.floor(step / 3) as NodeIndex;
    assert.equal(nextEligible(counts), eligible);
    for (const i of [0, 1, 2, 3] as NodeIndex[]) if (i !== eligible) assert.equal(addRequest(counts, i), null);
    const previous = [...counts];
    const result = addRequest(counts, eligible)!;
    assert.deepEqual(counts, previous, 'input is not mutated');
    assert.equal(result.nextValue, step % 3 + 1);
    counts = result.nextCounts;
  }
  assert.deepEqual(counts, [3, 3, 3, 3]);
  assert.equal(nextEligible(counts), null);
  assert.equal(addRequest(counts, 3), null);
});
test('reject impossible state and invalid counts', () => {
  assert.throws(() => nextEligible([1, 1, 0, 0]));
  assert.throws(() => nextEligible([3, 0, 1, 0]));
  assert.throws(() => nextEligible([4, 0, 0, 0] as unknown as Counts));
});
test('dot durations match count mapping', () => assert.deepEqual(TRAVEL_SECONDS, {1: 10, 2: 5, 3: 3}));
