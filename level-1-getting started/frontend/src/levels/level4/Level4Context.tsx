import React, { createContext, useContext, useMemo } from 'react';
import type { DashboardState, SimulationConfig } from '../../types';

const FALLBACK_INITIAL_TIERS: Record<string, number> = {
  copper: 2, energy: 3, metals: 1, resin: 2, silicon: 2,
  chassis: 1, electronics: 1,
  actuator: 1, battery: 1,
  engineer: 1, gatherer: 1,
};

const MAX_STATIONS = 3;

// ── Derived helpers from simulation_config (or fallback) ──────────────────────

function initialTiers(cfg: SimulationConfig | null): Record<string, number> {
  if (!cfg) return FALLBACK_INITIAL_TIERS;
  return cfg.station_initial_tiers;
}


// ── Types ─────────────────────────────────────────────────────────────────────

export interface StationSlot {
  id: number;
  tier: number;
}

interface Level4ContextValue {
  stationSlots: Record<string, StationSlot[]>;
  maxStations: number;
  configReady: boolean;
  /** Order a Builder robot to add a station to `key`. */
  addStation: (key: string) => Promise<void>;
  /** Order a Gatherer (gathering station) or Engineer (any other station) to upgrade `key`. */
  upgradeStation: (key: string) => Promise<void>;
  orderRobot: (robotType: RobotType, station: string) => Promise<void>;
  cancelOrder: (orderId: string) => Promise<void>;
  /** True while an order for `station` is waiting for the Queen to place it. */
  isOrderPending: (station: string) => boolean;
}

type RobotType = 'gatherer' | 'engineer' | 'builder';

const GATHERING_STATIONS = new Set(['copper', 'energy', 'metals', 'resin', 'silicon']);

const Level4Context = createContext<Level4ContextValue | null>(null);

export const Level4Provider: React.FC<{ state: DashboardState; children: React.ReactNode }> = ({ state, children }) => {
  const cfg = state.simulation_config;

  // Stations as configured at the start of the run. The Queen's orders do not change them yet:
  // TODO: apply upgrade / add-station effects once QueenState.assign_robot has an effect on the
  // stations (see Phase 3 in next_steps_simulation.md).
  const stationSlots = useMemo<Record<string, StationSlot[]>>(() => {
    const tiers = initialTiers(cfg);
    return Object.fromEntries(
      Object.entries(tiers).map(([stationId, tier]) => [
        stationId,
        [{ id: 1, tier }],
      ])
    );
  }, [cfg]);

  const configReady = cfg !== null;

  const orderRobot = async (robotType: RobotType, station: string) => {
    try {
      const r = await fetch('/api/order-robot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ robot_type: robotType, station }),
      });
      if (!r.ok) console.error('Queen rejected the order:', await r.text());
    } catch (err) {
      console.error('Failed to order robot:', err);
    }
  };

  // The order shows up in the queue when Flink writes it to queens_orders, not here.
  const addStation = (key: string) => orderRobot('builder', key);

  const upgradeStation = (key: string) =>
    orderRobot(GATHERING_STATIONS.has(key) ? 'gatherer' : 'engineer', key);

  const cancelOrder = async (orderId: string) => {
    try {
      const r = await fetch(`/api/orders/${encodeURIComponent(orderId)}`, { method: 'DELETE' });
      if (!r.ok) console.error('Could not cancel the order:', await r.text());
    } catch (err) {
      console.error('Failed to cancel order:', err);
    }
  };

  // TODO: return true while an order for `station` has been sent but has not yet appeared in
  // queens_orders, so the button can be disabled meanwhile.
  const isOrderPending = (_station: string) => false;

  return (
    <Level4Context.Provider
      value={{
        stationSlots,
        maxStations: MAX_STATIONS,
        configReady,
        addStation,
        upgradeStation,
        orderRobot,
        cancelOrder,
        isOrderPending,
      }}
    >
      {children}
    </Level4Context.Provider>
  );
};

export const useLevel4 = () => {
  return useContext(Level4Context);
};
