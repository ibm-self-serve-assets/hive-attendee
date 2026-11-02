import React, { createContext, useContext, useState, useEffect, useMemo } from 'react';
import type { DashboardState, SimulationConfig } from '../../types';

// ── Fallback values used only while simulation_config has not yet arrived ──────
// These keep the UI non-broken before the first simulation.initialized event.
const FALLBACK_TIER_COSTS: Record<number, { cost_purchase: number; cost_upgrade: number; interval_sim_minutes: number }> = {
  1: { cost_purchase: 1000, cost_upgrade: 250,  interval_sim_minutes: 10 },
  2: { cost_purchase: 0,    cost_upgrade: 1000, interval_sim_minutes: 5  },
  3: { cost_purchase: 0,    cost_upgrade: -1,   interval_sim_minutes: 3  },
};

const FALLBACK_INITIAL_TIERS: Record<string, number> = {
  copper: 2, energy: 3, metals: 1, resin: 2, silicon: 2,
  chassis: 1, electronics: 1,
  actuator: 1, battery: 1,
  engineer: 1, gatherer: 1,
};

const FALLBACK_MAX_SLOTS = 3;
const FALLBACK_ADD_COST = 1000;

// ── Derived helpers from simulation_config (or fallback) ──────────────────────

function tierCostMap(cfg: SimulationConfig | null): Record<number, { cost_purchase: number; cost_upgrade: number; interval_sim_minutes: number }> {
  if (!cfg) return FALLBACK_TIER_COSTS;
  return Object.fromEntries(
    cfg.workstation_tiers.map((t) => [
      t.tier,
      { cost_purchase: t.cost_purchase, cost_upgrade: t.cost_upgrade, interval_sim_minutes: t.interval_sim_minutes },
    ])
  );
}

function initialTiers(cfg: SimulationConfig | null): Record<string, number> {
  if (!cfg) return FALLBACK_INITIAL_TIERS;
  return cfg.station_initial_tiers;
}

function maxSlots(cfg: SimulationConfig | null): number {
  return cfg?.max_station_slots ?? FALLBACK_MAX_SLOTS;
}

function addStationCost(cfg: SimulationConfig | null): number {
  if (!cfg) return FALLBACK_ADD_COST;
  const tier1 = cfg.workstation_tiers.find((t) => t.tier === 1);
  return tier1?.cost_purchase ?? FALLBACK_ADD_COST;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface StationSlot {
  id: number;
  tier: number;
}

interface Level4ContextValue {
  stationSlots: Record<string, StationSlot[]>;
  addStationCost: number;
  maxStations: number;
  tierCosts: Record<number, { cost_purchase: number; cost_upgrade: number; interval_sim_minutes: number }>;
  configReady: boolean;
  addStation: (key: string) => void;
  upgradeStation: (key: string, index: number) => void;
  addToQueue: (robotType: string) => Promise<void>;
  removeFromQueue: (index: number) => Promise<void>;
}

const Level4Context = createContext<Level4ContextValue | null>(null);

export const Level4Provider: React.FC<{ state: DashboardState; children: React.ReactNode }> = ({ state, children }) => {
  const cfg = state.simulation_config;

  // Build initial station slots from config (or fallback) — memoised on cfg identity.
  const initialStationSlots = useMemo<Record<string, StationSlot[]>>(() => {
    const tiers = initialTiers(cfg);
    return Object.fromEntries(
      Object.entries(tiers).map(([stationId, tier]) => [
        stationId,
        [{ id: 1, tier }],
      ])
    );
  }, [cfg]);

  const [stationSlots, setStationSlots] = useState<Record<string, StationSlot[]>>(initialStationSlots);

  // Reset on new run_id or when config first arrives
  useEffect(() => {
    setStationSlots(initialStationSlots);
  }, [state.run_id, initialStationSlots]);

  const costMap = tierCostMap(cfg);
  const addCost = addStationCost(cfg);
  const maxSlotsCount = maxSlots(cfg);
  const configReady = cfg !== null;

  const addStation = (key: string) => {
    setStationSlots((prev) => {
      const current = prev[key] ?? [{ id: 1, tier: 1 }];
      if (current.length >= maxSlotsCount) return prev;
      return {
        ...prev,
        [key]: [...current, { id: current.length + 1, tier: 1 }],
      };
    });
  };

  const upgradeStation = (key: string, index: number) => {
    const current = stationSlots[key] ?? [{ id: 1, tier: 1 }];
    const st = current[index];
    if (!st || st.tier >= 3) return;
    const cost = costMap[st.tier]?.cost_upgrade ?? 250;
    if (cost === -1) return;

    setStationSlots((prev) => ({
      ...prev,
      [key]: (prev[key] ?? current).map((sItem, i) =>
        i === index ? { ...sItem, tier: Math.min(3, sItem.tier + 1) } : sItem
      ),
    }));
  };

  const addToQueue = async (robotType: string) => {
    try {
      await fetch('/api/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ robot_type: robotType }),
      });
    } catch (err) {
      console.error('Failed to add robot to queue:', err);
    }
  };

  const removeFromQueue = async (index: number) => {
    try {
      await fetch(`/api/queue/${index}`, {
        method: 'DELETE',
      });
    } catch (err) {
      console.error('Failed to remove robot from queue:', err);
    }
  };

  return (
    <Level4Context.Provider
      value={{
        stationSlots,
        addStationCost: addCost,
        maxStations: maxSlotsCount,
        tierCosts: costMap,
        configReady,
        addStation,
        upgradeStation,
        addToQueue,
        removeFromQueue,
      }}
    >
      {children}
    </Level4Context.Provider>
  );
};

export const useLevel4 = () => {
  return useContext(Level4Context);
};
