import { Gathering, type Counts } from './gathering-component';

/** Read-only gathering graphic: tier controls the first circle's count and dot speed. */
export function GatheringStation({ tier, resourceName }: {
  tier: number;
  resourceName: string;
}) {
  const count = (Number.isFinite(tier)
    ? Math.max(1, Math.min(3, Math.trunc(tier)))
    : 1) as 1 | 2 | 3;
  const counts: Counts = [count, 0, 0, 0];
  return <Gathering counts={counts} readOnly resourceName={resourceName} />;
}
