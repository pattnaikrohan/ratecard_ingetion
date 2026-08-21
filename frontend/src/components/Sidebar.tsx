import React from 'react';
import { 
  BarChart3, 
  UploadCloud, 
  ListFilter, 
  CheckSquare, 
  History, 
  Settings, 
  Sparkles, 
  Database,
  Anchor
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  masterDataStatus: any;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, masterDataStatus }) => {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard', sub: 'Summary & Dynamics', icon: BarChart3 },
    { id: 'ingest', label: 'Rate Ingestion', sub: 'Upload & Standardize', icon: UploadCloud },
    { id: 'queue', label: 'Processing Queue', sub: 'Live Worker Pipeline', icon: ListFilter },
    { id: 'review', label: 'Review Grid', sub: 'Inspect & Edit Rates', icon: CheckSquare },
    { id: 'history', label: 'History & Exports', sub: 'Freightify .XLSM Files', icon: History },
    { id: 'settings', label: 'Master Data', sub: 'Synonyms & Config', icon: Settings },
  ];

  return (
    <aside className="w-64 shrink-0 h-screen bg-white border-r border-slate-200/90 text-slate-900 flex flex-col justify-between select-none z-40 shadow-xs relative overflow-hidden">
      
      {/* ── TOP: Brand & Logo ── */}
      <div className="relative z-10">
        <div className="p-5 border-b border-slate-100 flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-600/25 shrink-0 border border-indigo-400/30">
            <Anchor className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-black text-slate-900 tracking-tight truncate flex items-center gap-1.5">
              RateBridge
              <Sparkles className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
            </h1>
            <p className="text-[10px] text-slate-400 font-extrabold uppercase tracking-widest">Rate Intelligence</p>
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
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-2xl text-xs font-black transition-all duration-200 relative group ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700 shadow-2xs border border-indigo-200/80 scale-[1.01]'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
                }`}
              >
                <div className={`w-7 h-7 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
                  isActive ? 'bg-indigo-600 text-white shadow-xs' : 'bg-slate-100 text-slate-500 group-hover:text-slate-900 group-hover:bg-slate-200/70'
                }`}>
                  <Icon className="w-4 h-4" />
                </div>
                
                <div className="text-left min-w-0 flex-1">
                  <div className="truncate text-xs font-black">{tab.label}</div>
                  <div className={`text-[10px] truncate font-medium ${isActive ? 'text-indigo-500' : 'text-slate-400'}`}>
                    {tab.sub}
                  </div>
                </div>

                {isActive && (
                  <span className="w-2 h-2 rounded-full bg-indigo-600 ml-auto shrink-0 shadow-2xs animate-pulse" />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* ── BOTTOM: Master Data Engine Widget (Light Theme) ── */}
      <div className="p-4 m-3 rounded-2xl bg-slate-50 border border-slate-200/90 space-y-2.5 relative z-10 shadow-2xs">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-indigo-600" /> Master Data Engine
          </span>
          <span className="flex items-center gap-1 text-[10px] font-mono font-black text-emerald-700 bg-emerald-100/80 border border-emerald-300 px-2 py-0.5 rounded-full shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Active
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-center pt-1 border-t border-slate-200/70">
          <div className="p-2 rounded-xl bg-white border border-slate-200/80">
            <p className="text-[10px] text-slate-400 font-bold uppercase">UNLOCODEs</p>
            <p className="text-xs font-black text-indigo-600 font-mono mt-0.5">
              {masterDataStatus?.ports_count?.toLocaleString() || '13,670'}
            </p>
          </div>
          <div className="p-2 rounded-xl bg-white border border-slate-200/80">
            <p className="text-[10px] text-slate-400 font-bold uppercase">Carriers</p>
            <p className="text-xs font-black text-purple-600 font-mono mt-0.5">
              {masterDataStatus?.carriers_count || '164'}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
};
