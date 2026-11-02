import React from 'react';
import { Chevrons } from './Chevrons';

export const HexagonTierBadge: React.FC<{
  tier: number;
  blocked?: boolean;
  /** Gray out without the warning icon (e.g. nothing scheduled to build). */
  disabled?: boolean;
  active?: boolean;
  tooltip?: string;
  size?: number;
}> = ({ tier: tierProp, blocked = false, disabled = false, active = false, tooltip, size = 50 }) => {
  const height = Math.round(size * 1.15);
  const tier = (Math.max(1, Math.min(3, tierProp))) as 1 | 2 | 3;
  const gray = blocked || disabled;

  return (
    <div className="relative select-none flex-none" style={{ width: size, height }}>
      <svg
        viewBox="0 0 120 120"
        width={size}
        height={height}
        style={{
          display: 'block',
          overflow: 'visible',
          filter: gray ? 'grayscale(1)' : 'none',
        }}
      >
        {/* Solid blue hexagon (grayscale when blocked or disabled) */}
        <polygon
          points="60,6 107,33 107,87 60,114 13,87 13,33"
          fill={gray ? '#8C9BAE' : '#0059E8'}
          stroke={gray ? '#8C9BAE' : '#0059E8'}
          strokeWidth="4"
          strokeLinejoin="round"
        />

        {/* Animated Chevrons */}
        <Chevrons
          tier={tier}
          active={active && !gray}
          inactiveOpacity={gray ? 0.4 : 1}
        />
      </svg>

      {/* Warning icon overlay on top right */}
      {blocked && (
        <img
          src="/icons/svg/warning.svg"
          width={22}
          height={22}
          alt="blocked"
          title={tooltip ?? 'Blocked'}
          className="absolute -top-1.5 -right-2 drop-shadow-sm pointer-events-auto"
          style={{ objectFit: 'contain' }}
        />
      )}
    </div>
  );
};
