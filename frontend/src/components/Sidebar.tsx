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
    { id: 'dashboard', label: 'Dashboard', sub: 'Analytics & AI Cost', icon: BarChart3 },
    { id: 'ingest', label: 'Rate Ingestion', sub: 'Upload & Standardize', icon: UploadCloud },
    { id: 'queue', label: 'Processing Queue', sub: 'Live Worker Pipeline', icon: ListFilter },
    { id: 'review', label: 'Review Grid', sub: 'Inspect & Edit Rates', icon: CheckSquare },
    { id: 'history', label: 'History & Exports', sub: 'Freightify .XLSM Files', icon: History },
    { id: 'settings', label: 'Master Data', sub: 'Synonyms & Config', icon: Settings },
  ];

  return (
    <aside 
      style={{ backgroundColor: '#00AFAF' }} 
      className="w-64 shrink-0 h-screen text-white flex flex-col justify-between select-none z-40 shadow-2xl relative overflow-hidden border-r border-[#009696]"
    >
      {/* Background Subtle Gradient & Light Bloom */}
      <div className="absolute top-0 right-0 w-48 h-48 bg-white/10 rounded-full blur-2xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-48 h-48 bg-black/10 rounded-full blur-2xl pointer-events-none" />

      {/* ── TOP: Brand & Logo ── */}
      <div className="relative z-10">
        <div className="p-5 border-b border-white/15 flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-white text-[#00AFAF] flex items-center justify-center shadow-md shadow-black/10 shrink-0 font-black">
            <Anchor className="w-5 h-5 text-[#00AFAF]" />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-black text-white tracking-tight truncate flex items-center gap-1.5">
              RateBridge
              <Sparkles className="w-3.5 h-3.5 text-white/90 shrink-0" />
            </h1>
            <p className="text-[10px] text-white/80 font-extrabold uppercase tracking-widest">Rate Intelligence</p>
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
                    ? 'bg-white text-[#007f7f] shadow-lg shadow-black/10 scale-[1.02]'
                    : 'text-white/90 hover:text-white hover:bg-white/15 border border-transparent'
                }`}
              >
                <div className={`w-7 h-7 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
                  isActive ? 'bg-[#00AFAF] text-white shadow-2xs' : 'bg-white/15 text-white group-hover:bg-white/25'
                }`}>
                  <Icon className="w-4 h-4" />
                </div>
                
                <div className="text-left min-w-0 flex-1">
                  <div className="truncate text-xs font-black">{tab.label}</div>
                  <div className={`text-[10px] truncate font-medium ${isActive ? 'text-[#008f8f]' : 'text-white/70'}`}>
                    {tab.sub}
                  </div>
                </div>

                {isActive && (
                  <span className="w-2 h-2 rounded-full bg-[#00AFAF] ml-auto shrink-0 animate-pulse" />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* ── BOTTOM: Master Data Engine Widget ── */}
      <div className="p-4 m-3 rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 space-y-2.5 relative z-10 shadow-sm text-white">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-white flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-white" /> Master Data Engine
          </span>
          <span className="flex items-center gap-1 text-[10px] font-mono font-black text-white bg-white/20 border border-white/30 px-2 py-0.5 rounded-full shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> Active
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-center pt-1 border-t border-white/15">
          <div className="p-2 rounded-xl bg-white/20 border border-white/20">
            <p className="text-[10px] text-white/80 font-bold uppercase">UNLOCODEs</p>
            <p className="text-xs font-black text-white font-mono mt-0.5">
              {masterDataStatus?.ports_count?.toLocaleString() || '13,670'}
            </p>
          </div>
          <div className="p-2 rounded-xl bg-white/20 border border-white/20">
            <p className="text-[10px] text-white/80 font-bold uppercase">Carriers</p>
            <p className="text-xs font-black text-white font-mono mt-0.5">
              {masterDataStatus?.carriers_count || '164'}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
};
