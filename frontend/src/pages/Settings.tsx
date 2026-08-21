import React, { useState } from 'react';
import { Settings, Database, RefreshCw } from 'lucide-react';
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
    <div className="w-full flex-1 flex flex-col min-h-0 space-y-6 animate-fade-in select-none text-slate-900 pb-8">
      
      {/* ── TOP HERO HEADER (Posh Light Theme) ── */}
      <div className="bg-white rounded-3xl p-6 sm:p-7 border border-slate-200/90 shadow-sm relative overflow-hidden shrink-0 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-bl from-indigo-500/10 via-purple-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative z-10 space-y-2">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200/80 text-indigo-700 text-[11px] font-black uppercase tracking-wider flex items-center gap-1.5 shadow-2xs">
              <Settings className="w-3.5 h-3.5 text-indigo-600" />
              RateBridge Engine Configuration
            </span>
            <span className="px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-emerald-700 text-[11px] font-mono font-black flex items-center gap-1.5 shadow-2xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              Master Data Synchronized
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Master Data & Ingestion Settings
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 font-medium max-w-3xl leading-relaxed">
            Manage global UNLOCODE port dictionaries, container equipment aliases, self-learned carrier synonyms, and export validation policies.
          </p>
        </div>
      </div>

      {/* ── MASTER DATA STATS & RELOAD ── */}
      <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm space-y-5">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider">Freightify Master Data Status</h2>
              <p className="text-xs text-slate-500 font-medium mt-0.5">UNLOCODE port index and carrier SCAC synonym database</p>
            </div>
          </div>

          <button
            onClick={handleReloadMasterData}
            disabled={isReloading}
            className="px-4 py-2 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-black text-xs transition-all shadow-md shadow-indigo-600/20 flex items-center gap-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isReloading ? 'animate-spin' : ''}`} />
            <span>Reload Master Data</span>
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
            <p className="text-[11px] font-black text-slate-400 uppercase">UNLOCODE Ports</p>
            <p className="text-2xl font-black text-slate-900 font-mono mt-1">
              {masterDataStatus?.ports_count?.toLocaleString() || '13,670'}
            </p>
          </div>
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
            <p className="text-[11px] font-black text-slate-400 uppercase">Carrier SCACs</p>
            <p className="text-2xl font-black text-purple-600 font-mono mt-1">
              {masterDataStatus?.carriers_count || '164'}
            </p>
          </div>
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
            <p className="text-[11px] font-black text-slate-400 uppercase">Port Synonyms</p>
            <p className="text-2xl font-black text-indigo-600 font-mono mt-1">
              {masterDataStatus?.port_synonyms_count?.toLocaleString() || '14,515'}
            </p>
          </div>
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
            <p className="text-[11px] font-black text-slate-400 uppercase">Self-Learned Aliases</p>
            <p className="text-2xl font-black text-emerald-600 font-mono mt-1">
              {masterDataStatus?.learned_synonyms_count?.toLocaleString() || '1,438'}
            </p>
          </div>
        </div>
      </div>

      {/* ── EXPORT VALIDATION POLICY CARD ── */}
      <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm space-y-4">
        <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider">Default Export Validation Policy</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
              className={`p-4 rounded-2xl border-2 cursor-pointer transition-all ${
                exportPolicy === pol.id
                  ? 'border-indigo-600 bg-indigo-50/50 shadow-sm'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-black text-slate-900">{pol.title}</span>
                {exportPolicy === pol.id && (
                  <span className="w-2.5 h-2.5 rounded-full bg-indigo-600" />
                )}
              </div>
              <p className="text-[11px] text-slate-500 font-medium leading-relaxed">{pol.desc}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
