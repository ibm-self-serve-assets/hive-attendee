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
  structural_molding: 1, electronics_assembly: 1,
  actuator_fabrication: 1, battery_assembly: 1,
  worker_assembly: 1, gatherer_assembly: 1,
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
  spentCoins: number;
  coins: number;
  addStationCost: number;
  maxStations: number;
  tierCosts: Record<number, { cost_purchase: number; cost_upgrade: number; interval_sim_minutes: number }>;
  configReady: boolean;
  addStation: (key: string) => void;
  upgradeStation: (key: string, index: number) => void;
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
  const [spentCoins, setSpentCoins] = useState<number>(0);

  // Reset on new run_id or when config first arrives
  useEffect(() => {
    setStationSlots(initialStationSlots);
    setSpentCoins(0);
  }, [state.run_id, initialStationSlots]);

  // Coins: authoritative sum from order.fulfilled events minus locally spent coins
  const coins = Math.max(0, state.treasury_coins - spentCoins);

  const costMap = tierCostMap(cfg);
  const addCost = addStationCost(cfg);
  const maxSlotsCount = maxSlots(cfg);
  const configReady = cfg !== null;

  const addStation = (key: string) => {
    if (coins < addCost) return;
    setStationSlots((prev) => {
      const current = prev[key] ?? [{ id: 1, tier: 1 }];
      if (current.length >= maxSlotsCount) return prev;
      setSpentCoins((s) => s + addCost);
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
    if (cost === -1 || coins < cost) return;

    setSpentCoins((s) => s + cost);
    setStationSlots((prev) => ({
      ...prev,
      [key]: (prev[key] ?? current).map((sItem, i) =>
        i === index ? { ...sItem, tier: Math.min(3, sItem.tier + 1) } : sItem
      ),
    }));
  };

  return (
    <Level4Context.Provider
      value={{
        stationSlots,
        spentCoins,
        coins,
        addStationCost: addCost,
        maxStations: maxSlotsCount,
        tierCosts: costMap,
        configReady,
        addStation,
        upgradeStation,
      }}
    >
      {children}
    </Level4Context.Provider>
  );
};

export const useLevel4 = () => {
  return useContext(Level4Context);
};
