import React from 'react';
import { Anchor, BarChart3, UploadCloud, ListFilter, CheckSquare, History, Settings, Sparkles } from 'lucide-react';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  masterDataStatus: any;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, setActiveTab, masterDataStatus }) => {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
    { id: 'ingest', label: 'Rate Ingestion', icon: UploadCloud },
    { id: 'queue', label: 'Queue', icon: ListFilter },
    { id: 'review', label: 'Review Grid', icon: CheckSquare },
    { id: 'history', label: 'History', icon: History },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <header className="bg-white border-b border-slate-200/90 text-slate-900 sticky top-0 z-50 shadow-2xs select-none">
      <div className="w-full px-6 lg:px-8 flex items-center justify-between h-16">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-md shadow-indigo-600/20">
            <Anchor className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-black text-slate-900 tracking-tight flex items-center gap-1.5 leading-tight">
              RateBridge
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            </h1>
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider leading-tight">Autonomous Rate Intelligence</p>
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
                    ? 'border-indigo-600 text-indigo-700 bg-indigo-50/50'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Status Indicator */}
        <div className="hidden lg:flex items-center gap-3 text-xs">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-sm shadow-emerald-500" />
            <span className="font-extrabold text-emerald-700">Engine Active</span>
          </div>
          <div className="px-3 py-1 rounded-full bg-slate-50 border border-slate-200 text-slate-600 font-mono text-[11px]">
            <span className="font-black text-indigo-600">{masterDataStatus?.ports_count?.toLocaleString() || '13,670'}</span> ports
          </div>
          <div className="px-3 py-1 rounded-full bg-slate-50 border border-slate-200 text-slate-600 font-mono text-[11px]">
            <span className="font-black text-purple-600">{masterDataStatus?.carriers_count || '164'}</span> carriers
          </div>
        </div>
      </div>
    </header>
  );
};
