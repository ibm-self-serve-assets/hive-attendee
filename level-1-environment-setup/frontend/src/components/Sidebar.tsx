import React from 'react';
import { DashboardState, fmtSimTime } from '../types';
import { LEVELS } from '../levels/registry';
import { useLevel4 } from '../levels/level4/Level4Context';

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
  const { stream_health, lifecycle_status, running, sim_time_minutes, active_simulation_id, run_id, attendee_id } = state;
  const isLive = stream_health === 'live';
  const isExpired = lifecycle_status === 'expired';
  const isStopped = lifecycle_status === 'stopped';
  const hasSimulation = Boolean(active_simulation_id);
  const hasState = stream_health !== 'awaiting_events' || hasSimulation;
  const level = LEVELS.find((l) => l.id === levelId) ?? LEVELS[0];
  const isUnlocked = level.isUnlocked ? level.isUnlocked(state) : true;
  // Show sim/restart controls when unlocked; hide sim time until also ready
  const showControls = isUnlocked;
  // Show sim time once the sim is running, even before the level has Flink data
  const showSimTime = isUnlocked && (isReady || state.running);

  const level4 = useLevel4();
  const coins = level4?.coins ?? 0;

  return (
    <aside
      className="shrink-0 flex flex-col justify-between border-r border-[#1A2760]"
      style={{ width: '216px', background: '#031040', color: '#fff' }}
    >
      <div className="p-5 space-y-5">

        {/* ── Level selector ── */}
        <section>
          <label htmlFor="level-select" className="block text-xs font-bold text-white mb-3">
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
          <h2 className="text-xs font-bold text-white mb-3">Simulation controls</h2>

          {/* Connection status */}
          <div className="flex items-center gap-2 text-white text-sm mb-3">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                stream_health === 'stale' ? 'bg-amber-400' : isLive || hasSimulation ? 'bg-emerald-400' : 'bg-[#4A5A8A]'
              }`}
            />
            <span>
              {isLive ? 'Connected' : stream_health === 'stale' ? 'Stale' : hasSimulation ? 'Connected' : 'Connecting'}
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
            <div className="flex items-center gap-2 text-[#8AA0D0] text-xs mb-1">
              <img src="/icons/svg/clock.svg" width={16} height={16} alt="clock" className="opacity-70" />
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
              <h2 className="text-xs font-bold text-white mb-3">Orders</h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <img
                      src="/icons/svg/order-engineer.svg"
                      width={28}
                      height={28}
                      alt="Engineer"
                      className="rounded"
                    />
                    <span className="text-sm font-semibold text-white">Engineer</span>
                  </div>
                  <span className="font-bold font-mono text-white text-sm tabular-nums">
                    {state.inventory.robot?.engineer ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <img
                      src="/icons/svg/order-forager.svg"
                      width={28}
                      height={28}
                      alt="Forager"
                      className="rounded"
                    />
                    <span className="text-sm font-semibold text-white">Forager</span>
                  </div>
                  <span className="font-bold font-mono text-white text-sm tabular-nums">
                    {state.inventory.robot?.forager ?? 0}
                  </span>
                </div>
              </div>
            </section>

            <hr className="border-t border-[#2A4896]" />

            <section>
              <h2 className="text-xs font-bold text-white mb-3">Treasury</h2>
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
                  {coins}
                </span>
              </div>
            </section>
          </>
        )}

      </div>

      <div className="border-t border-[#2A4896] px-5 py-3 text-[10px] text-white">
        Closing this app does not pause the hosted simulation.
        {(attendee_id || active_simulation_id) && (
          <hr className="border-t border-white my-2" />
        )}
        {attendee_id && (
          <>
            <div className="font-bold">Attendee ID</div>
            <div className="font-mono text-[11px] break-all">{attendee_id}</div>
          </>
        )}
        {active_simulation_id && (
          <>
            <div className={`font-bold ${attendee_id ? 'mt-2' : ''}`}>Simulation ID</div>
            <div className="font-mono text-[11px] break-all">{active_simulation_id}</div>
          </>
        )}
        {run_id && (
          <>
            <div className="font-bold mt-2">Run ID</div>
            <div className="font-mono text-[11px] break-all">{run_id}</div>
          </>
        )}
      </div>
    </aside>
  );
};
