import React from 'react';
import { EventPanel } from '../../components/EventPanel';
import { FlowDots } from '../../components/FlowDots';
import { HexagonTierBadge } from '../../components/HexagonTierBadge';
import { GatheringStation } from '../../components/GatheringStation';
import { AssemblyQueue } from '../../components/AssemblyQueue';
import { useLevel4 } from './Level4Context';
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

// Set to true to show the Gatherer/Engineer/Builder buttons and the "Add station" hexagons.
const SHOW_ORDER_BUTTONS = false;

const AddStationHexagon: React.FC<{ onClick?: () => void; disabled?: boolean; size?: number }> = ({ onClick, disabled = false, size = 50 }) => {
  const height = Math.round(size * 1.15);
  return (
    <div
      onClick={disabled ? undefined : onClick}
      className={`relative select-none flex-none ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer group'}`}
      style={{ width: size, height }}
      title="Add workstation (max 3)"
    >
      <svg
        viewBox="0 0 100 115"
        width={size}
        height={height}
        style={{ display: 'block', overflow: 'visible' }}
      >
        <polygon
          points="50,5 94,30 94,85 50,110 6,85 6,30"
          fill="transparent"
          stroke="#94A3B8"
          strokeWidth="3.5"
          strokeDasharray="7,5"
          strokeLinejoin="round"
          className={disabled ? '' : 'group-hover:stroke-[#0059E8] transition-colors'}
        />
        <path
          d="M 50,38 L 50,72 M 33,55 L 67,55"
          fill="none"
          stroke="#64748B"
          strokeWidth="4.5"
          strokeLinecap="round"
          className={disabled ? '' : 'group-hover:stroke-[#0059E8] transition-colors'}
        />
      </svg>
    </div>
  );
};

// ── Inventory strip ───────────────────────────────────────────────────────────

const InventoryItem: React.FC<{ icon: string; label: string; qty: number }> = ({ icon, label, qty }) => (
  <div className="flex items-center gap-2">
    <img src={icon} width={22} height={22} alt={label} style={{ objectFit: 'contain' }} />
    <span className="text-sm text-[#57606A]">{label}</span>
    <span className="text-sm font-bold font-mono text-[#031040] tabular-nums ml-1">{qty}</span>
  </div>
);

// ── Floor sub-components ──────────────────────────────────────────────────────

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

const actionBtnClass = (enabled: boolean) =>
  `rounded-md font-bold text-xs flex items-center justify-center gap-1 py-1 px-1.5 transition w-full select-none border ${
    enabled
      ? 'bg-white border-[#0059E8] text-[#0059E8] hover:bg-[#EEF4FF] cursor-pointer'
      : 'bg-[#F1F4F9] border-[#CBD5E1] text-[#94A3B8] cursor-not-allowed'
  }`;

// ── Main screen ───────────────────────────────────────────────────────────────

