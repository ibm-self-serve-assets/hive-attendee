import type { CSSProperties } from 'react';
import './chevrons.css';

export interface ChevronsProps {
  tier: 1 | 2 | 3;
  active: boolean;
  /** Static opacity when inactive: e.g. 0.4 blocked, 1 paused. */
  inactiveOpacity?: number;
  color?: string;
}

/** SVG group: insert inside your existing SVG with viewBox="0 0 120 120". */
export function Chevrons({ tier, active, inactiveOpacity = 1, color = '#fff' }: ChevronsProps) {
  return (
    <g className="hive-chevrons" data-active={active} aria-hidden="true"
      fill={color} style={{ '--hive-inactive-opacity': inactiveOpacity } as CSSProperties}>
      {Array.from({ length: tier }, (_, index) => {
        // Bottom to top. Center the group vertically for every tier.
        const y = 57.5 + (tier - 1) * 10 - index * 20;
        return <path key={index} className="hive-chevron"
          style={{ animationDelay: `${index * 0.24}s` }}
          d={`M39 ${y + 4} L60 ${y - 9} L81 ${y + 4} L81 ${y + 14} L60 ${y + 1} L39 ${y + 14} Z`} />;
      })}
    </g>
  );
}
