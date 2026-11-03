import React from 'react';
import type { ConnectionIssue } from '../types';

const SOURCE_LABEL: Record<ConnectionIssue['source'], string> = {
  config: 'Your settings',
  simulation_server: 'Simulation server',
  confluent: 'Confluent Cloud',
};

interface ConnectionIssuesProps {
  issues: ConnectionIssue[];
}

/**
 * Shown in the main area instead of the level screen when the backend could not connect
 * the dashboard to the Simulation server or Confluent. Each issue says what went wrong.
 * The backend only reads .env at startup, so after editing it the backend must be restarted.
 */
export const ConnectionIssues: React.FC<ConnectionIssuesProps> = ({ issues }) => {
  return (
    <div className="h-full overflow-auto px-6 py-8" role="alert">
      <div className="mx-auto max-w-2xl">
        <ol className="space-y-4">
          {issues.map((issue) => (
            <li key={issue.code} className="rounded-xl border border-red-200 bg-white p-5">
              <div className="text-[11px] font-bold uppercase tracking-wide text-red-700">
                {SOURCE_LABEL[issue.source] ?? issue.source}
              </div>
              <h3 className="mt-1 text-base font-normal text-[#031040]">{issue.title}</h3>
              {issue.message && <p className="mt-2 text-sm text-[#3A4A7A] leading-snug">{issue.message}</p>}

              {issue.detail && (
                <details className="mt-3">
                  <summary className="cursor-pointer text-xs text-[#57606A]">Technical detail</summary>
                  <pre className="mt-1 whitespace-pre-wrap break-words text-xs font-mono text-[#57606A]">{issue.detail}</pre>
                </details>
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
};
