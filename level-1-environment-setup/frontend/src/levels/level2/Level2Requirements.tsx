import React from 'react';

/** Shown in the main area instead of the Level 2 screen until Level 2 is unlocked. */
export const Level2Requirements: React.FC = () => (
  <div className="h-full flex flex-col items-center justify-center text-center px-6">
    <img src="/icons/svg/lock.svg" width={96} height={96} alt="Locked" />
    <h2 className="mt-3 text-2xl font-bold text-[#031040]">Level 2 is locked</h2>
    <p className="mt-2 max-w-xs text-lg text-[#3A4A7A] leading-snug">
      The <code className="font-mono text-[#031040]">hive_job_durations</code> topic is not yet
      present in Confluent.
    </p>
  </div>
);
