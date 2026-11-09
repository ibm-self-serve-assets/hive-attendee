import React from 'react';

export type TabId = 'robotics' | 'queen' | 'assets' | 'colony';

export interface Tab {
  id: TabId;
  label: string;
}

export const TABS: Tab[] = [
  { id: 'robotics', label: 'Robotics' },
  { id: 'queen', label: 'Queen' },
  { id: 'assets', label: 'Assets' },
  { id: 'colony', label: 'Colony' },
];

interface HeaderProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, onTabChange }) => (
  <header
    className="shrink-0 flex items-stretch border-b border-[#1A2760]"
    style={{ height: '52px', background: '#031040', color: '#fff' }}
  >
    {/* Left section above sidebar */}
    <div className="w-[216px] shrink-0 flex items-center px-5 border-r border-[#1A2760]">
      <span className="text-lg font-bold tracking-tight text-white">Hive Simulation</span>
    </div>

    {/* Middle-right section above main content */}
    <div className="flex-1 flex items-stretch px-6">
      <nav className="flex items-stretch gap-8 h-full" aria-label="Main Navigation">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={`relative flex items-center justify-center text-lg font-bold tracking-tight transition-colors focus:outline-none ${
                isActive ? 'text-white' : 'text-[#A8BEE5] hover:text-white'
              }`}
            >
              <span className="pb-1">{tab.label}</span>
              {isActive && (
                <span
                  className="absolute bottom-0 left-0 right-0 h-[3px] bg-[#E5A825] rounded-t-sm"
                  aria-hidden="true"
                />
              )}
            </button>
          );
        })}
      </nav>
    </div>
  </header>
);
