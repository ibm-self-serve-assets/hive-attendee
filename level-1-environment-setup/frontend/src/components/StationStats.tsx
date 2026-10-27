import React from 'react';

// ── Legacy segment-ring (kept as backup) ──────────────────────────────────────
// TODO: delete SegmentRingLegacy if DotSpinner is confirmed (see next_steps.md)
/**
 * Ring of arc segments, one per minute of the job duration (capped at 60 so the
 * ring stays readable), drawn as a progress bar: while `spinning` a segment turns
 * solid every `duration / n` seconds, clockwise from 12 o'clock, and stays solid
 * until the ring is full, then the ring resets.  1 real second = 1 sim minute, so
 * one lap takes "n mins" seconds.  Pausing the simulation freezes the ring.
 * The completed count and "n mins" are drawn inside the ring.
 */
export const SegmentRingLegacy: React.FC<{
  segments: number;
  size: number;
  spinning: boolean;
  count: number;
  showCount?: boolean;
  centerContent?: React.ReactNode;
}> = ({ segments, size, spinning, count, showCount = true, centerContent }) => {
  const lapMs = Math.max(1, segments) * 1000;
  const [elapsedMs, setElapsedMs] = React.useState(0);

  React.useEffect(() => {
    if (!spinning) return;
    let last = performance.now();
    const id = window.setInterval(() => {
      const now = performance.now();
      setElapsedMs((e) => (e + (now - last)) % lapMs);
      last = now;
    }, 100);
    return () => window.clearInterval(id);
  }, [spinning, lapMs]);

  const n = Math.min(Math.max(1, Math.round(segments)), 60);
  const stroke = Math.max(3, size * 0.075);
  const c = size / 2;
  const r = c - stroke;
  const step = 360 / n;
  const gap = n === 1 ? 0 : Math.min(16, step * 0.35);
  const lit = Math.min(n, Math.floor((elapsedMs / lapMs) * n) + 1);
  const point = (deg: number) => {
    const rad = (deg * Math.PI) / 180;
    return [c + r * Math.sin(rad), c - r * Math.cos(rad)];
  };

  const arcs = Array.from({ length: n }, (_, i) => {
    const [x0, y0] = point(i * step + gap / 2);
    const [x1, y1] = point((i + 1) * step - gap / 2);
    return { d: `M ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1}` };
  });

  return (
    <div className="relative inline-block select-none flex-none" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
        {n === 1 ? (
          <circle cx={c} cy={c} r={r} fill="none" strokeWidth={stroke} stroke="#DCE6FA" />
        ) : (
          arcs.map(({ d }, i) => (
            <path key={`t${i}`} d={d} fill="none" strokeWidth={stroke} strokeLinecap="butt" stroke="#DCE6FA" />
          ))
        )}
        {elapsedMs > 0 &&
          (n === 1 ? (
            <circle cx={c} cy={c} r={r} fill="none" strokeWidth={stroke} stroke="#2850B8" />
          ) : (
            arcs.slice(0, lit).map(({ d }, i) => (
              <path key={`s${i}`} d={d} fill="none" strokeWidth={stroke} strokeLinecap="butt" stroke="#2850B8" />
            ))
          ))}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none" style={{ pointerEvents: centerContent ? 'auto' : 'none' }}>
        {showCount && (
          <span className="font-bold font-mono text-[#031040] tabular-nums" style={{ fontSize: Math.round(size * 0.27) }}>
            {count}
          </span>
        )}
        {centerContent ?? (
          <span className="font-semibold text-[#57606A]" style={{ fontSize: Math.max(9, Math.round(size * 0.14)), marginTop: showCount ? 4 : 0 }}>
            {segments} mins
          </span>
        )}
      </div>
    </div>
  );
};

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
 * Internally renders DotSpinner instead of SegmentRingLegacy.
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
