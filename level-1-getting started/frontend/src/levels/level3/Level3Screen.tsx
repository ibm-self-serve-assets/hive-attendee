import React from 'react';
import { EventPanel } from '../../components/EventPanel';
import { FlowDots } from '../../components/FlowDots';
import { HexagonTierBadge } from '../../components/HexagonTierBadge';
import { AssemblyQueue } from '../../components/AssemblyQueue';
import { useLevel4 } from '../level4/Level4Context';
import type { LevelScreenProps } from '../types';

import {
  GATHERING_ORDER,
  RESOURCES,
  RESOURCE_ICON,
  STATIONS,
  ROBOTS,
  PARTS,
  PART_ICON,
} from '../robots';

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

/** Tier hexagon with the job duration beneath it. No upgrade/add-station controls before Level 4. */
const StationHexagon: React.FC<{
  tier: number;
  blocked: boolean;
  durationText: string;
  running: boolean;
  tooltip: string;
}> = ({ tier, blocked, durationText, running, tooltip }) => (
  <div className="flex flex-col items-center gap-1.5" style={{ width: 80 }}>
    <HexagonTierBadge tier={tier} blocked={blocked} active={running} tooltip={tooltip} size={50} />
    <span
      className="text-xs font-semibold leading-tight text-center whitespace-nowrap"
      style={{ color: blocked ? '#D36B00' : '#57606A' }}
    >
      {blocked ? 'Parts unavailable' : durationText}
    </span>
  </div>
);

// ── Main screen ───────────────────────────────────────────────────────────────

export const Level3Screen: React.FC<LevelScreenProps> = ({ state }) => {
  const {
    running,
    manufacturing_blocked,
    assembly_blocked,
    manufacturing_inputs,
    assembly_inputs,
    job_durations,
    inventory,
    events,
    robot_queue,
  } = state;

  const queue = robot_queue ?? [];
  const level4 = useLevel4();
  const stationSlots = level4?.stationSlots ?? {};

  /** Tier of a station's (single) workstation, and its duration label — same sources as Level 4. */
  const stationTier = (stationId: string) => stationSlots[stationId]?.[0]?.tier ?? 1;
  const durationLabel = (dur?: number) => dur == null ? `? mins` : `${dur} mins`;

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="flex items-start gap-0 min-w-0">

        {/* ── Column 1: Resource gathering ──────────────────────────────── */}
        <div className="flex-[4] flex flex-col gap-4 min-w-0">
          {/* Inventory */}
          <div className="rounded-xl border border-[#E0E8F8] bg-white px-5 py-2">
            <h2 className="text-[#2850B8] font-bold text-sm mb-1">Resource inventory</h2>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {RESOURCES.map(({ id, label, icon }) => (
                <InventoryItem key={id} icon={icon} label={label} qty={inventory.resource[id] ?? 0} />
              ))}
            </div>
          </div>
          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white p-3" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-1">Resource gathering</h2>
              <div className="grid grid-cols-2 gap-3">
                {GATHERING_ORDER.map((gid) => {
                  const res = RESOURCES.find(r => r.id === gid)!;
                  const { id, label, icon } = res;
                  const blocked = false;
                  const dur     = job_durations[id];
                  
                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-2">
                      <div className="flex items-center gap-2 self-start">
                        <img src={icon} width={32} height={32} alt={label}
                          style={{ objectFit: 'contain' }} />
                        <span className="text-xs font-semibold text-[#57606A]">{label}</span>
                      </div>
                      <StationHexagon tier={stationTier(id)} blocked={blocked}
                        durationText={durationLabel(dur)} running={running}
                        tooltip="Waiting for resources" />
                    </div>
                  );
                })}
              </div>
            </div>
            <EventPanel title="Resource events" events={events?.gathering ?? []} defaultOpen={false} />
          </section>
        </div>

        <FlowDots running={running} />

        {/* ── Column 2: Parts manufacturing ─────────────────────────────── */}
        <div className="flex-[3] flex flex-col gap-4 min-w-0">
          {/* Inventory */}
          <div className="rounded-xl border border-[#E0E8F8] bg-white px-4 py-2">
            <h2 className="text-[#2850B8] font-bold text-sm mb-1">Parts inventory</h2>
            <div className="flex flex-wrap gap-x-6 gap-y-1">
              {PARTS.map(({ id, label, icon }) => (
                <InventoryItem key={id} icon={icon} label={label} qty={inventory.part[id] ?? 0} />
              ))}
            </div>
          </div>
          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white px-4 py-2" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-1">Parts manufacturing</h2>
              <div className="flex flex-col gap-3">
                {STATIONS.map(({ id, label, icon, output_type }) => {
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
                      <div className="flex items-center gap-4">
                        <img src={icon} width={55} height={55} alt={output_type}
                          style={{ objectFit: 'contain' }} />
                        <StationHexagon tier={stationTier(id)} blocked={blocked}
                          durationText={durationLabel(dur)} running={running}
                          tooltip="Waiting for resources" />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <EventPanel title="Manufacturing events" events={events?.manufacturing ?? []} defaultOpen={false} />
          </section>
        </div>

        <FlowDots running={running} />

        {/* ── Column 3: Worker robot assembly ───────────────────────────────────── */}
        <div className="flex-[3] flex flex-col gap-2 min-w-0">
          {/* The Queen's open orders */}
          <AssemblyQueue queue={queue} />

          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white px-3 py-2" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-1">Worker robot assembly</h2>
              <div className="flex flex-col gap-3">
                {ROBOTS.map(({ id, station_id, label, icon }) => {
                  const blocked    = station_id in assembly_blocked;
                  const dur        = job_durations[station_id] ?? job_durations[id];
                  const inputs     = assembly_inputs[station_id] ?? {};
                  const missingSet = blocked ? new Set(Object.keys(assembly_blocked[station_id] ?? {})) : undefined;
                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] px-4 py-3">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                        <InputChips inputs={inputs} iconMap={PART_ICON} blockedKeys={missingSet} />
                      </div>
                      <div className="flex items-center gap-4">
                        <img src={icon} width={60} height={60} alt={label} style={{ objectFit: 'contain' }} />
                        <StationHexagon tier={stationTier(station_id)} blocked={blocked}
                          durationText={durationLabel(dur)} running={running}
                          tooltip="Waiting for parts" />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <EventPanel title="Assembly events" events={events?.assembly ?? []} defaultOpen={false} />
          </section>
        </div>

      </div>
    </div>
  );
};