export const Level4Screen: React.FC<LevelScreenProps> = ({ state }) => {
  const {
    running,
    manufacturing_blocked,
    assembly_blocked,
    manufacturing_inputs,
    assembly_inputs,
    inventory,
    events,
    robot_queue,
  } = state;

  const queue = robot_queue ?? [];
  const assemblyActive = state.assembly_active ?? {};

  const level4 = useLevel4();
  const stationSlots = level4?.stationSlots ?? {};
  const maxStations = level4?.maxStations ?? 3;
  const addStation = level4?.addStation ?? (() => Promise.resolve());
  const upgradeStation = level4?.upgradeStation ?? (() => Promise.resolve());
  const isOrderPending = level4?.isOrderPending ?? ((_station: string, _action: 'add' | 'upgrade') => false);

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
                  const slots = stationSlots[id] ?? [{ id: 1, tier: 1 }];

                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-3">
                      {/* Header with Icon and Label */}
                      <div className="flex items-center gap-2">
                        <img src={icon} width={28} height={28} alt={label} style={{ objectFit: 'contain' }} />
                        <span className="text-sm font-semibold text-[#031040]">{label}</span>
                      </div>

                      <GatheringStation tier={slots[0].tier} resourceName={label} />
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
                  const blocked    = id in (manufacturing_blocked ?? {});
                  const inputs     = manufacturing_inputs[id] ?? {};
                  const missingSet = blocked ? new Set(Object.keys(manufacturing_blocked[id] ?? {})) : undefined;
                  const slots      = stationSlots[id] ?? [{ id: 1, tier: 1 }];

                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-3">
                      {/* Header with Icon, Label, and Input chips */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <img src={icon} width={28} height={28} alt={output_type} style={{ objectFit: 'contain' }} />
                        <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                        <InputChips inputs={inputs} iconMap={RESOURCE_ICON} blockedKeys={missingSet} />
                      </div>

                      {/* Stations row (up to 3) + Add button */}
                      <div className="flex items-start justify-start gap-3 flex-wrap">
                        {slots.map((st) => {
                          const isMax = st.tier >= 3;
                          return (
                            <div key={st.id} className="flex flex-col items-center gap-1.5" style={{ width: 80 }}>
                              <HexagonTierBadge
                                tier={st.tier}
                                blocked={blocked}
                                active={running}
                                tooltip="Waiting for resources"
                                size={50}
                              />
                              {isMax || !SHOW_ORDER_BUTTONS ? (
                                <div></div>
                              ) : (
                                <button
                                  onClick={() => upgradeStation(id)}
                                  title="Assign an Engineer to increase production"
                                  disabled={isOrderPending(id, 'upgrade')}
                                  className={actionBtnClass(!isOrderPending(id, 'upgrade'))}
                                >
                                  <svg width="14" height="20" viewBox="0 0 12 17" fill="none" aria-hidden="true"><path d="M6 14V3M3 6l3-3 3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                                  Engineer
                                </button>
                              )}
                            </div>
                          );
                        })}

                        {SHOW_ORDER_BUTTONS && slots.length < maxStations && (
                          <div className="flex flex-col items-center gap-1.5" style={{ width: 68 }}>
                            <AddStationHexagon
                              onClick={() => addStation(id)}
                              disabled={isOrderPending(id, 'add')}
                              size={50}
                            />
                            <span className="text-xs font-semibold leading-tight text-center whitespace-nowrap" style={{ color: '#57606A' }}>
                              Add station
                            </span>
                            <button
                              onClick={() => addStation(id)}
                              title="Assign a Builder to add a new manufacturing station"
                              disabled={isOrderPending(id, 'add')}
                              className={actionBtnClass(!isOrderPending(id, 'add'))}
                            >
                              <svg width="20" height="20" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                              Builder
                            </button>
                          </div>
                        )}
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

        {/* ── Column 3: Worker robot assembly ─────────────────────────────────── */}
        <div className="flex-[3] flex flex-col gap-2 min-w-0">
          {/* The Queen's open orders */}
          <AssemblyQueue queue={queue} />

          {/* Floor */}
          <section>
            <div className="rounded-xl border border-[#E0E8F8] bg-white p-5" style={{ minHeight: 480 }}>
              <h2 className="text-[#2850B8] font-bold text-base mb-4">Worker robot assembly</h2>
              <div className="flex flex-col gap-3">
                {ROBOTS.map(({ id, station_id, label, icon }) => {
                  // Strict FIFO: only the head of the order queue is staged/built, so a station is
                  // "scheduled" only if its robot is next in the queue or already building.
                  const scheduled   = queue[0]?.robot_type === id || !!assemblyActive[station_id];
                  const blocked     = scheduled && station_id in (assembly_blocked ?? {});
                  const disabled    = !scheduled;
                  const inputs      = assembly_inputs[station_id] ?? {};
                  const missingSet  = blocked ? new Set(Object.keys(assembly_blocked[station_id] ?? {})) : undefined;
                  const slots       = stationSlots[station_id] ?? [{ id: 1, tier: 1 }];

                  return (
                    <div key={id} className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col items-start gap-3">
                      {/* Header with Icon, Label, and Input chips */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <img src={icon} width={40} height={40} alt={label} style={{ objectFit: 'contain' }} />
                        <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                        <InputChips inputs={inputs} iconMap={PART_ICON} blockedKeys={missingSet} />
                      </div>

                      {/* Stations row (up to 3) + Add button */}
                      <div className="flex items-start justify-start gap-3 flex-wrap">
                        {slots.map((st) => {
                          const isMax = st.tier >= 3;
                          return (
                            <div key={st.id} className="flex flex-col items-center gap-1.5" style={{ width: 80 }}>
                              <HexagonTierBadge
                                tier={st.tier}
                                blocked={blocked}
                                disabled={disabled}
                                active={running}
                                tooltip="Waiting for parts"
                                size={50}
                              />
                              {isMax || !SHOW_ORDER_BUTTONS ? (
                                <div></div>
                              ) : (
                                <button
                                  onClick={() => upgradeStation(station_id)}
                                  title="Assign an Engineer to increase production"
                                  disabled={isOrderPending(station_id, 'upgrade')}
                                  className={actionBtnClass(!isOrderPending(station_id, 'upgrade'))}
                                >
                                  <svg width="14" height="20" viewBox="0 0 12 17" fill="none" aria-hidden="true"><path d="M6 14V3M3 6l3-3 3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                                  Engineer
                                </button>
                              )}
                            </div>
                          );
                        })}

                        {SHOW_ORDER_BUTTONS && slots.length < maxStations && (
                          <div className="flex flex-col items-center gap-1.5" style={{ width: 68 }}>
                            <AddStationHexagon
                              onClick={() => addStation(station_id)}
                              disabled={isOrderPending(station_id, 'add')}
                              size={50}
                            />
                            <span className="text-xs font-semibold leading-tight text-center whitespace-nowrap" style={{ color: '#57606A' }}>
                              Add station
                            </span>
                            <button
                              onClick={() => addStation(station_id)}
                              title="Assign a Builder to add a new assembly station"
                              disabled={isOrderPending(station_id, 'add')}
                              className={actionBtnClass(!isOrderPending(station_id, 'add'))}
                            >
                              <svg width="20" height="20" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                              Builder
                            </button>
                          </div>
                        )}
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
