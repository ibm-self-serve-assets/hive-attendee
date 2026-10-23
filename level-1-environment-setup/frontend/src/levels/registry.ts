import { Level1Screen } from './level1/Level1Screen';
import { Level1Requirements } from './level1/Level1Requirements';
import { Level2Screen } from './level2/Level2Screen';
import { Level2Requirements } from './level2/Level2Requirements';
import { Level3Screen } from './level3/Level3Screen';
import { Level3Requirements } from './level3/Level3Requirements';
import { Level4Screen } from './level4/Level4Screen';
import { Level4Requirements } from './level4/Level4Requirements';
import type { LevelDefinition } from './types';

/** Add a new level by appending one entry here. The dropdown is built from this list. */
export const LEVELS: LevelDefinition[] = [
  {
    id: 'level-1',
    label: 'Level 1',
    Screen: Level1Screen,
    isUnlocked: (state) => state.event_topics_ready,
    Requirements: Level1Requirements,
  },
  {
    id: 'level-2',
    label: 'Level 2',
    Screen: Level2Screen,
    isUnlocked: (state) => state.hive_job_durations_ready,
    Requirements: Level2Requirements,
    // Ready once Flink has produced at least one duration for the current run.
    isReady: (state) => Object.keys(state.job_durations).length > 0,
  },
  {
    id: 'level-3',
    label: 'Level 3',
    Screen: Level3Screen,
    isUnlocked: (state) => state.hive_inventory_balances_ready,
    Requirements: Level3Requirements,
  },
  {
    id: 'level-4',
    label: 'Level 4',
    Screen: Level4Screen,
    isUnlocked: (state) => state.hive_inventory_balances_ready,
    Requirements: Level4Requirements,
  },
];

export const DEFAULT_LEVEL_ID = LEVELS[0].id;
