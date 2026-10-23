import React from 'react';
import { EventPanel } from '../../components/EventPanel';
import { FlowDots } from '../../components/FlowDots';
import { StationStats } from '../../components/StationStats';
import type { LevelScreenProps } from '../types';

// ── Static metadata ───────────────────────────────────────────────────────────

// Inventory order: copper energy metals / resin silicon
// Gathering grid: copper energy / metals resin / silicon
const RESOURCES: { id: string; label: string; icon: string }[] = [
  { id: 'copper',  label: 'Copper',  icon: '/icons/svg/resource_copper.svg' },
  { id: 'energy',  label: 'Energy',  icon: '/icons/svg/resources_energy.svg' },
  { id: 'metals',  label: 'Metals',  icon: '/icons/svg/resources_metals.svg' },
  { id: 'resin',   label: 'Resin',   icon: '/icons/svg/resources_resin.svg' },
  { id: 'silicon', label: 'Silicon', icon: '/icons/svg/resources_silicon.svg' },
];

const GATHERING_ORDER = ['copper', 'energy', 'metals', 'resin', 'silicon'];

const RESOURCE_ICON: Record<string, string> = {
  energy:    '/icons/svg/resources_energy.svg',
  resin:     '/icons/svg/resources_resin.svg',
  silicon:   '/icons/svg/resources_silicon.svg',
  metals:    '/icons/svg/resources_metals.svg',
  copper:    '/icons/svg/resource_copper.svg',
};

const PARTS: { id: string; label: string; icon: string }[] = [
  { id: 'actuator',    label: 'Actuators',   icon: '/icons/svg/parts_actuator.svg' },
  { id: 'battery',     label: 'Batteries',   icon: '/icons/svg/parts_battery.svg' },
  { id: 'chassis',     label: 'Chassis',     icon: '/icons/svg/parts_chassis.svg' },
  { id: 'electronics', label: 'Electronics', icon: '/icons/svg/parts_electronics.svg' },
];

const PART_ICON: Record<string, string> = {
  chassis:     '/icons/svg/parts_chassis.svg',
  electronics: '/icons/svg/parts_electronics.svg',
  actuator:    '/icons/svg/parts_actuator.svg',
  battery:     '/icons/svg/parts_battery.svg',
};

const STATIONS: { id: string; label: string; icon: string; output_type: string }[] = [
  { id: 'actuator_fabrication', label: 'Actuator Fabrication', icon: '/icons/svg/parts_actuator.svg',    output_type: 'actuator' },
  { id: 'battery_assembly',     label: 'Battery Assembly',     icon: '/icons/svg/parts_battery.svg',     output_type: 'battery' },
  { id: 'structural_molding',   label: 'Chassis Molding',      icon: '/icons/svg/parts_chassis.svg',     output_type: 'chassis' },
  { id: 'electronics_assembly', label: 'Electronics Assembly', icon: '/icons/svg/parts_electronics.svg', output_type: 'electronics' },
];

const ROBOTS: { id: string; station_id: string; label: string; icon: string }[] = [
  { id: 'engineer', station_id: 'worker_assembly',  label: 'Engineer', icon: '/icons/svg/robot-engineer.svg' },
  { id: 'forager',  station_id: 'forager_assembly', label: 'Forager',  icon: '/icons/svg/harvester.svg' },
];

// ── Inventory strip ───────────────────────────────────────────────────────────

const InventoryItem: React.FC<{ icon: string; label: string; qty: number }> = ({ icon, label, qty }) => (
  <div className="flex items-center gap-2">
    <img src={icon} width={22} height={22} alt={label} style={{ objectFit: 'contain' }} />
    <span className="text-sm text-[#57606A]">{label}</span>
    <span className="text-sm font-bold font-mono text-[#031040] tabular-nums ml-1">{qty}</span>
  </div>
);

// ── Floor sub-components (same as Level 2) ────────────────────────────────────

const InputChip: React.FC<{ icon: string; qty: number; blocked?: boolean }> = ({ icon, qty, blocked }) => (
  <span className="inline-flex items-center gap-0.5" style={{ color: blocked ? '#C75000' : '#57606A' }}>
    <img
      src={icon} width={18} height={18} alt=""
      style={{ objectFit: 'contain', opacity: blocked ? 1 : 0.85 }}
    />
    <span className="text-xs font-semibold tabular-nums" style={{ fontSize: 11 }}>+{qty}</span>
  </span>
);

const InputChips: React.FC<{
  inputs: Record<string, number>;
  iconMap: Record<string, string>;
  blockedKeys?: Set<string>;
}> = ({ inputs, iconMap, blockedKeys }) => (
  <span className="flex items-center flex-wrap gap-1.5">
    {Object.entries(inputs).map(([inputId, qty]) => {
      const icon = iconMap[inputId];
      if (!icon) return null;
      return <InputChip key={inputId} icon={icon} qty={qty} blocked={blockedKeys?.has(inputId)} />;
    })}
  </span>
);

// ── Main screen ───────────────────────────────────────────────────────────────

