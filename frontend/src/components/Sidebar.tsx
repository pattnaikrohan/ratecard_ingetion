import React from 'react';
import { Ship, LayoutDashboard, ListFilter, CheckSquare, History, Settings, Sparkles, Database } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  masterDataStatus: any;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, masterDataStatus }) => {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'queue', label: 'Processing Queue', icon: ListFilter },
    { id: 'review', label: 'Review Grid', icon: CheckSquare },
    { id: 'history', label: 'History', icon: History },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 shrink-0 h-screen bg-[#090d16] border-r border-slate-800/80 text-white flex flex-col justify-between select-none z-40 shadow-2xl relative overflow-hidden">
      {/* Background Subtle Mesh */}
      <div className="absolute top-0 left-0 w-full h-40 bg-gradient-to-b from-indigo-600/10 to-transparent pointer-events-none" />

      {/* ── TOP: Brand & Logo ── */}
      <div className="relative z-10">
        <div className="p-5 border-b border-slate-800/80 flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-500 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 shrink-0 border border-indigo-400/30">
            <Ship className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-black text-white tracking-tight truncate flex items-center gap-1.5">
              Freightify Ingest
              <Sparkles className="w-3.5 h-3.5 text-cyan-400 shrink-0 animate-pulse" />
            </h1>
            <p className="text-[10px] text-slate-400 font-extrabold uppercase tracking-widest">Enterprise v3.0</p>
          </div>
        </div>

        {/* ── NAVIGATION MENU ── */}
        <nav className="p-3 space-y-1.5 mt-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-2xl text-xs font-black transition-all duration-300 relative group ${
                  isActive
                    ? 'bg-gradient-to-r from-indigo-600 via-indigo-600 to-purple-600 text-white shadow-xl shadow-indigo-600/35 scale-[1.02] border border-indigo-400/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <Icon className={`w-4 h-4 transition-transform group-hover:scale-110 ${isActive ? 'text-cyan-300' : 'text-slate-400'}`} />
                <span className="truncate">{tab.label}</span>
                {isActive && (
                  <span className="w-2 h-2 rounded-full bg-cyan-400 ml-auto shrink-0 shadow-md shadow-cyan-400 animate-pulse" />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* ── BOTTOM: Master Data Engine Widget ── */}
      <div className="p-4 m-3 rounded-2xl bg-slate-900/90 border border-slate-800/90 space-y-3 relative z-10 shadow-xl">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-cyan-400" /> Master Data Engine
          </span>
          <span className="flex items-center gap-1 text-[10px] font-mono font-black text-emerald-400 bg-emerald-950/80 border border-emerald-800/80 px-2 py-0.5 rounded-full shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Active
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-center pt-1 border-t border-slate-800/80">
          <div className="p-2 rounded-xl bg-slate-950/80 border border-slate-800/80">
            <p className="text-[10px] text-slate-400 font-bold uppercase">UNLOCODEs</p>
            <p className="text-xs font-black text-cyan-300 font-mono mt-0.5">
              {masterDataStatus?.ports_count?.toLocaleString() || '13,670'}
            </p>
          </div>
          <div className="p-2 rounded-xl bg-slate-950/80 border border-slate-800/80">
            <p className="text-[10px] text-slate-400 font-bold uppercase">Carriers</p>
            <p className="text-xs font-black text-purple-300 font-mono mt-0.5">
              {masterDataStatus?.carriers_count || '164'}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
};
