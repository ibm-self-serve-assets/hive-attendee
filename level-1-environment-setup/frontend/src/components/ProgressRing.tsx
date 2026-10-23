import React from 'react';

interface ProgressRingProps {
  /** Label shown in the centre (e.g. "+5" or "3 mins") */
  label: string;
  size?: number;
  /** Whether the pulsing animation is active (1 cycle every 5 seconds) */
  spinning?: boolean;
  /**
   * When provided, draws a segmented arc instead of 12 uniform dots.
   * Each segment represents 1 minute; segments are evenly spaced around
   * the ring.  Capped at 60 so the ring never looks overwhelmed.
   */
  segments?: number;
}

/**
 * Dot spinner with two modes:
 *
 * 1. **Default (no `segments`)** — 12 evenly-spaced dots that pulse their
 *    opacity sequentially to simulate clockwise rotation.
 *
 * 2. **Segmented (`segments > 0`)** — one arc-dot per minute (capped at 60),
 *    still animating when `spinning` is true.  The number of segments comes
 *    from `elapsed_sim_minutes` in the `hive_job_durations` Flink topic.
 */
export const ProgressRing: React.FC<ProgressRingProps> = ({
  label,
  size = 80,
  spinning = true,
  segments,
}) => {
  const cx = size / 2;
  const cy = size / 2;
  const ringRadius = size * 0.37;
  const cycleSeconds = 5;

  // Determine dot count: use segments (capped at 60) or default 12.
  const numDots = segments != null && segments > 0
    ? Math.min(segments, 60)
    : 12;

  // Minimum dot radius so dots stay visible even with many segments.
  const dotRadius = numDots <= 12
    ? size * 0.052
    : Math.max(size * 0.025, size * 0.62 / numDots);

  const dots = Array.from({ length: numDots }, (_, i) => {
    // Clockwise: 0 = 12 o'clock
    const angle = (i * 360) / numDots;
    const rad = (angle * Math.PI) / 180;
    const x = cx + ringRadius * Math.sin(rad);
    const y = cy - ringRadius * Math.cos(rad);
    // Stagger delay so the "lit" dot travels clockwise
    const delay = -((((numDots - i) % numDots) * cycleSeconds) / numDots);
    return { x, y, delay, key: i };
  });

  return (
    <div className="relative inline-block select-none" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ display: 'block' }}
      >
        {dots.map(({ x, y, delay, key }) => (
          <circle
            key={key}
            cx={x}
            cy={y}
            r={dotRadius}
            fill="#2850B8"
            style={{
              opacity: spinning ? undefined : 0.15,
              animation: spinning ? `dotClockwiseFade ${cycleSeconds}s linear infinite` : 'none',
              animationDelay: spinning ? `${delay.toFixed(3)}s` : undefined,
            }}
          />
        ))}
      </svg>
      {/* Centre label — fixed orientation */}
      <div
        className="absolute inset-0 flex items-center justify-center font-bold text-[#031040] pointer-events-none"
        style={{
          fontSize: `${Math.round(size * 0.19)}px`,
          fontFamily: 'IBM Plex Sans, sans-serif',
          lineHeight: 1,
        }}
      >
        {label}
      </div>
    </div>
  );
};
