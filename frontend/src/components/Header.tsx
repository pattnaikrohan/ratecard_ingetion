import React from 'react';
import { Ship, LayoutDashboard, ListFilter, CheckSquare, History, Settings, Sparkles } from 'lucide-react';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  masterDataStatus: any;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, setActiveTab, masterDataStatus }) => {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'queue', label: 'Processing Queue', icon: ListFilter },
    { id: 'review', label: 'Review Grid', icon: CheckSquare },
    { id: 'history', label: 'History', icon: History },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <header className="bg-slate-900 border-b border-slate-800 text-white sticky top-0 z-50 shadow-xl select-none">
      <div className="w-full px-6 lg:px-10 flex items-center justify-between h-14">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 via-indigo-600 to-purple-600 flex items-center justify-center shadow-md shadow-indigo-500/20">
            <Ship className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-black text-white tracking-tight flex items-center gap-1.5 leading-tight">
              Freightify Rate Ingest
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            </h1>
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider leading-tight">Enterprise v3.0</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex items-center gap-1.5 h-full">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 h-full px-4 text-xs font-bold transition-all relative border-b-2 ${
                  isActive
                    ? 'border-cyan-400 text-white bg-slate-800/60'
                    : 'border-transparent text-slate-300 hover:text-white hover:bg-slate-800/30'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Status Indicator */}
        <div className="hidden lg:flex items-center gap-3 text-xs">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/80 text-slate-300 font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400" />
            <span className="font-extrabold text-emerald-400">Engine Active</span>
          </div>
          <div className="px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/80 text-slate-300 font-mono text-[11px]">
            <span className="font-black text-cyan-300">{masterDataStatus?.ports_count?.toLocaleString() || '13,670'}</span> ports
          </div>
          <div className="px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/80 text-slate-300 font-mono text-[11px]">
            <span className="font-black text-purple-300">{masterDataStatus?.carriers_count || '164'}</span> carriers
          </div>
        </div>
      </div>
    </header>
  );
};
