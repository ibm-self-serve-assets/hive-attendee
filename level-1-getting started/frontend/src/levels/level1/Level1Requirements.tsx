import React from 'react';
import type { LevelScreenProps } from '../types';

/** Shown in the main area instead of the Level 1 screen until every event topic exists in Confluent. */
export const Level1Requirements: React.FC<LevelScreenProps> = ({ state }) => {
  const missing = state.event_topics_missing;
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-6">
      <img src="/icons/svg/lock.svg" width={96} height={96} alt="Locked" />
      <h2 className="mt-3 text-2xl font-bold text-[#031040]">Level 1 is locked</h2>
      <p className="mt-2 max-w-sm text-lg text-[#3A4A7A] leading-snug">
        {missing.length > 0
          ? 'These topics are not yet present in Confluent:'
          : 'The Hive event topics could not be verified in Confluent.'}
      </p>
      {missing.length > 0 && (
        <ul className="mt-2 font-mono text-sm text-[#031040] leading-snug">
          {missing.map((topic) => (
            <li key={topic}>{topic}</li>
          ))}
        </ul>
      )}
      <p className="mt-3 max-w-sm text-sm text-[#57606A] leading-snug">
        Complete Level 1 to create these topics.
      </p>
    </div>
  );
};
