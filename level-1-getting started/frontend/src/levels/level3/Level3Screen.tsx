import React from 'react';
import { EventPanel } from '../../components/EventPanel';
import { FlowDots } from '../../components/FlowDots';
import { HexagonTierBadge } from '../../components/HexagonTierBadge';
import { GatheringStation } from '../../components/GatheringStation';
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
      src={icon} width={22.5} height={22.5} alt=""
      style={{ objectFit: 'contain', opacity: blocked ? 1 : 0.85 }}
    />
    <span className="text-xs font-semibold tabular-nums" style={{ fontSize: 13.75 }}>+{qty}</span>
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

/** Tier hexagon. No upgrade/add-station controls before Level 4. */
const StationHexagon: React.FC<{
  tier: number;
  blocked: boolean;
  running: boolean;
  tooltip: string;
}> = ({ tier, blocked, running, tooltip }) => (
  <div className="flex flex-col items-center gap-1.5" style={{ width: 80 }}>
    <HexagonTierBadge tier={tier} blocked={blocked} active={running} tooltip={tooltip} size={50} />
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
    inventory,
    events,
  } = state;

  const level4 = useLevel4();
  const stationSlots = level4?.stationSlots ?? {};

  /** Tier of a station's (single) workstation — same source as Level 4. */
  const stationTier = (stationId: string) => stationSlots[stationId]?.[0]?.tier ?? 1;

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

                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-3">
                      <div className="flex items-center gap-2">
                        <img src={icon} width={28} height={28} alt={label} style={{ objectFit: 'contain' }} />
                        <span className="text-sm font-semibold text-[#031040]">{label}</span>
                      </div>
                      <GatheringStation tier={stationTier(id)} resourceName={label} />
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
                  const blocked    = id in manufacturing_blocked;
                  const inputs     = manufacturing_inputs[id] ?? {};
                  const missingSet = blocked ? new Set(Object.keys(manufacturing_blocked[id] ?? {})) : undefined;
                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <img src={icon} width={28} height={28} alt={output_type} style={{ objectFit: 'contain' }} />
                        <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                        <InputChips inputs={inputs} iconMap={RESOURCE_ICON} blockedKeys={missingSet} />
                      </div>
                      <StationHexagon tier={stationTier(id)} blocked={blocked}
                        running={running}
                        tooltip="Waiting for resources" />
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
          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white p-5" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-4">Worker robot assembly</h2>
              <div className="flex flex-col gap-3">
                {ROBOTS.map(({ id, station_id, label, icon }) => {
                  const blocked    = station_id in assembly_blocked;
                  const inputs     = assembly_inputs[station_id] ?? {};
                  const missingSet = blocked ? new Set(Object.keys(assembly_blocked[station_id] ?? {})) : undefined;
                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <img src={icon} width={40} height={40} alt={label} style={{ objectFit: 'contain' }} />
                        <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                        <InputChips inputs={inputs} iconMap={PART_ICON} blockedKeys={missingSet} />
                      </div>
                      <StationHexagon tier={stationTier(station_id)} blocked={blocked}
                        running={running}
                        tooltip="Waiting for parts" />
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
