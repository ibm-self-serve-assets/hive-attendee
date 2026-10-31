import React from 'react';
import { EventPanel } from '../../components/EventPanel';
import { FlowDots } from '../../components/FlowDots';
import { StationStats } from '../../components/StationStats';
import type { LevelScreenProps } from '../types';

import {
  RESOURCES,
  RESOURCE_ICON,
  STATIONS,
  ROBOTS,
  PART_ICON,
} from '../robots';

// ── Shared sub-components ─────────────────────────────────────────────────────

/**
 * A single input chip: small greyscale icon + "+qty" label.
 * Turns orange when `blocked` is true (input is missing).
 */
const InputChip: React.FC<{
  icon: string;
  qty: number;
  blocked?: boolean;
}> = ({ icon, qty }) => (
  <span
    className="inline-flex items-center gap-0.5"
    style={{ color: '#57606A' }}
  >
    <img
      src={icon}
      width={23}
      height={23}
      alt=""
      style={{
        objectFit: 'contain',
        opacity: 0.85,
      }}
    />
    <span className="text-xs font-semibold tabular-nums" style={{ fontSize: 11 }}>
      +{qty}
    </span>
  </span>
);

/**
 * Row of input chips derived from the `inputs` dict of a *.started event.
 * Uses RESOURCE_ICON for manufacturing stations; PART_ICON for assembly stations.
 */
const InputChips: React.FC<{
  inputs: Record<string, number>;
  iconMap: Record<string, string>;
  blockedKeys?: Set<string>;
}> = ({ inputs, iconMap, blockedKeys }) => (
  <span className="flex items-center flex-wrap gap-1.5">
    {Object.entries(inputs).map(([inputId, qty]) => {
      const icon = iconMap[inputId];
      if (!icon) return null;
      const isBlocked = blockedKeys?.has(inputId) ?? false;
      return (
        <InputChip key={inputId} icon={icon} qty={qty} blocked={isBlocked} />
      );
    })}
  </span>
);

// ── Main screen ───────────────────────────────────────────────────────────────

