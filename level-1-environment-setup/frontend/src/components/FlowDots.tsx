import React from 'react';

interface FlowDotsProps {
  running?: boolean;
}

/** Horizontal dotted connector between the three lanes, flowing left to right. */
export const FlowDots: React.FC<FlowDotsProps> = ({ running = true }) => {
  const numDots = 6;
  const cycleSeconds = 1.8;

  return (
    <div
      className="flex items-center justify-center select-none"
      style={{ width: '32px', flexShrink: 0, marginTop: '170px' }}
    >
      <div className="flex gap-1">
        {Array.from({ length: numDots }, (_, i) => {
          const delay = (i * cycleSeconds) / numDots;
          return (
            <span
              key={i}
              className="block rounded-full bg-[#2850B8]"
              style={{
                width: 6,
                height: 6,
                opacity: running ? undefined : 0.25,
                animation: running ? `dotFlowRight ${cycleSeconds}s infinite ease-out` : 'none',
                animationDelay: running ? `${delay.toFixed(3)}s` : undefined,
              }}
            />
          );
        })}
      </div>
    </div>
  );
};
