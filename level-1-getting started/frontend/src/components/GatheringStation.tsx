import { Gathering, type Counts } from './gathering-component';

/** Dot colors taken from each resource's icon: main fill and its darker outline. */
const DOT_COLORS: Record<string, { fill: string; stroke: string }> = {
  Copper:  { fill: '#FF9E42', stroke: '#D36B00' },
  Energy:  { fill: '#6FDC8C', stroke: '#1E7A40' },
  Metals:  { fill: '#6FBEC6', stroke: '#226E78' },
  Resin:   { fill: '#FF9E42', stroke: '#D36B00' },
  Silicon: { fill: '#6FA1FE', stroke: '#2850B8' },
};

/** Read-only gathering graphic: tier controls the first circle's count and dot speed. */
export function GatheringStation({ tier, resourceName, running }: {
  tier: number;
  resourceName: string;
  /** Dots animate only while the Simulation is running. */
  running: boolean;
}) {
  const count = (Number.isFinite(tier)
    ? Math.max(1, Math.min(3, Math.trunc(tier)))
    : 1) as 1 | 2 | 3;
  const counts: Counts = [count, 0, 0, 0];
  return <Gathering counts={counts} readOnly active={running} resourceName={resourceName} dotColors={DOT_COLORS[resourceName]} />;
}
