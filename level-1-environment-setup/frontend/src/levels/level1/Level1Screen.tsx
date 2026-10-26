import React from 'react';
import { EventPanel } from '../../components/EventPanel';
import type { LevelScreenProps } from '../types';

// ── Resource gathering ────────────────────────────────────────────────────────
const RESOURCES: { id: string; label: string; icon: string }[] = [
  { id: 'copper',  label: 'Copper',  icon: '/icons/svg/resource_copper.svg' },
  { id: 'energy',  label: 'Energy',  icon: '/icons/svg/resources_energy.svg' },
  { id: 'metals',  label: 'Metals',  icon: '/icons/svg/resources_metals.svg' },
  { id: 'resin',   label: 'Resin',   icon: '/icons/svg/resources_resin.svg' },
  { id: 'silicon', label: 'Silicon', icon: '/icons/svg/resources_silicon.svg' },
];

// ── Parts manufacturing ───────────────────────────────────────────────────────
const STATIONS: { id: string; label: string; icon: string }[] = [
  { id: 'actuator_fabrication',  label: 'Actuator Fabrication', icon: '/icons/svg/parts_actuator.svg' },
  { id: 'battery_assembly',      label: 'Battery Assembly',     icon: '/icons/svg/parts_battery.svg' },
  { id: 'structural_molding',    label: 'Chassis Molding',      icon: '/icons/svg/parts_chassis.svg' },
  { id: 'electronics_assembly',  label: 'Electronics Assembly', icon: '/icons/svg/parts_electronics.svg' },
];

// ── Robot assembly ────────────────────────────────────────────────────────────
const ROBOTS: { id: string; label: string; icon: string }[] = [
  { id: 'engineer', label: 'Engineer', icon: '/icons/svg/robot-engineer.svg' },
  { id: 'forager',  label: 'Forager',  icon: '/icons/svg/harvester.svg' },
];

export const Level1Screen: React.FC<LevelScreenProps> = ({ state }) => {
  const {
    gathering_completed,
    manufacturing_completed,
    assembly_completed,
    events,
  } = state;

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="flex items-start gap-8 min-w-0">

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
        <section className="flex-none" style={{ minWidth: 280 }}>
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
        <section className="flex-none" style={{ minWidth: 220 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 480 }}
          >
            <h2 className="font-bold text-base text-[#031040] mb-4">Assemble robots</h2>
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