export const Level3Screen: React.FC<LevelScreenProps> = ({ state }) => {
  const {
    running,
    gathering_completed,
    manufacturing_completed,
    assembly_completed,
    gathering_blocked,
    manufacturing_blocked,
    assembly_blocked,
    manufacturing_inputs,
    assembly_inputs,
    job_durations,
    inventory,
    events,
  } = state;

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="flex items-start gap-0 min-w-0">

        {/* ── Column 1: Resource gathering ──────────────────────────────── */}
        <div className="flex-[4] flex flex-col gap-4 min-w-0">
          {/* Inventory */}
          <div className="rounded-xl border border-[#E0E8F8] bg-white px-5 py-4">
            <h2 className="text-[#2850B8] font-bold text-sm mb-3">Resource inventory</h2>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {RESOURCES.map(({ id, label, icon }) => (
                <InventoryItem key={id} icon={icon} label={label} qty={inventory.resource[id] ?? 0} />
              ))}
            </div>
          </div>
          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white p-5" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-4">Resource gathering</h2>
              <div className="grid grid-cols-2 gap-3">
                {GATHERING_ORDER.map((gid) => {
                  const res = RESOURCES.find(r => r.id === gid)!;
                  const { id, label, icon } = res;
                  const count   = gathering_completed[id] ?? 0;
                  const blocked = id in gathering_blocked;
                  const dur     = job_durations[id];
                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-center gap-2">
                      <div className="flex items-center gap-2 self-start">
                        <img src={icon} width={32} height={32} alt={label}
                          style={{ objectFit: 'contain' }} />
                        <span className="text-xs font-semibold text-[#57606A]">{label}</span>
                      </div>
                      <StationStats count={count} blocked={blocked} durationMins={dur} running={running}
                        tooltip="Waiting for resources" ringSize={95} showCount={false} />
                    </div>
                  );
                })}
              </div>
            </div>
            <EventPanel title="Resource events" events={events?.gathering ?? []} />
          </section>
        </div>

        <FlowDots running={running} />

        {/* ── Column 2: Parts manufacturing ─────────────────────────────── */}
        <div className="flex-[3] flex flex-col gap-4 min-w-0">
          {/* Inventory */}
          <div className="rounded-xl border border-[#E0E8F8] bg-white px-5 py-4">
            <h2 className="text-[#2850B8] font-bold text-sm mb-3">Parts inventory</h2>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {PARTS.map(({ id, label, icon }) => (
                <InventoryItem key={id} icon={icon} label={label} qty={inventory.part[id] ?? 0} />
              ))}
            </div>
          </div>
          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white p-5" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-4">Parts manufacturing</h2>
              <div className="flex flex-col gap-3">
                {STATIONS.map(({ id, label, icon, output_type }) => {
                  const count      = manufacturing_completed[id] ?? 0;
                  const blocked    = id in manufacturing_blocked;
                  const dur        = job_durations[id] ?? job_durations[output_type];
                  const inputs     = manufacturing_inputs[id] ?? {};
                  const missingSet = blocked ? new Set(Object.keys(manufacturing_blocked[id] ?? {})) : undefined;
                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] px-4 py-3">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                        <InputChips inputs={inputs} iconMap={RESOURCE_ICON} blockedKeys={missingSet} />
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <img src={icon} width={55} height={55} alt={output_type}
                          style={{ objectFit: 'contain' }} />
                        <StationStats count={count} blocked={blocked} durationMins={dur} running={running}
                          tooltip="Waiting for resources" ringSize={85} align="end" showCount={false} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <EventPanel title="Manufacturing events" events={events?.manufacturing ?? []} />
          </section>
        </div>

        <FlowDots running={running} />

        {/* ── Column 3: Robot assembly ───────────────────────────────────── */}
        <div className="flex-[3] flex flex-col gap-4 min-w-0">
          {/* Inventory */}
          <div className="rounded-xl border border-[#E0E8F8] bg-white px-5 py-4">
            <h2 className="text-[#2850B8] font-bold text-sm mb-3">Robot inventory</h2>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {ROBOTS.map(({ id, label, icon }) => (
                <InventoryItem key={id} icon={icon} label={label} qty={inventory.robot[id] ?? 0} />
              ))}
            </div>
            {/* Spacer row to match height of Resource/Parts inventory cards */}
            <div className="mt-2 h-[22px]" />
          </div>
          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white p-5" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-4">Robot assembly</h2>
              <div className="flex flex-col gap-3">
                {ROBOTS.map(({ id, station_id, label, icon }) => {
                  const count      = assembly_completed[id] ?? 0;
                  const blocked    = station_id in assembly_blocked;
                  const dur        = job_durations[station_id] ?? job_durations[id];
                  const inputs     = assembly_inputs[station_id] ?? {};
                  const missingSet = blocked ? new Set(Object.keys(assembly_blocked[station_id] ?? {})) : undefined;
                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] px-4 py-3">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <InputChips inputs={inputs} iconMap={PART_ICON} blockedKeys={missingSet} />
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <img src={icon} width={60} height={60} alt={label}
                          style={{ objectFit: 'contain' }} />
                        <StationStats count={count} blocked={blocked} durationMins={dur} running={running}
                          tooltip="Waiting for parts" ringSize={90} countClass="text-3xl" align="end" showCount={false} />
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
    </div>
  );
};
