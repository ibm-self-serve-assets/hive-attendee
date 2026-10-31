import React from 'react';
import { EventPanel } from '../../components/EventPanel';
import type { LevelScreenProps } from '../types';

import {
  RESOURCES,
  STATIONS,
  ROBOTS,
} from '../robots';

export const Level1Screen: React.FC<LevelScreenProps> = ({ state }) => {
  const {
    gathering_completed,
    manufacturing_completed,
    assembly_completed,
    events,
  } = state;

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="flex items-start gap-[11px] min-w-0">

        {/* ── Lane 1: Resource gathering ─────────────────────────────── */}
        <section className="flex-none" style={{ minWidth: 300 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Gather resources</h2>
            <div className="grid grid-cols-2 gap-3">
              {RESOURCES.map(({ id, label, icon }) => {
                const count = gathering_completed[id] ?? 0;
                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <img src={icon} width={33} height={33} alt={label} />
                      <span className="text-sm font-semibold text-[#031040]">{label}</span>
                    </div>
                    <div className="text-2xl font-bold font-mono text-[#031040] tabular-nums mt-3">
                      {count}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <EventPanel title="Resource events" events={events?.gathering ?? []} />
        </section>

        {/* ── Lane 2: Parts manufacturing ────────────────────────────── */}
        <section className="flex-none" style={{ width: 380 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Manufacture parts</h2>
            <div className="flex flex-col gap-3">
              {STATIONS.map(({ id, label, icon }) => {
                const count = manufacturing_completed[id] ?? 0;
                return (
                  <div
                    key={id}
                    className="flex items-center justify-between gap-4 rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] px-4 py-3.5"
                  >
                    <div className="flex items-center gap-3">
                      <img src={icon} width={60} height={60} alt={label} style={{ objectFit: 'contain' }} />
                      <span className="text-sm font-semibold text-[#031040]">{label}</span>
                    </div>
                    <div className="text-2xl font-bold font-mono text-[#031040] tabular-nums text-right">
                      {count}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <EventPanel title="Manufacturing events" events={events?.manufacturing ?? []} />
        </section>

        {/* ── Lane 3: Robot assembly ─────────────────────────────────── */}
        <section className="flex-none" style={{ width: 380 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Assemble robots</h2>
            <div className="flex flex-col gap-3">
              {ROBOTS.map(({ id, label, icon }) => {
                const count = assembly_completed[id] ?? 0;
                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-4"
                  >
                    <div className="text-sm font-semibold text-[#031040] mb-3">{label}</div>
                    <div className="flex items-center justify-between gap-4">
                      <img src={icon} width={80} height={80} alt={label} style={{ objectFit: 'contain' }} />
                      <div className="text-3xl font-bold font-mono text-[#031040] tabular-nums">
                        {count}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <EventPanel title="Assembly events" events={events?.assembly ?? []} />
        </section>

      </div>
    </div>
  );
};
