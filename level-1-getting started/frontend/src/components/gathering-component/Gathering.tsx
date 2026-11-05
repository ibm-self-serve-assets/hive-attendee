import { useRef, useState, type CSSProperties } from 'react';
import { addRequest, LABELS, TRAVEL_SECONDS, nextEligible, type AddRequest, type Counts, type NodeIndex } from './gatheringModel';
import './Gathering.css';
export type { AddRequest, Count, Counts, NodeIndex } from './gatheringModel';

export interface GatheringProps {
  /** Controlled counts, ordered upper-near, upper-far, lower-near, lower-far. */
  counts: Counts;
  /** Parent performs purchase/assignment and supplies updated counts. May be async. */
  onAdd?: (request: AddRequest) => void | Promise<void>;
  /** Disable adding (e.g. no unassigned Foragers, paused, or external request). */
  disabled?: boolean;
  /** Hide add controls while preserving counts and active animation. */
  readOnly?: boolean;
  /** Animate return trips. False hides dots; counts and routes remain visible. */
  active?: boolean;
  /** Accessible name only; no resource heading is drawn. */
  resourceName?: string;
  /** Fill and outline of the animated return-trip dots. Defaults to the light blue theme colors. */
  dotColors?: { fill: string; stroke: string };
  className?: string;
  style?: CSSProperties;
}
const POSITIONS = [[280, 75], [480, 75], [280, 235], [480, 235]] as const;
// Return paths run from each circle toward the hive, reversing the drawn branches.
const RETURN_PATHS = [
  'M280 75 C185 75 165 155 108 155',
  'M480 75 H280 C185 75 165 155 108 155',
  'M280 235 C185 235 165 155 108 155',
  'M480 235 H280 C185 235 165 155 108 155',
] as const;

/** Borderless gathering diagram. No purchases or simulation timing run internally. */
export function Gathering({ counts, onAdd, disabled = false, readOnly = false, active = true, resourceName = 'Resource', dotColors, className = '', style }: GatheringProps) {
  const eligible = nextEligible(counts);
  const lock = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function handleAdd(index: NodeIndex) {
    if (readOnly || !onAdd || disabled || lock.current) return;
    const request = addRequest(counts, index);
    if (!request) return;
    lock.current = true;
    setPending(true);
    setError('');
    try { await onAdd(request); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to add Forager. Try again.'); }
    finally { lock.current = false; setPending(false); }
  }
  const blue = 'var(--gathering-blue, #0755f9)';
  const inactive = 'var(--gathering-gray, #b8c0cb)';
  return <div className={`gathering ${className}`} style={style} role="group" aria-label={`${resourceName} gathering`} aria-busy={pending}>
    <div className="gathering__diagram">
      <svg className="gathering__routes" viewBox="0 0 600 310" aria-hidden="true">
        <g fill="none" strokeWidth="5" strokeLinecap="round">
          <path d="M108 155 C165 155 185 75 280 75" stroke={counts[0] ? blue : inactive}/>
          <path d="M280 75 H480" stroke={counts[1] ? blue : inactive}/>
          <path d="M108 155 C165 155 185 235 280 235" stroke={counts[2] ? blue : inactive}/>
          <path d="M280 235 H480" stroke={counts[3] ? blue : inactive}/>
        </g>
        {active && counts.map((count, index) => count > 0 && (
          <circle key={`${index}-${count}`} className="gathering__dot" r="15" fill={dotColors?.fill ?? 'var(--gathering-dot, #bde7ff)'} stroke={dotColors?.stroke ?? blue} strokeWidth="1">
            <animateMotion
              path={RETURN_PATHS[index]}
              dur={`${TRAVEL_SECONDS[count as 1 | 2 | 3]}s`}
              begin={`${-index * 0.8}s`}
              repeatCount="indefinite"
              calcMode="paced"
            />
          </circle>
        ))}
        <polygon points="108,155 90,186 54,186 36,155 54,124 90,124" fill={blue}/>
      </svg>
      {counts.map((count, i) => {
        const index = i as NodeIndex;
        const allowed = !readOnly && Boolean(onAdd) && index === eligible;
        return <div key={index} className="gathering__node" style={{ left: `${POSITIONS[index][0] / 6}%`, top: `${POSITIONS[index][1] / 3.1}%` }}>
          <svg className="gathering__circle" viewBox="0 0 100 100" role="img" aria-label={`${LABELS[index]}: ${count} of 3 Foragers`}>
            <circle cx="50" cy="50" r="47" fill={count ? blue : 'var(--gathering-empty, #eef1f5)'} stroke={count ? blue : inactive} strokeWidth="3"/>
            {count > 0 && <text x="50" y="51" textAnchor="middle" dominantBaseline="central" className="gathering__value">{count}</text>}
          </svg>
          {allowed && <button type="button" className="gathering__add" disabled={disabled || pending} onClick={() => void handleAdd(index)} aria-label={`Add Forager to ${resourceName}, ${LABELS[index]} (${count} of 3)`} title="Add Forager">+</button>}
        </div>;
      })}
    </div>
    <span className="gathering__sr" role="status">{counts.reduce<number>((a, b) => a + b, 0)} Foragers assigned{eligible === null ? '; all circles full' : ''}</span>
    {error && <p className="gathering__error" role="alert">{error}</p>}
  </div>;
}