export const Level2Screen: React.FC<LevelScreenProps> = ({ state }) => {
  const {
    run_generation,
    running,
    gathering_completed,
    manufacturing_completed,
    assembly_completed,
    manufacturing_blocked,
    assembly_blocked,
    manufacturing_inputs,
    assembly_inputs,
    job_durations,
    events,
  } = state;

  // Show a restart prompt when there is an active run but Flink hasn't produced
  // any job durations yet — meaning the user is looking at Level 2 with stale
  // Level 1 data.  Once Flink starts writing to hive_job_durations the prompt
  // disappears automatically.
  const needsRestart = run_generation > 0 && Object.keys(job_durations).length === 0;

  if (needsRestart) {
    const simRunning = state.running;
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center max-w-sm">
          {simRunning ? (
            <>
              <div className="mx-auto mb-4" style={{ width: 48, height: 48 }}>
                {/* Pulsing dot to indicate waiting */}
                <svg viewBox="0 0 48 48" width={48} height={48}>
                  <circle cx="24" cy="24" r="10" fill="#2850B8" opacity="0.2">
                    <animate attributeName="r" values="8;16;8" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.6;0.1;0.6" dur="2s" repeatCount="indefinite" />
                  </circle>
                  <circle cx="24" cy="24" r="6" fill="#2850B8" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-[#031040] mb-2">Waiting for Flink…</h2>
              <p className="text-sm text-[#57606A] leading-relaxed">
                The Simulation is running. Waiting for the first job duration
                from the <code className="font-mono text-[#031040]">hive_job_durations</code> pipeline.
                This can take up to a minute after the first job completes.
              </p>
            </>
          ) : (
            <>
              <img src="/icons/svg/warning.svg" width={48} height={48} alt="" className="mx-auto mb-4 opacity-60" />
              <h2 className="text-xl font-bold text-[#031040] mb-2">New Simulation run required</h2>
              <p className="text-sm text-[#57606A] leading-relaxed">
                Level 2 needs a fresh run so the Flink pipeline can calculate job
                durations from the start. Click <strong>Restart</strong> in the sidebar to begin.
              </p>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="flex items-start gap-[5.33px] min-w-0">

        {/* ── Lane 1: Resource gathering ──────────────────────────────────── */}
        <section className="flex-none" style={{ minWidth: 300 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 604 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Gather resources</h2>
            <div className="grid grid-cols-2 gap-3">
              {RESOURCES.map(({ id, label, icon }) => {
                const count   = gathering_completed[id] ?? 0;
                const blocked = false;
                const dur     = job_durations[id];

                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-3 flex flex-col justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <img src={icon} width={33} height={33} alt={label} />
                      <span className="text-sm font-semibold text-[#031040]">{label}</span>
                    </div>
                    <div className="mt-3">
                      <StationStats
                        count={count}
                        blocked={blocked}
                        durationMins={dur}
                        running={running}
                        tooltip="Waiting for resources"
                        ringSize={95}
                        countScale={0.19}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <EventPanel title="Resource events" events={events?.gathering ?? []} />
        </section>

        <FlowDots running={state.running} />

        {/* ── Lane 2: Parts manufacturing ─────────────────────────────────── */}
        <section className="flex-none" style={{ width: 420 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 604 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Manufacture parts</h2>
            <div className="flex flex-col gap-3">
              {STATIONS.map(({ id, label, icon, output_type }) => {
                const count   = manufacturing_completed[id] ?? 0;
                const blocked = id in manufacturing_blocked;
                const dur     = job_durations[id] ?? job_durations[output_type];
                const inputs  = manufacturing_inputs[id] ?? {};
                // Which input keys are missing when blocked
                const missingSet = blocked
                  ? new Set(Object.keys(manufacturing_blocked[id] ?? {}))
                  : undefined;

                return (
                  <div
                    key={id}
                    className="flex items-center justify-between gap-4 rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] px-4 py-3.5"
                  >
                    {/* Part icon + workstation label with input chips below */}
                    <div className="flex items-center gap-3 min-w-0">
                      <img src={icon} width={60} height={60} alt={output_type} style={{ objectFit: 'contain' }} />
                      <div className="flex flex-col gap-1">
                        <span className="text-sm font-semibold text-[#031040]">{label}</span>
                        <InputChips inputs={inputs} iconMap={RESOURCE_ICON} blockedKeys={missingSet} />
                      </div>
                    </div>
                    <StationStats
                      count={count}
                      blocked={blocked}
                      durationMins={dur}
                      running={running}
                      tooltip="Waiting for resources"
                      ringSize={85}
                      countScale={0.19}
                    />
                  </div>
                );
              })}
            </div>
          </div>
          <EventPanel title="Manufacturing events" events={events?.manufacturing ?? []} />
        </section>

        <FlowDots running={state.running} />

        {/* ── Lane 3: Robot assembly ───────────────────────────────────────── */}
        <section className="flex-none" style={{ width: 420 }}>
          <div
            className="rounded-xl border border-[#E0E8F8] bg-white p-5"
            style={{ minHeight: 604 }}
          >
            <h2 className="text-[#2850B8] font-bold text-base mb-4">Assemble robots</h2>
            <div className="flex flex-col gap-3">
              {ROBOTS.map(({ id, station_id, label, icon }) => {
                const count   = assembly_completed[id] ?? 0;
                const blocked = station_id in assembly_blocked;
                const dur     = job_durations[station_id] ?? job_durations[id];
                const inputs  = assembly_inputs[station_id] ?? {};
                const missingSet = blocked
                  ? new Set(Object.keys(assembly_blocked[station_id] ?? {}))
                  : undefined;

                return (
                  <div
                    key={id}
                    className="rounded-lg border border-[#E8EFF8] bg-[#F8FAFD] p-4"
                  >
                    {/* Robot header: label + input part chips */}
                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                      <span className="text-sm font-semibold text-[#031040] mr-1">{label}</span>
                      <InputChips inputs={inputs} iconMap={PART_ICON} blockedKeys={missingSet} />
                    </div>
                    {/* Robot body: robot icon + count, warning and duration */}
                    <div className="flex items-center justify-between gap-4">
                      <img src={icon} width={80} height={80} alt={label} style={{ objectFit: 'contain' }} />
                      <StationStats
                        count={count}
                        blocked={blocked}
                        durationMins={dur}
                        running={running}
                        tooltip="Waiting for parts"
                        ringSize={90}
                        countScale={0.19}
                      />
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
