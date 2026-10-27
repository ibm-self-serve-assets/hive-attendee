import React, { useEffect, useState } from 'react';
import { HiveEvent } from '../types';

const titleCase = (s: string) =>
  s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const sentenceCase = (s: string) => {
  const t = s.replace(/_/g, ' ');
  return t.charAt(0).toUpperCase() + t.slice(1);
};

/** Compact sim time for the log: "0d 01:46" (days, hours:minutes). */
const fmtLogTime = (totalMin: number) => {
  const mins = Math.max(0, totalMin);
  const d = Math.floor(mins / 1440);
  const h = Math.floor((mins % 1440) / 60);
  const m = mins % 60;
  return `${d}d ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

const asNum = (v: unknown) => (typeof v === 'number' ? v : Number(v) || 0);

const fmtCounts = (obj: unknown): string => {
  if (!obj || typeof obj !== 'object') return '';
  return Object.entries(obj as Record<string, unknown>)
    .map(([k, v]) => `${titleCase(k)} ×${asNum(v)}`)
    .join(', ');
};

/** One useful line of detail drawn from the event payload. */
export function describeEvent(ev: HiveEvent): string {
  const p = ev.payload ?? {};
  const workstation = typeof p.station_id === 'string' ? titleCase(p.station_id) : '';
  switch (ev.event_type) {
    case 'gathering.started':
      return `${titleCase(String(p.station_id ?? ''))}`;
    case 'gathering.completed':
      return `+${asNum(p.quantity)} ${titleCase(String(p.station_id ?? ''))}`;
    case 'manufacturing.resources.acquired':
      return `${station} →  (${fmtCounts(p.inputs_acquired)})`;
    case 'manufacturing.started':
      return `${station} → ${titleCase(String(p.output_type ?? ''))} (uses ${fmtCounts(p.inputs)})`;
    case 'manufacturing.completed':
      return `${titleCase(String(p.part_id ?? ''))} +${asNum(p.quantity) || 1} from ${station}`;
    case 'manufacturing.blocked':
    case 'assembly.blocked':
      return `${station} waiting for ${fmtCounts(p.missing_inputs) || 'inputs'}`;
    case 'assembly.started':
      return `${station} → ${titleCase(String(p.output_type ?? ''))} (uses ${fmtCounts(p.inputs)})`;
    case 'assembly.completed':
      return `${titleCase(String(p.output_type ?? ''))} +${asNum(p.quantity) || 1} from ${station}`;
    default:
      return Object.keys(p).length ? sentenceCase(Object.keys(p).join(', ')) : '';
  }
}

const isBlocked = (type: string) => type.endsWith('.blocked');

// ── Detail modal ─────────────────────────────────────────────────────────────

const ENVELOPE_FIELDS: [keyof HiveEvent, string][] = [
  ['event_type', 'Event type'],
  ['occurred_at', 'Occurred at'],
  ['sim_time_minutes', 'Sim time (min)'],
  ['event_id', 'Event ID'],
  ['causation_id', 'Caused by'],
  ['event_sequence', 'Sequence'],
  ['state_revision', 'State revision'],
  ['run_generation', 'Run generation'],
  ['run_id', 'Run ID'],
  ['simulation_id', 'Simulation ID'],
  ['server_epoch', 'Server epoch'],
  ['schema_version', 'Schema version'],
];

const EventModal: React.FC<{ event: HiveEvent; onClose: () => void }> = ({ event, onClose }) => {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const payloadEntries = Object.entries(event.payload ?? {});

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#031040]/50 p-6"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-xl max-h-[85vh] overflow-auto rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#E0E8F8] px-5 py-4">
          <div>
            <div
              className={`font-mono text-base font-semibold ${
                isBlocked(event.event_type) ? 'text-[#C2410C]' : 'text-[#2850B8]'
              }`}
            >
              {event.event_type}
            </div>
            <div className="text-xs text-[#57606a] mt-0.5">{describeEvent(event)}</div>
          </div>
          <button
            onClick={onClose}
            className="text-[#57606a] hover:text-[#031040] text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="px-5 py-4 space-y-5">
          <section>
            <h3 className="text-xs font-bold uppercase tracking-wide text-[#57606a] mb-2">Envelope</h3>
            <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-1.5 text-xs">
              {ENVELOPE_FIELDS.map(([key, label]) => {
                const v = event[key];
                if (v === undefined || v === null || v === '') return null;
                return (
                  <React.Fragment key={key}>
                    <dt className="text-[#57606a]">{label}</dt>
                    <dd className="font-mono text-[#031040] break-all">{String(v)}</dd>
                  </React.Fragment>
                );
              })}
            </dl>
          </section>

          <section>
            <h3 className="text-xs font-bold uppercase tracking-wide text-[#57606a] mb-2">Payload</h3>
            {payloadEntries.length === 0 ? (
              <div className="text-xs italic text-[#8AA0D0]">Empty</div>
            ) : (
              <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-1.5 text-xs">
                {payloadEntries.map(([k, v]) => (
                  <React.Fragment key={k}>
                    <dt className="text-[#57606a]">{k}</dt>
                    <dd className="font-mono text-[#031040] break-all">
                      {typeof v === 'object' && v !== null ? (
                        <pre className="whitespace-pre-wrap">{JSON.stringify(v, null, 2)}</pre>
                      ) : (
                        String(v)
                      )}
                    </dd>
                  </React.Fragment>
                ))}
              </dl>
            )}
          </section>

          <section>
            <h3 className="text-xs font-bold uppercase tracking-wide text-[#57606a] mb-2">Raw JSON</h3>
            <pre className="rounded-lg bg-[#F8FAFD] border border-[#E8EFF8] p-3 text-[11px] leading-relaxed overflow-auto text-[#031040]">
              {JSON.stringify(event, null, 2)}
            </pre>
          </section>
        </div>
      </div>
    </div>
  );
};

// ── Panel ────────────────────────────────────────────────────────────────────

interface EventPanelProps {
  title: string;
  events: HiveEvent[];
}

export const EventPanel: React.FC<EventPanelProps> = ({ title, events }) => {
  const [open, setOpen] = useState(true);
  const [selected, setSelected] = useState<HiveEvent | null>(null);

  return (
    <div className="mt-4 rounded-xl border border-[#E0E8F8] bg-white overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 text-sm font-bold text-[#2850B8]">
          {title}
          <span className="rounded bg-[#EEF1FB] px-1.5 py-0.5 text-[11px] font-semibold text-[#2850B8]">
            {events.length}
          </span>
        </span>
        <svg
          width="18"
          height="18"
          viewBox="0 0 20 20"
          fill="none"
          stroke="#57606a"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          style={{ transform: open ? 'none' : 'rotate(180deg)' }}
        >
          <path d="M5 12.5 10 7.5l5 5" />
        </svg>
      </button>

      {open && (
        <div className="border-t border-[#E8EFF8] overflow-y-auto" style={{ maxHeight: 280 }}>
          {events.length === 0 ? (
            <div className="px-4 py-4 text-left text-xs italic text-[#8AA0D0]">No events yet.</div>
          ) : (
            <ul>
              {events.map((ev) => (
                <li key={ev.event_id} className="border-b border-[#EEF3FA] last:border-b-0">
                  <button
                    onClick={() => setSelected(ev)}
                    className="w-full flex gap-3 px-4 py-2.5 text-left hover:bg-[#F8FAFD]"
                  >
                    <span className="font-mono text-[11px] text-[#57606a] tabular-nums shrink-0 pt-0.5">
                      {fmtLogTime(ev.sim_time_minutes)}
                    </span>
                    <span className="min-w-0">
                      <span
                        className={`block text-xs font-semibold ${
                          isBlocked(ev.event_type) ? 'text-[#C2410C]' : 'text-[#2850B8]'
                        }`}
                      >
                        {ev.event_type}
                      </span>
                      <span className="block text-xs text-[#031040] break-words">
                        {describeEvent(ev)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {selected && <EventModal event={selected} onClose={() => setSelected(null)} />}
    </div>
  );
};
