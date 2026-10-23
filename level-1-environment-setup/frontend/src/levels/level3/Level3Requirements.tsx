import React from 'react';

/** Shown in the main area instead of the Level 3 screen until Level 3 is unlocked. */
export const Level3Requirements: React.FC = () => (
  <div className="h-full flex flex-col items-center justify-center text-center px-6">
    <img src="/icons/svg/lock.svg" width={96} height={96} alt="Locked" />
    <h2 className="mt-3 text-2xl font-bold text-[#031040]">Level 3 is locked</h2>
    <p className="mt-2 max-w-xs text-lg text-[#3A4A7A] leading-snug">
      The <code className="font-mono text-[#031040]">hive_inventory_balances</code> topic is not
      yet present in Confluent.
    </p>
    <p className="mt-2 max-w-xs text-sm text-[#57606A] leading-snug">
      Complete the Flink inventory setup in{' '}
      <code className="font-mono">level-3-hive-inventory/</code> to unlock this view.
    </p>
  </div>
);
