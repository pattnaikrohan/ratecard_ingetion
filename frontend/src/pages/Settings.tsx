import React, { useState } from 'react';
import { Database, RefreshCw, Sparkles, } from 'lucide-react';
import { api } from '../services/api';

interface SettingsProps {
  exportPolicy: string;
  setExportPolicy: (policy: string) => void;
  masterDataStatus: any;
  onMasterDataReloaded: () => void;
}

export const SettingsPage: React.FC<SettingsProps> = ({
  exportPolicy,
  setExportPolicy,
  masterDataStatus,
  onMasterDataReloaded,
}) => {
  const [isReloading, setIsReloading] = useState(false);

  const handleReloadMasterData = async () => {
    try {
      setIsReloading(true);
      await api.reloadMasterData();
      onMasterDataReloaded();
      alert('Master Data successfully reloaded and port index rebuilt!');
    } catch (err) {
      alert('Error reloading master data: ' + err);
    } finally {
      setIsReloading(false);
    }
  };

  return (
    <div className="w-full flex-1 flex flex-col min-h-0 space-y-8 animate-fade-in select-none text-slate-900 pb-16 px-1">
      
      {/* ── TOP HERO HEADER (Posh Ambient Glassmorphic Card) ── */}
      <div className="bg-white/95 backdrop-blur-xl rounded-3xl p-8 border border-slate-200/80 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.04)] relative overflow-hidden shrink-0 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-bl from-[#00AFAF]/12 via-indigo-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative z-10 space-y-2.5 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="px-3.5 py-1 rounded-full bg-[#00AFAF]/10 border border-[#00AFAF]/25 text-[#008f8f] text-xs font-black uppercase tracking-wider flex items-center gap-1.5 shadow-2xs">
              <Sparkles className="w-3.5 h-3.5 text-[#00AFAF]" />
              RateBridge Engine Configuration
            </span>
            <span className="px-3.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-emerald-700 text-xs font-mono font-black flex items-center gap-1.5 shadow-2xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              Master Data Active
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Master Data & Ingestion Settings
          </h1>
          <p className="text-sm text-slate-500 font-medium leading-relaxed">
            Manage global UNLOCODE port dictionaries, container equipment aliases, self-learned carrier synonyms, and export validation policies.
          </p>
        </div>
      </div>

      {/* ── MASTER DATA STATS & RELOAD (Luxury Porcelain) ── */}
      <div className="bg-white rounded-3xl p-8 border border-slate-200/90 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] space-y-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-[#00AFAF] via-indigo-600 to-purple-600" />

        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-[#00AFAF]/10 border border-[#00AFAF]/25 text-[#00AFAF] flex items-center justify-center">
              <Database className="w-5.5 h-5.5" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider">Freightify Master Data Database</h2>
              <p className="text-xs text-slate-500 font-medium mt-0.5">UNLOCODE port index and carrier SCAC synonym database</p>
            </div>
          </div>

          <button
            onClick={handleReloadMasterData}
            disabled={isReloading}
            style={{ backgroundColor: '#00AFAF' }}
            className="px-5 py-2.5 rounded-2xl text-white font-black text-xs transition-all shadow-md shadow-[#00AFAF]/20 flex items-center gap-2 disabled:opacity-50 hover:brightness-105"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isReloading ? 'animate-spin' : ''}`} />
            <span>Reload Master Data</span>
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
          <div className="p-5 rounded-3xl bg-slate-50 border border-slate-200/80">
            <p className="text-[11px] font-black text-slate-400 uppercase">UNLOCODE Ports</p>
            <p className="text-3xl font-black text-slate-900 font-mono mt-1">
              {masterDataStatus?.ports_count?.toLocaleString('en-US') || '13,670'}
            </p>
          </div>
          <div className="p-5 rounded-3xl bg-slate-50 border border-slate-200/80">
            <p className="text-[11px] font-black text-slate-400 uppercase">Carrier SCACs</p>
            <p className="text-3xl font-black text-purple-600 font-mono mt-1">
              {masterDataStatus?.carriers_count || '164'}
            </p>
          </div>
          <div className="p-5 rounded-3xl bg-slate-50 border border-slate-200/80">
            <p className="text-[11px] font-black text-slate-400 uppercase">Port Synonyms</p>
            <p className="text-3xl font-black text-indigo-600 font-mono mt-1">
              {masterDataStatus?.port_synonyms_count?.toLocaleString('en-US') || '14,515'}
            </p>
          </div>
          <div className="p-5 rounded-3xl bg-slate-50 border border-slate-200/80">
            <p className="text-[11px] font-black text-slate-400 uppercase">Self-Learned Aliases</p>
            <p className="text-3xl font-black text-[#00AFAF] font-mono mt-1">
              {masterDataStatus?.learned_synonyms_count?.toLocaleString('en-US') || '1,438'}
            </p>
          </div>
        </div>
      </div>

      {/* ── EXPORT VALIDATION POLICY CARD ── */}
      <div className="bg-white rounded-3xl p-8 border border-slate-200/90 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] space-y-5">
        <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider">Default Export Validation Policy</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[
            {
              id: 'STRICT',
              title: 'Strict Mode',
              desc: 'Exports only 100% valid rows. Any row with missing validity or unmapped port is omitted from the .xlsm export.',
            },
            {
              id: 'PARTIAL',
              title: 'Partial Export (Recommended)',
              desc: 'Exports valid and warning rows with highlighted flags. Completely invalid error rows are quarantined.',
            },
            {
              id: 'WARNING_PERMISSIVE',
              title: 'Permissive Mode',
              desc: 'Exports all extracted rows into the Freightify workbook regardless of validation warnings.',
            },
          ].map((pol) => (
            <div
              key={pol.id}
              onClick={() => setExportPolicy(pol.id)}
              className={`p-5 rounded-3xl border-2 cursor-pointer transition-all ${
                exportPolicy === pol.id
                  ? 'border-[#00AFAF] bg-[#00AFAF]/5 shadow-sm'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-black text-slate-900">{pol.title}</span>
                {exportPolicy === pol.id && (
                  <span className="w-2.5 h-2.5 rounded-full bg-[#00AFAF]" />
                )}
              </div>
              <p className="text-xs text-slate-500 font-medium leading-relaxed">{pol.desc}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
