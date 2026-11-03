import type React from 'react';
import type { DashboardState } from '../types';

/** Props every level's main screen receives. Keep this contract stable. */
export interface LevelScreenProps {
  state: DashboardState;
}

export interface LevelDefinition {
  /** Stable id, e.g. "level-1". */
  id: string;
  /** Label shown in the Levels dropdown. */
  label: string;
  /** The level's main screen; owns the whole content area. */
  Screen: React.FC<LevelScreenProps>;
  /**
   * Optional gate. While `isUnlocked(state)` is false the main area shows `Requirements`
   * instead of `Screen`, and the sidebar hides the Simulation controls and time.
   * Omit for ungated levels.
   */
  isUnlocked?: (state: DashboardState) => boolean;
  Requirements?: React.FC<LevelScreenProps>;
  /**
   * Optional readiness check. The level is unlocked (topic exists) but the current
   * sim run does not yet have data for it. While `isReady(state)` is false the sidebar
   * hides Simulation controls and sim time (same as locked), but the main area shows
   * the Screen — which is responsible for rendering its own "restart required" prompt.
   * Omit when no per-run readiness check is needed.
   */
  isReady?: (state: DashboardState) => boolean;
}
