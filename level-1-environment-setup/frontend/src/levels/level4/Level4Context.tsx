import React, { createContext, useContext, useState, useEffect } from 'react';
import type { DashboardState } from '../../types';

export const STATION_METADATA: Record<number, { cost_purchase: number; cost_upgrade: number; interval_sim_minutes: number }> = {
  1: { cost_purchase: 100, cost_upgrade: 100, interval_sim_minutes: 10 },
  2: { cost_purchase: 500, cost_upgrade: 500, interval_sim_minutes: 5 },
  3: { cost_purchase: 1000, cost_upgrade: -1, interval_sim_minutes: 3 },
};

export const ADD_STATION_COST = STATION_METADATA[1].cost_purchase;

export const ROBOT_PRICES: Record<string, number> = {
  engineer: 250,
  forager: 250,
};

export const RESOURCE_METADATA: Record<string, { level: number }> = {
  copper:  { level: 2 },
  energy:  { level: 3 },
  metals:  { level: 1 },
  resin:   { level: 2 },
  silicon: { level: 2 },
};

export const MANUFACTURING_METADATA: Record<string, { level: number }> = {
  structural_molding:   { level: 1 },
  electronics_assembly: { level: 1 },
  actuator_fabrication: { level: 1 },
  battery_assembly:     { level: 1 },
};

export const ASSEMBLY_METADATA: Record<string, { level: number }> = {
  worker_assembly:  { level: 1 },
  forager_assembly: { level: 1 },
};

export interface StationSlot {
  id: number;
  level: number;
}

export const INITIAL_STATIONS: Record<string, StationSlot[]> = {
  copper:               [{ id: 1, level: RESOURCE_METADATA.copper.level }],
  energy:               [{ id: 1, level: RESOURCE_METADATA.energy.level }],
  metals:               [{ id: 1, level: RESOURCE_METADATA.metals.level }],
  resin:                [{ id: 1, level: RESOURCE_METADATA.resin.level }],
  silicon:              [{ id: 1, level: RESOURCE_METADATA.silicon.level }],
  structural_molding:   [{ id: 1, level: MANUFACTURING_METADATA.structural_molding.level }],
  electronics_assembly: [{ id: 1, level: MANUFACTURING_METADATA.electronics_assembly.level }],
  actuator_fabrication: [{ id: 1, level: MANUFACTURING_METADATA.actuator_fabrication.level }],
  battery_assembly:     [{ id: 1, level: MANUFACTURING_METADATA.battery_assembly.level }],
  worker_assembly:      [{ id: 1, level: ASSEMBLY_METADATA.worker_assembly.level }],
  forager_assembly:     [{ id: 1, level: ASSEMBLY_METADATA.forager_assembly.level }],
};

export const MAX_STATIONS = 3;

interface Level4ContextValue {
  stationSlots: Record<string, StationSlot[]>;
  spentCoins: number;
  coins: number;
  addStation: (key: string) => void;
  upgradeStation: (key: string, index: number) => void;
}

const Level4Context = createContext<Level4ContextValue | null>(null);

export const Level4Provider: React.FC<{ state: DashboardState; children: React.ReactNode }> = ({ state, children }) => {
  const [stationSlots, setStationSlots] = useState<Record<string, StationSlot[]>>(INITIAL_STATIONS);
  const [spentCoins, setSpentCoins] = useState<number>(0);

  // Reset state on run_id change
  useEffect(() => {
    setStationSlots(INITIAL_STATIONS);
    setSpentCoins(0);
  }, [state.run_id]);

  const earnedCoins =
    (state.inventory.robot?.engineer ?? 0) * (ROBOT_PRICES.engineer ?? 250) +
    (state.inventory.robot?.forager ?? 0) * (ROBOT_PRICES.forager ?? 250);

  const coins = Math.max(0, earnedCoins - spentCoins);

  const addStation = (key: string) => {
    if (coins < ADD_STATION_COST) return;
    setStationSlots((prev) => {
      const current = prev[key] ?? [{ id: 1, level: 1 }];
      if (current.length >= MAX_STATIONS) return prev;
      setSpentCoins((s) => s + ADD_STATION_COST);
      return {
        ...prev,
        [key]: [...current, { id: current.length + 1, level: 1 }],
      };
    });
  };

  const upgradeStation = (key: string, index: number) => {
    const current = stationSlots[key] ?? [{ id: 1, level: 1 }];
    const st = current[index];
    if (!st || st.level >= 3) return;
    const cost = STATION_METADATA[st.level]?.cost_upgrade ?? 100;
    if (cost === -1 || coins < cost) return;

    setSpentCoins((s) => s + cost);
    setStationSlots((prev) => ({
      ...prev,
      [key]: (prev[key] ?? current).map((sItem, i) =>
        i === index ? { ...sItem, level: Math.min(3, sItem.level + 1) } : sItem
      ),
    }));
  };

  return (
    <Level4Context.Provider value={{ stationSlots, spentCoins, coins, addStation, upgradeStation }}>
      {children}
    </Level4Context.Provider>
  );
};

export const useLevel4 = () => {
  return useContext(Level4Context);
};
