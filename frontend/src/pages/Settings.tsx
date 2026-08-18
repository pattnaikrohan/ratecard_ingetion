import React, { useState } from 'react';
import { RefreshCw, Database, Shield, CheckCircle2, Settings, Cpu, Sparkles } from 'lucide-react';
import { api } from '../services/api';

interface SettingsProps {
  exportPolicy: string;
  setExportPolicy: (policy: string) => void;
  masterDataStatus: any;
  onMasterDataReloaded: () => void;
}

export const SettingsPage: React.FC<SettingsProps> = ({ exportPolicy, setExportPolicy, masterDataStatus, onMasterDataReloaded }) => {
  const [isReloading, setIsReloading] = useState(false);

  const handleReloadMasterData = async () => {
    try {
      setIsReloading(true);
      await api.reloadMasterData();
      onMasterDataReloaded();
      alert('Master Data reloaded successfully into memory!');
    } catch (err) {
      alert('Error reloading master data: ' + err);
    } finally {
      setIsReloading(false);
    }
  };

  return (
    <div className="w-full flex-1 flex flex-col min-h-0 space-y-4 animate-fade-in select-none overflow-y-auto custom-scrollbar text-slate-900 pr-1">
      
      {/* ── TOP HERO BANNER ── */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-5 text-white shadow-xl border border-indigo-900/40 relative overflow-hidden shrink-0 flex items-center justify-between gap-6">
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-cyan-300 text-[10px] font-black uppercase tracking-widest flex items-center gap-1.5">
              <Settings className="w-3.5 h-3.5 text-cyan-400" /> Platform Configuration
            </span>
          </div>
          <h2 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
            Engine & Master Data Alignment Controls
          </h2>
          <p className="text-xs text-slate-300 font-medium mt-1">
            Configure default export policies and manage UNLOCODE master data cache in RAM
          </p>
        </div>
      </div>

      {/* ── SETTINGS CARDS CONTAINER ── */}
      <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0 space-y-4">
        {/* Export Policy Card */}
        <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center">
              <Shield className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h3 className="text-sm font-black text-slate-900 uppercase tracking-wider">Export Policy Rule</h3>
              <p className="text-xs text-slate-500 font-medium">How validation exceptions are handled during Freightify .xlsm export generation</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { id: 'STRICT', label: 'Strict Validation', desc: 'Any error blocks .xlsm export until resolved.' },
              { id: 'PARTIAL', label: 'Partial Export', desc: 'Exports valid rows into Freightify workbook, flags exceptions.' },
              { id: 'WARNING_PERMISSIVE', label: 'Permissive Export', desc: 'Exports all rate rows, including non-fatal warnings.' },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => setExportPolicy(p.id)}
                className={`text-left p-4 rounded-2xl border-2 transition-all ${
                  exportPolicy === p.id
                    ? 'border-indigo-600 bg-indigo-50/60 shadow-sm'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-black text-slate-900">{p.label}</span>
                  {exportPolicy === p.id ? (
                    <CheckCircle2 className="w-4 h-4 text-indigo-600" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border-2 border-slate-300" />
                  )}
                </div>
                <p className="text-xs text-slate-500 font-medium">{p.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Master Data Engine Cache */}
        <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-sky-50 border border-sky-100 flex items-center justify-center">
                <Database className="w-5 h-5 text-sky-600" />
              </div>
              <div>
                <h3 className="text-sm font-black text-slate-900 uppercase tracking-wider">Master Data RAM Cache</h3>
                <p className="text-xs text-slate-500 font-medium">Version {masterDataStatus?.version || '1.09'} (Freightify Master Sheet)</p>
              </div>
            </div>
            <button
              onClick={handleReloadMasterData}
              disabled={isReloading}
              className="btn-primary text-xs py-2 px-4 rounded-xl shadow-xs"
            >
              <RefreshCw className={`w-4 h-4 ${isReloading ? 'animate-spin' : ''}`} />
              Reload Master Cache
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { label: 'Port UNLOCODEs', value: masterDataStatus?.ports_count?.toLocaleString() || '13,670', color: 'text-sky-600 bg-sky-50 border-sky-100' },
              { label: 'Carrier SCACs', value: masterDataStatus?.carriers_count || '164', color: 'text-indigo-600 bg-indigo-50 border-indigo-100' },
              { label: 'Load Types', value: masterDataStatus?.load_types?.length || '18', color: 'text-emerald-600 bg-emerald-50 border-emerald-100' },
            ].map((s) => (
              <div key={s.label} className={`rounded-2xl p-4 text-center border ${s.color}`}>
                <p className="text-xs font-extrabold uppercase tracking-wider">{s.label}</p>
                <p className="text-2xl font-black font-mono mt-1">{s.value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Azure AI Integration Status */}
        <div className="bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-purple-50 border border-purple-100 flex items-center justify-center">
                <Cpu className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <h3 className="text-sm font-black text-slate-900 uppercase tracking-wider">Azure Document Intelligence AI</h3>
                <p className="text-xs text-slate-500 font-medium">Resource: <span className="font-bold text-slate-700">Freightify-rate-extraction</span> (v3.0 REST API prebuilt-layout)</p>
              </div>
            </div>
            <span className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-mono font-black flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-emerald-600" /> Live & Connected
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
