import React from 'react';

// ── New dot-spinner ───────────────────────────────────────────────────────────
/**
 * 8-dot classic loading spinner.
 * All dots are the same size. The active "head" steps clockwise once per
 * durationSecs seconds (one step = durationSecs/8 seconds). The head dot is
 * near-black; the dot one step behind is mid-grey; all others are pale.
 * When `spinning` is false all dots render as uniform pale grey.
 */
const NUM_DOTS = 15;

export const DotSpinner: React.FC<{
  durationSecs: number;
  size: number;
  spinning: boolean;
  centerContent?: React.ReactNode;
}> = ({ durationSecs, size, spinning, centerContent }) => {
  const lapMs = Math.max(1, durationSecs) * 1000;
  const [headStep, setHeadStep] = React.useState(0);

  React.useEffect(() => {
    if (!spinning) return;
    const stepMs = lapMs / NUM_DOTS;
    const id = window.setInterval(() => {
      setHeadStep((s) => (s + 1) % NUM_DOTS);
    }, stepMs);
    return () => window.clearInterval(id);
  }, [spinning, lapMs]);

  const c = size / 2;
  const orbitR = size * 0.35;
  const dotR   = size * 0.0275;

  // Colour stops: head = near-black, one behind = mid-grey, rest = pale
  const dotColor = (i: number): string => {
    const behind = ((headStep - i) % NUM_DOTS + NUM_DOTS) % NUM_DOTS;
    if (!spinning)    return '#D0D8E8';
    if (behind === 0) return '#2D3748';   // head
    if (behind === 1) return '#718096';   // one behind
    return '#D0D8E8';                     // all others pale
  };

  return (
    <div className="relative inline-flex items-center justify-center select-none flex-none"
      style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}
        style={{ display: 'block', position: 'absolute', top: 0, left: 0 }}>
        {Array.from({ length: NUM_DOTS }, (_, i) => {
          const angleDeg = (i / NUM_DOTS) * 360 - 90;
          const angleRad = (angleDeg * Math.PI) / 180;
          const x = c + orbitR * Math.cos(angleRad);
          const y = c + orbitR * Math.sin(angleRad);
          return <circle key={i} cx={x} cy={y} r={dotR} fill={dotColor(i)} />;
        })}
      </svg>
      <div className="relative flex flex-col items-center justify-center leading-none z-10"
        style={{ pointerEvents: centerContent ? 'auto' : 'none' }}>
        {centerContent}
      </div>
    </div>
  );
};

const COUNT_SCALE = 0.27;

// ── SegmentRing: now delegates to DotSpinner ──────────────────────────────────
/**
 * Public API unchanged — callers pass the same props.
 * Internally renders DotSpinner.
 * The "n mins" label or custom centerContent is shown in the centre.
 */
export const SegmentRing: React.FC<{
  segments: number;
  size: number;
  spinning: boolean;
  count: number;
  showCount?: boolean;
  centerContent?: React.ReactNode;
  countScale?: number;
}> = ({ segments, size, spinning, count, showCount = true, centerContent, countScale = COUNT_SCALE }) => {
  const inner = centerContent ?? (
    <span className="font-semibold text-[#57606A]"
      style={{ fontSize: Math.max(9, Math.round(size * 0.14)), marginTop: showCount ? 4 : 0 }}>
      {segments} mins
    </span>
  );

  return (
    <DotSpinner durationSecs={segments} size={size} spinning={spinning}
      centerContent={
        <div className="flex flex-col items-center gap-0">
          {showCount && (
            <span className="font-bold font-mono text-[#031040] tabular-nums"
              style={{ fontSize: Math.round(size * countScale) }}>
              {count}
            </span>
          )}
          {inner}
        </div>
      }
    />
  );
};

/**
 * Per-station figure, always `ringSize` square so every state lines up.
 *  - Duration known and not blocked: DotSpinner (via SegmentRing).
 *  - Blocked: the count with a warning icon where "n mins" would be.
 *  - Duration not yet known: the count with "? mins" below it.
 * The count and label use the same fonts as inside the ring.
 */
export const StationStats: React.FC<{
  count: number;
  blocked: boolean;
  durationMins?: number;
  running: boolean;
  tooltip?: string;
  ringSize?: number;
  showCount?: boolean;
  centerContent?: React.ReactNode;
  countScale?: number;
}> = ({ count, blocked, durationMins, running, tooltip, ringSize = 72, showCount = true, centerContent, countScale = COUNT_SCALE }) => {
  if (!blocked && durationMins != null) {
    return <SegmentRing segments={durationMins} size={ringSize} spinning={running} count={count} showCount={showCount} centerContent={centerContent} countScale={countScale} />;
  }

  // The label slot is as tall as the "n mins" label, so the count sits exactly where it
  // does in the ring; the warning icon is centred in that slot and may overflow it.
  const labelSize = Math.max(9, Math.round(ringSize * 0.14));
  const iconSize = showCount ? 20 : 30;

  return (
    <div
      className="flex flex-col items-center justify-center leading-none select-none flex-none"
      style={{ width: ringSize, height: ringSize }}
    >
      {showCount && (
        <span className="font-bold font-mono text-[#031040] tabular-nums" style={{ fontSize: Math.round(ringSize * countScale) }}>
          {count}
        </span>
      )}
      <div className="flex items-center justify-center" style={{ height: labelSize, marginTop: showCount ? 4 : 0 }}>
        {blocked ? (
          <img
            src="/icons/svg/warning.svg"
            width={iconSize}
            height={iconSize}
            alt="blocked"
            title={tooltip}
            style={{ objectFit: 'contain', cursor: 'help', flex: 'none' }}
          />
        ) : (
          <span className="font-semibold text-[#57606A]" style={{ fontSize: labelSize }}>? mins</span>
        )}
      </div>
    </div>
  );
};
