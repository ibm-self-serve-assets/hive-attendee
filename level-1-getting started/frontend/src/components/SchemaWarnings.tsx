import React from 'react';
import type { ConnectionIssue } from '../types';

interface SchemaWarningsProps {
  warnings: ConnectionIssue[];
}

/**
 * Shown above the level screen when the schemas in the attendee's Schema Registry do not match
 * what the Simulation server publishes. It only warns: the attendee fixes Confluent themselves
 * by running register_schemas.sh, and the warning clears on its own.
 */
export const SchemaWarnings: React.FC<SchemaWarningsProps> = ({ warnings }) => {
  return (
    <div className="border-b border-amber-200 bg-amber-50 px-6 py-3" role="alert">
      <ul className="space-y-2">
        {warnings.map((w) => (
          <li key={w.code}>
            <div className="text-[11px] font-bold uppercase tracking-wide text-amber-800">Confluent Cloud</div>
            <div className="text-sm text-[#031040]">{w.title}</div>
            {w.message && <p className="text-sm text-[#3A4A7A] leading-snug">{w.message}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
};
