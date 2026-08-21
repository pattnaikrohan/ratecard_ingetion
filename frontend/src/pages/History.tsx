import React from 'react';
import { Download, Eye, CheckCircle2, FileSpreadsheet, Sparkles } from 'lucide-react';
import { api } from '../services/api';

interface HistoryProps {
  jobs: any[];
  onSelectJob: (jobId: string) => void;
}

export const HistoryPage: React.FC<HistoryProps> = ({ jobs, onSelectJob }) => {
  const completedJobs = jobs.filter((j) => ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(j.status));

  return (
    <div className="w-full flex-1 flex flex-col min-h-0 space-y-8 animate-fade-in select-none text-slate-900 pb-16 px-1">
      
      {/* ── TOP HERO HEADER (Posh Ambient Glassmorphic Card) ── */}
      <div className="bg-white/95 backdrop-blur-xl rounded-3xl p-8 border border-slate-200/80 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.04)] relative overflow-hidden shrink-0 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-bl from-[#00AFAF]/12 via-indigo-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative z-10 space-y-2.5 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="px-3.5 py-1 rounded-full bg-[#00AFAF]/10 border border-[#00AFAF]/25 text-[#008f8f] text-xs font-black uppercase tracking-wider flex items-center gap-1.5 shadow-2xs">
              <Sparkles className="w-3.5 h-3.5 text-[#00AFAF]" />
              RateBridge Audit Archive
            </span>
            <span className="px-3.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-emerald-700 text-xs font-mono font-black flex items-center gap-1.5 shadow-2xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              {completedJobs.length} Workbooks Saved
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Rate Card Archive & Workbook Exports
          </h1>
          <p className="text-sm text-slate-500 font-medium leading-relaxed">
            Browse all previously standardized carrier rate cards, view parsing audit logs, and download pre-generated Freightify upload spreadsheets (.xlsm).
          </p>
        </div>
      </div>

      {/* ── AUDIT HISTORY TABLE CARD (Luxury Porcelain) ── */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] flex-1 min-h-0 flex flex-col overflow-hidden relative">
        <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-[#00AFAF] via-indigo-600 to-purple-600" />

        <div className="px-8 py-5 flex items-center justify-between border-b border-slate-100 bg-slate-50/70 shrink-0">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4 text-[#00AFAF]" />
            <h3 className="text-xs font-black text-slate-900 uppercase tracking-wider">
              Completed Freightify Workbooks ({completedJobs.length})
            </h3>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0">
          <table className="custom-table w-full align-middle text-slate-900 text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase text-[10px] tracking-wider font-extrabold">
                <th className="pl-8 text-left py-4">Source File</th>
                <th className="text-center py-4">Carrier SCAC</th>
                <th className="text-center py-4">Rows Standardized</th>
                <th className="text-left py-4">Output Freightify Sheet</th>
                <th className="pr-8 text-center py-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {completedJobs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-20 text-slate-400 font-medium">
                    No completed rate cards found.
                  </td>
                </tr>
              ) : (
                completedJobs.map((j) => (
                  <tr key={j.job_id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="pl-8 py-4">
                      <p className="font-black text-slate-900 text-xs truncate max-w-xs">{j.file_name}</p>
                      <p className="text-[10px] text-slate-400 font-mono mt-0.5">{j.created_at || 'Recently'}</p>
                    </td>
                    <td className="text-center py-4">
                      <span className="font-mono text-xs font-black text-indigo-700 bg-indigo-50 px-3 py-1 rounded-xl border border-indigo-100">
                        {j.summary?.carriers_found?.join(', ') || 'MAEU'}
                      </span>
                    </td>
                    <td className="text-center py-4">
                      <span className="font-mono text-xs font-black text-emerald-600 inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {j.summary?.total_rows || 0} rows
                      </span>
                    </td>
                    <td className="py-4 font-mono text-xs text-slate-600 font-bold truncate max-w-xs">
                      {j.output_file_name || `Freightify_Upload_${j.job_id}.xlsm`}
                    </td>
                    <td className="pr-8 text-center py-4">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => onSelectJob(j.job_id)}
                          className="px-3.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-black text-xs transition-all border border-slate-200 shadow-2xs inline-flex items-center gap-1"
                        >
                          <Eye className="w-3.5 h-3.5" /> Inspect
                        </button>
                        <a
                          href={api.getDownloadUrl(j.job_id)}
                          target="_blank"
                          rel="noreferrer"
                          style={{ backgroundColor: '#00AFAF' }}
                          className="px-4 py-1.5 rounded-xl text-white font-black text-xs transition-all shadow-md shadow-[#00AFAF]/20 inline-flex items-center gap-1.5"
                        >
                          <Download className="w-3.5 h-3.5" /> Export .xlsm
                        </a>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};
