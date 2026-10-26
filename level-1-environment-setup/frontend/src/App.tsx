import React, { useEffect, useState } from 'react';
import { ConnectionIssues } from './components/ConnectionIssues';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { DEFAULT_LEVEL_ID, LEVELS } from './levels/registry';
import { Level4Provider } from './levels/level4/Level4Context';
import { DashboardState, EMPTY_STATE } from './types';

/** Read the current hash and return the matching level id, or the default. */
function levelIdFromHash(): string {
  const hash = window.location.hash.replace('#', '');
  return LEVELS.find((l) => l.id === hash)?.id ?? DEFAULT_LEVEL_ID;
}

export const App: React.FC = () => {
  const [state, setState] = useState<DashboardState>(EMPTY_STATE);
  const [levelId, setLevelId] = useState(levelIdFromHash);
  const level = LEVELS.find((l) => l.id === levelId) ?? LEVELS[0];
  const { Screen, Requirements } = level;
  // A failed connection is the real reason nothing works, so it takes over the main area
  // (otherwise the attendee would see "Level 1 is locked" and look in the wrong place).
  const connectionFailed = state.connection_status === 'failed' && state.connection_issues.length > 0;
  const isUnlocked = level.isUnlocked ? level.isUnlocked(state) : true;
  const isReady = isUnlocked && (level.isReady ? level.isReady(state) : true);
  const [isCommandPending, setIsCommandPending] = useState(false);

  // Keep hash in sync when levelId changes programmatically (dropdown)
  const handleLevelChange = (id: string) => {
    window.location.hash = id;
    setLevelId(id);
  };

  // Sync levelId if the user navigates with browser back/forward buttons
  useEffect(() => {
    const onHashChange = () => setLevelId(levelIdFromHash());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // SSE stream
  useEffect(() => {
    const es = new EventSource('/api/stream');

    es.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data) as { type: string; state: DashboardState };
        if (msg.state) {
          setState(msg.state);
        }
      } catch (e) {
        console.error('SSE parse error', e);
      }
    };

    es.onerror = () => {
      setState((prev) => ({ ...prev, stream_health: 'stale' }));
    };

    return () => es.close();
  }, []);

  const handleSendCommand = async (command: string, extra?: Record<string, unknown>) => {
    setIsCommandPending(true);
    try {
      const res = await fetch('/api/controls', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          command,
          ...extra,
        }),
      });

      if (res.ok) {
        try {
          const data = await res.json();
          if (data && data.lifecycle_status) {
            setState((prev) => ({
              ...prev,
              lifecycle_status: data.lifecycle_status,
              running: data.lifecycle_status === 'running',
            }));
          }
        } catch {
          // ignore
        }
      } else {
        let msg = 'Error';
        try {
          const err = await res.json();
          const detail = err?.detail;
          if (typeof detail === 'object' && detail !== null) {
            msg = detail.message || detail.error_code || JSON.stringify(detail);
          } else if (typeof detail === 'string') {
            msg = detail;
          } else {
            msg = err?.message || JSON.stringify(err);
          }
        } catch {
          msg = (await res.text()) || `HTTP ${res.status}`;
        }
        alert(`Command rejected (${res.status}): ${msg}`);
      }
    } catch (e: unknown) {
      const err = e as Error;
      alert(`Command network failure: ${err.message}`);
    } finally {
      setIsCommandPending(false);
    }
  };

  return (
    <Level4Provider state={state}>
      <div className="h-screen flex flex-col overflow-hidden" style={{ background: '#F4F7FC' }}>
        <Header />

        <div className="flex-1 min-h-0 flex overflow-hidden">
          <Sidebar
            state={state}
            isCommandPending={isCommandPending}
            onSendCommand={handleSendCommand}
            levelId={levelId}
            onLevelChange={handleLevelChange}
            isReady={isReady}
          />
          <main className="flex-1 min-h-0 overflow-auto">
            {connectionFailed ? (
              <ConnectionIssues issues={state.connection_issues} />
            ) : isUnlocked ? (
              <Screen state={state} />
            ) : Requirements ? (
              <Requirements state={state} />
            ) : null}
          </main>
        </div>
      </div>
    </Level4Provider>
  );
};

export default App;
