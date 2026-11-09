import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { DashboardState, SimulationConfig } from '../../types';

const FALLBACK_INITIAL_TIERS: Record<string, number> = {
  copper: 2, energy: 3, metals: 1, resin: 2, silicon: 2,
  chassis: 1, electronics: 1,
  actuator: 1, battery: 1,
  engineer: 1, gatherer: 1,
};

// A workstation type has up to 4 workstations, each with its own tier (1 to 3).
const MAX_WORKSTATIONS = 4;
const MAX_TIER = 3;

// ── Derived helpers from simulation_config (or fallback) ──────────────────────

function initialTiers(cfg: SimulationConfig | null): Record<string, number> {
  if (!cfg) return FALLBACK_INITIAL_TIERS;
  return cfg.workstation_initial_tiers;
}


// ── Types ─────────────────────────────────────────────────────────────────────

export interface StationSlot {
  workstation_id: number;
  tier: number;
}

interface Level4ContextValue {
  stationSlots: Record<string, StationSlot[]>;
  maxStations: number;
  configReady: boolean;
  /** Order a Builder robot to add a workstation to the type `workstationType`. */
  addStation: (workstationType: string) => Promise<void>;
  /** Order a Gatherer (gathering) or Engineer (any other type) to upgrade one workstation. */
  upgradeStation: (workstationType: string, workstationId: number) => Promise<void>;
  orderRobot: (robotType: RobotType, workstationType: string, workstationId?: number) => Promise<void>;
  /**
   * Why an order cannot be sent right now, in plain words, or null when it can.
   * An upgrade is per workstation (pass its `workstationId`); an add is per type.
   * The matching button is disabled, with this text as its tooltip.
   */
  orderBlockedReason: (workstationType: string, action: OrderAction, workstationId?: number) => string | null;
}

type RobotType = 'gatherer' | 'engineer' | 'builder';
type OrderAction = 'add' | 'upgrade';

/** A click is remembered this long if the order never shows up in queens_orders. */
const SUBMITTED_TTL_MS = 20000;

/** `<type>:<id>:upgrade` for one workstation, `<type>:add` for a Builder (per type). */
const orderKey = (workstationType: string, action: OrderAction, workstationId?: number | null) =>
  action === 'add' ? `${workstationType}:add` : `${workstationType}:${workstationId}:upgrade`;

const GATHERING_STATIONS = new Set(['copper', 'energy', 'metals', 'resin', 'silicon']);

const Level4Context = createContext<Level4ContextValue | null>(null);

export const Level4Provider: React.FC<{ state: DashboardState; children: React.ReactNode }> = ({ state, children }) => {
  const cfg = state.simulation_config;

  // Use the live workstations from the backend (built from the *.state events).
  // Falls back to initial tiers from simulation_config when the backend has not yet sent slot data.
  const stationSlots = useMemo<Record<string, StationSlot[]>>(() => {
    if (state.workstations && Object.keys(state.workstations).length > 0) {
      return state.workstations;
    }
    // Fallback: workstation 1 of each type at its initial tier.
    const tiers = initialTiers(cfg);
    return Object.fromEntries(
      Object.entries(tiers).map(([workstationType, tier]) => [
        workstationType,
        [{ workstation_id: 1, tier }],
      ])
    );
  }, [state.workstations, cfg]);

  const configReady = cfg !== null;

  // Orders that are in the Queen's queue or under assembly, by order key.
  const activeKeys = useMemo(() => {
    const active = [...(state.robot_queue ?? []), ...(state.orders_in_assembly ?? [])];
    return new Set(active.map((o) => orderKey(o.workstation_type, o.action, o.workstation_id)));
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

  const orderRobot = async (robotType: RobotType, workstationType: string, workstationId?: number) => {
    const action: OrderAction = robotType === 'builder' ? 'add' : 'upgrade';
    const key = orderKey(workstationType, action, workstationId);
    setSubmitted((prev) => ({ ...prev, [key]: Date.now() }));
    try {
      const r = await fetch('/api/order-worker-beee', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          robot_type: robotType,
          workstation_type: workstationType,
          ...(action === 'upgrade' ? { workstation_id: workstationId } : {}),
        }),
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
  const addStation = (workstationType: string) => orderRobot('builder', workstationType);

  const upgradeStation = (workstationType: string, workstationId: number) =>
    orderRobot(GATHERING_STATIONS.has(workstationType) ? 'gatherer' : 'engineer', workstationType, workstationId);

  // One order per workstation (upgrade) or per type (add) at a time. This also keeps the
  // pending orders from passing tier 3 (E5) or 4 workstations (E6), and stops a double click (E7).
  const isOrderPending = (workstationType: string, action: OrderAction, workstationId?: number) => {
    const key = orderKey(workstationType, action, workstationId);
    return activeKeys.has(key) || key in submitted;
  };

  const orderBlockedReason = (workstationType: string, action: OrderAction, workstationId?: number): string | null => {
    if (state.connection_status !== 'connected') return 'Not connected to the Simulation server';
    if (state.lifecycle_status === 'stopped') return 'The Simulation is stopped';
    if (state.lifecycle_status === 'expired') return 'The Simulation has expired';

    const slots = stationSlots[workstationType] ?? [];
    if (action === 'add') {
      if (slots.length >= MAX_WORKSTATIONS) return `Already ${MAX_WORKSTATIONS} workstations`;
    } else {
      const slot = slots.find((s) => s.workstation_id === workstationId);
      if (!slot) return 'This workstation does not exist yet';
      if (slot.tier >= MAX_TIER) return `Already at the highest tier (${MAX_TIER})`;
    }
    if (isOrderPending(workstationType, action, workstationId)) return 'An order for this is already waiting';
    return null;
  };

  return (
    <Level4Context.Provider
      value={{
        stationSlots,
        maxStations: MAX_WORKSTATIONS,
        configReady,
        addStation,
        upgradeStation,
        orderRobot,
        orderBlockedReason,
      }}
    >
      {children}
    </Level4Context.Provider>
  );
};

export const useLevel4 = () => {
  return useContext(Level4Context);
};
