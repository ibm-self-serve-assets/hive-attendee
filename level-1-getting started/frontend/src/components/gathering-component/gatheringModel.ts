/** Clockwise reading order: upper-near, upper-far, lower-near, lower-far. */
export type Count = 0 | 1 | 2 | 3;
export type NodeIndex = 0 | 1 | 2 | 3;
export type Counts = readonly [Count, Count, Count, Count];
/** Decorative return-trip duration, in real seconds; not a production timer. */
export const TRAVEL_SECONDS = { 1: 10, 2: 5, 3: 3 } as const;
export const LABELS = ['upper near', 'upper far', 'lower near', 'lower far'] as const;
export interface AddRequest {
  index: NodeIndex;
  previousValue: Count;
  nextValue: 1 | 2 | 3;
  nextCounts: Counts;
}
/** Reject malformed or out-of-order external state instead of silently changing it. */
export function validateCounts(counts: Counts): void {
  if (counts.length !== 4 || counts.some(n => !Number.isInteger(n) || n < 0 || n > 3))
    throw new Error('Gathering requires four integer counts between 0 and 3.');
  let incomplete = false;
  for (const count of counts) {
    if (incomplete && count !== 0) throw new Error('Fill each circle to 3 in reading order before starting the next.');
    if (count < 3) incomplete = true;
  }
}
export function nextEligible(counts: Counts): NodeIndex | null {
  validateCounts(counts);
  const index = counts.findIndex(n => n < 3);
  return index < 0 ? null : index as NodeIndex;
}
export function addRequest(counts: Counts, index: NodeIndex): AddRequest | null {
  if (nextEligible(counts) !== index) return null;
  const nextValue = (counts[index] + 1) as 1 | 2 | 3;
  const nextCounts: [Count, Count, Count, Count] = [...counts];
  nextCounts[index] = nextValue;
  return { index, previousValue: counts[index], nextValue, nextCounts };
}
