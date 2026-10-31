import React, { useState } from 'react';
import { DashboardState, fmtSimTime } from '../types';
import { LEVELS } from '../levels/registry';

interface SidebarProps {
  state: DashboardState;
  isCommandPending: boolean;
  onSendCommand: (command: string, extra?: Record<string, unknown>) => Promise<void>;
  levelId: string;
  onLevelChange: (levelId: string) => void;
  /** False when the level is unlocked but the current run has no data for it yet. */
  isReady?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  state,
  isCommandPending,
  onSendCommand,
  levelId,
  onLevelChange,
  isReady = true,
}) => {
  const [simInfoOpen, setSimInfoOpen] = useState(false);
  const { stream_health, lifecycle_status, running, sim_time_minutes, active_simulation_id, run_id, attendee_id } = state;
  const isLive = stream_health === 'live';
  const isExpired = lifecycle_status === 'expired';
  const isStopped = lifecycle_status === 'stopped';
  const connectionFailed = state.connection_status === 'failed';
  const hasSimulation = Boolean(active_simulation_id) && !connectionFailed;
  const hasState = stream_health !== 'awaiting_events' || hasSimulation;
  const level = LEVELS.find((l) => l.id === levelId) ?? LEVELS[0];
  const isUnlocked = level.isUnlocked ? level.isUnlocked(state) : true;
  // Show sim/restart controls when unlocked; hide sim time until also ready
  const showControls = isUnlocked;
  // Show sim time once the sim is running, even before the level has Flink data
  const showSimTime = isUnlocked && (isReady || state.running);

  return (
    <aside
      className="shrink-0 flex flex-col justify-between border-r border-[#1A2760]"
      style={{ width: '216px', background: '#031040', color: '#fff' }}
    >
      <div className="p-5 space-y-5">

        {/* ── Level selector ── */}
        <section>
          <label htmlFor="level-select" className="block text-md font-bold text-white mb-3">
            Levels
          </label>
          <select
            id="level-select"
            value={levelId}
            onChange={(e) => onLevelChange(e.target.value)}
            className="w-full rounded border border-[#1A2760] bg-[#0A1A55] text-white text-sm font-bold px-3 py-2"
          >
            {LEVELS.map(({ id, label }) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </section>

        <hr className="border-t border-[#2A4896]" />

        {/* ── Simulation controls ── */}
        <section>
          <h2 className="text-md font-bold text-white mb-3">Simulation controls</h2>

          {/* Connection status */}
          <div className="flex items-center gap-2 text-white font-semibold text-sm mb-3">
            <span
              className={`w-4 h-4 rounded-full ${
                connectionFailed
                  ? 'bg-red-500'
                  : stream_health === 'stale'
                    ? 'bg-amber-400'
                    : isLive || hasSimulation
                      ? 'bg-emerald-400'
                      : 'bg-[#4A5A8A]'
              }`}
            />
            <span>
              {connectionFailed
                ? 'Not connected'
                : isLive
                  ? 'Connected'
                  : stream_health === 'stale'
                    ? 'Stale'
                    : hasSimulation
                      ? 'Connected'
                      : 'Connecting'}
            </span>
          </div>

          {showControls && (
            <>
            {isExpired && (
              <div className="mb-3 px-3 py-2 rounded text-xs text-amber-300 border border-amber-800 bg-[#2a1800] leading-snug">
                Simulation complete. Start a new run below.
              </div>
            )}

            {isExpired ? (
              <button
                onClick={() => onSendCommand('restart', { start: true })}
                disabled={isCommandPending}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <img src="/icons/svg/simulation_controls_start.svg" width={14} height={14} alt="Restart" />
                <span>{isCommandPending ? 'Starting…' : 'Restart'}</span>
              </button>
            ) : isStopped ? (
              <button
                onClick={() => onSendCommand('restart', { start: true })}
                disabled={isCommandPending}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <img src="/icons/svg/simulation_controls_start.svg" width={14} height={14} alt="Restart" />
                <span>{isCommandPending ? 'Starting…' : 'Restart'}</span>
              </button>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={() => onSendCommand(running ? 'stop' : 'start')}
                  disabled={isCommandPending || !hasSimulation}
                  className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#2850B8] hover:bg-[#3460C8] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  {running ? (
                    <>
                      <img src="/icons/svg/simulation_controls_pause.svg" width={14} height={14} alt="Stop" />
                      <span>Stop</span>
                    </>
                  ) : (
                    <>
                      <img src="/icons/svg/simulation_controls_start.svg" width={14} height={14} alt="Run" />
                      <span>Start</span>
                    </>
                  )}
                </button>
                {running && (
                  <button
                    onClick={() => onSendCommand('pause')}
                    disabled={isCommandPending}
                    className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded text-sm font-bold bg-[#1A3080] hover:bg-[#243D96] text-white disabled:opacity-40 disabled:cursor-not-allowed transition"
                  >
                    <img src="/icons/svg/simulation_controls_pause.svg" width={14} height={14} alt="Pause" />
                    <span>Pause</span>
                  </button>
                )}
              </div>
            )}
            </>
          )}
        </section>

        {/* ── Simulation time (hidden while locked or not ready) ── */}
        {showSimTime && (
          <section>
            <div className="flex items-center gap-2 text-[#8AA0D0] text-sm font-semibold text-white mb-1">
              <img src="/icons/svg/clock.svg" width={24} height={24} alt="clock" className="opacity-70" />
              <span>Simulation Time</span>
            </div>
            <div className="font-bold font-mono text-white text-xl tabular-nums tracking-tight">
              {hasState ? fmtSimTime(sim_time_minutes) : '--'}
            </div>
          </section>
        )}

        {/* ── Level 4 Orders & Treasury ── */}
        {levelId === 'level-4' && (
          <>
            <hr className="border-t border-[#2A4896]" />

            <section>
              <h2 className="flex items-center gap-2 text-md font-bold text-white mb-3">
                <span>Open Orders</span>
              </h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <img
                      src="/icons/svg/robot_engineer_body.svg"
                      width={40}
                      height={40}
                      alt="Engineer"
                      className="rounded"
                    />
                    <span className="text-sm font-semibold text-white">Engineer</span>
                  </div>
                  <span className="font-bold font-mono text-white text-sm tabular-nums">
                    {state.open_order?.quantity_engineer ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <img
                      src="/icons/svg/robot_gatherer_body.svg"
                      width={40}
                      height={40}
                      alt="Gatherer"
                      className="rounded"
                    />
                    <span className="text-sm font-semibold text-white">Gatherer</span>
                  </div>
                  <span className="font-bold font-mono text-white text-sm tabular-nums">
                    {state.open_order?.quantity_gatherer ?? 0}
                  </span>
                </div>
              </div>
            </section>

            <hr className="border-t border-[#2A4896]" />

            <section>
              <h2 className="text-md font-bold text-white mb-3">Treasury</h2>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <img
                    src="/icons/svg/coin.svg"
                    width={28}
                    height={28}
                    alt="Coins"
                    style={{ objectFit: 'contain' }}
                  />
                  <span className="text-sm font-semibold text-white">Coins</span>
                </div>
                <span className="font-bold font-mono text-white text-sm tabular-nums">
                  {state.treasury_coins}
                </span>
              </div>
            </section>
          </>
        )}

      </div>

      <div className="border-t border-[#2A4896] px-5 py-3 text-white">
        <button
          type="button"
          onClick={() => setSimInfoOpen((prev) => !prev)}
          className="w-full flex items-center justify-between text-left cursor-pointer"
          aria-expanded={simInfoOpen}
        >
          <span className="text-xs font-bold text-white">Simulation Info</span>
          <svg
            width="14"
            height="14"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`text-white transition-transform duration-200 ${simInfoOpen ? 'rotate-180' : ''}`}
            aria-hidden="true"
          >
            <path d="M5 7.5l5 5 5-5" />
          </svg>
        </button>

        {simInfoOpen && (
          <div className="mt-2 space-y-2 text-[11px]">
            {attendee_id && (
              <div>
                <div className="font-bold">Attendee ID</div>
                <div className="font-mono text-[11px] break-all">{attendee_id}</div>
              </div>
            )}
            {active_simulation_id && (
              <div>
                <div className="font-bold">Simulation ID</div>
                <div className="font-mono text-[11px] break-all">{active_simulation_id}</div>
              </div>
            )}
            {run_id && (
              <div>
                <div className="font-bold">Run ID</div>
                <div className="font-mono text-[11px] break-all">{run_id}</div>
              </div>
            )}
          </div>
        )}

        <hr className="border-t border-white my-2" />

        <div className="text-[11px] text-white">
          Closing this app does not pause the hosted simulation.
        </div>
      </div>
    </aside>
  );
};
