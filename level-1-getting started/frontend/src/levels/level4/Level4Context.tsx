import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
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
  /**
   * True while an order for this `action` on `station` is active: just sent, waiting in the
   * Queen's queue, or under assembly. The matching button is disabled meanwhile.
   */
  isOrderPending: (station: string, action: OrderAction) => boolean;
}

type RobotType = 'gatherer' | 'engineer' | 'builder';
type OrderAction = 'add' | 'upgrade';

/** A click is remembered this long if the order never shows up in queens_orders. */
const SUBMITTED_TTL_MS = 20000;

const orderKey = (station: string, action: OrderAction) => `${station}:${action}`;

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

  // Orders that are in the Queen's queue or under assembly, by "station:action".
  const activeKeys = useMemo(() => {
    const active = [...(state.robot_queue ?? []), ...(state.orders_in_assembly ?? [])];
    return new Set(active.map((o) => orderKey(o.station, o.action)));
  }, [state.robot_queue, state.orders_in_assembly]);

  // Orders just sent that have not reached queens_orders yet (Flink adds a short delay),
  // so a second click cannot slip in. Value = when it was sent.
  const [submitted, setSubmitted] = useState<Record<string, number>>({});

  const clearSubmitted = (key: string) =>
    setSubmitted((prev) => {
      if (!(key in prev)) return prev;
      const { [key]: _removed, ...rest } = prev;
      return rest;
    });

  // Once the order shows up in the queue the real data takes over; drop the local marker.
  useEffect(() => {
    setSubmitted((prev) => {
      const rest = Object.fromEntries(Object.entries(prev).filter(([k]) => !activeKeys.has(k)));
      return Object.keys(rest).length === Object.keys(prev).length ? prev : rest;
    });
  }, [activeKeys]);

  // Safety net: never leave a button disabled for good if an order is lost.
  useEffect(() => {
    const keys = Object.keys(submitted);
    if (keys.length === 0) return;
    const oldest = Math.min(...keys.map((k) => submitted[k]));
    const timer = setTimeout(() => {
      setSubmitted((prev) =>
        Object.fromEntries(Object.entries(prev).filter(([, at]) => Date.now() - at < SUBMITTED_TTL_MS))
      );
    }, Math.max(0, SUBMITTED_TTL_MS - (Date.now() - oldest)) + 50);
    return () => clearTimeout(timer);
  }, [submitted]);

  const orderRobot = async (robotType: RobotType, station: string) => {
    const action: OrderAction = robotType === 'builder' ? 'add' : 'upgrade';
    const key = orderKey(station, action);
    setSubmitted((prev) => ({ ...prev, [key]: Date.now() }));
    try {
      const r = await fetch('/api/order-robot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ robot_type: robotType, station }),
      });
      if (!r.ok) {
        console.error('Queen rejected the order:', await r.text());
        clearSubmitted(key);
      }
    } catch (err) {
      console.error('Failed to order robot:', err);
      clearSubmitted(key);
    }
  };

  // The order shows up in the queue when Flink writes it to queens_orders, not here.
  const addStation = (key: string) => orderRobot('builder', key);

  const upgradeStation = (key: string) =>
    orderRobot(GATHERING_STATIONS.has(key) ? 'gatherer' : 'engineer', key);

  const isOrderPending = (station: string, action: OrderAction) => {
    const key = orderKey(station, action);
    return activeKeys.has(key) || key in submitted;
  };

  return (
    <Level4Context.Provider
      value={{
        stationSlots,
        maxStations: MAX_STATIONS,
        configReady,
        addStation,
        upgradeStation,
        orderRobot,
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
