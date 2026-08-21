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
  Anchor,
  Trash2
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  masterDataStatus: any;
  onClearData?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, masterDataStatus, onClearData }) => {
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
      {/* Ambient background bloom */}
      <div className="absolute top-0 right-0 w-48 h-48 bg-white/10 rounded-full blur-2xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-48 h-48 bg-black/10 rounded-full blur-2xl pointer-events-none" />

      {/* ── TOP: Brand & Darker Faded Logo Block ── */}
      <div className="relative z-10">
        <div className="p-5 bg-gradient-to-b from-[#006e6e]/90 via-[#008f8f]/60 to-transparent border-b border-white/10 flex items-center gap-3 relative shadow-inner">
          <div className="w-10 h-10 rounded-2xl bg-[#005555]/70 border border-white/15 text-white flex items-center justify-center shadow-lg shadow-black/20 shrink-0 font-black backdrop-blur-md">
            <Anchor className="w-5 h-5 text-white/95" />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-black text-white tracking-tight truncate flex items-center gap-1.5 drop-shadow-xs">
              RateBridge
              <Sparkles className="w-3.5 h-3.5 text-teal-200 shrink-0" />
            </h1>
            <p className="text-[10px] text-teal-100/80 font-extrabold uppercase tracking-widest">Rate Intelligence</p>
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
                    : 'text-white/90 hover:text-white hover:bg-white/15'
                }`}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 transition-transform duration-200 ${
                    isActive ? 'text-[#00AFAF]' : 'text-white/80 group-hover:scale-110'
                  }`}
                />
                <div className="text-left min-w-0">
                  <span className="block truncate">{tab.label}</span>
                  <span
                    className={`block text-[10px] font-medium leading-tight truncate ${
                      isActive ? 'text-[#008f8f]' : 'text-white/70'
                    }`}
                  >
                    {tab.sub}
                  </span>
                </div>
              </button>
            );
          })}
        </nav>
      </div>

      {/* ── BOTTOM: Master Data Status & Explicit Clear Data Button ── */}
      <div className="p-4 relative z-10 space-y-2">
        <div className="p-3 rounded-2xl bg-[#008f8f]/40 backdrop-blur-md border border-white/20 text-white space-y-2 shadow-inner">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider flex items-center gap-1.5 text-white">
              <Database className="w-3.5 h-3.5 text-teal-200" />
              Master Data
            </span>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px] text-white/90 font-mono">
            <div>
              <p className="text-white/70 text-[9px] uppercase">Ports</p>
              <p className="font-black text-xs text-white">{masterDataStatus?.ports_count?.toLocaleString('en-US') || '13,670'}</p>
            </div>
            <div>
              <p className="text-white/70 text-[9px] uppercase">SCACs</p>
              <p className="font-black text-xs text-white">{masterDataStatus?.carriers_count || '164'}</p>
            </div>
          </div>
        </div>

        {onClearData && (
          <button
            onClick={onClearData}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-[11px] font-bold text-white/85 hover:text-white bg-black/20 hover:bg-rose-600/85 border border-white/10 hover:border-rose-400/40 transition-all cursor-pointer shadow-xs group"
          >
            <Trash2 className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
            <span>Clear Ingested Data</span>
          </button>
        )}
      </div>
    </aside>
  );
};
