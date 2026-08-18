import React from 'react';
import { Download, Eye, CheckCircle2, History, FileSpreadsheet } from 'lucide-react';
import { api } from '../services/api';

interface HistoryProps {
  jobs: any[];
  onSelectJob: (jobId: string) => void;
}

export const HistoryPage: React.FC<HistoryProps> = ({ jobs, onSelectJob }) => {
  const completedJobs = jobs.filter((j) => ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(j.status));

  return (
    <div className="w-full flex-1 flex flex-col min-h-0 space-y-4 animate-fade-in select-none overflow-y-auto custom-scrollbar text-slate-900 pr-1">
      
      {/* ── TOP HERO BANNER ── */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-5 text-white shadow-xl border border-indigo-900/40 relative overflow-hidden shrink-0 flex items-center justify-between gap-6">
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-cyan-300 text-[10px] font-black uppercase tracking-widest flex items-center gap-1.5">
              <History className="w-3.5 h-3.5 text-cyan-400" /> Audit Log & Export Archive
            </span>
          </div>
          <h2 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
            Historical Ingestion Workbooks & Audit Trail
          </h2>
          <p className="text-xs text-slate-300 font-medium mt-1">
            Browse previously processed rate cards and download generated Freightify upload sheets (.xlsm)
          </p>
        </div>
      </div>

      {/* ── AUDIT HISTORY TABLE CARD ── */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-sm flex-1 min-h-0 flex flex-col overflow-hidden">
        <div className="px-6 py-3.5 flex items-center justify-between border-b border-slate-100 bg-slate-50/70 shrink-0">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4 text-indigo-600" />
            <h3 className="text-xs font-black text-slate-900 uppercase tracking-wider">Completed Workbooks ({completedJobs.length})</h3>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0">
          <table className="custom-table w-full align-middle text-slate-900">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase text-[10px] tracking-wider font-extrabold">
                <th className="pl-6 text-left py-3">Ingested At</th>
                <th className="text-left py-3">Source File</th>
                <th className="text-center py-3">Carrier SCAC</th>
                <th className="text-center py-3">Rows Standardized</th>
                <th className="text-left py-3">Output Freightify Sheet</th>
                <th className="pr-6 text-center py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {completedJobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-16 text-slate-400 text-xs font-medium">
                    No completed ingestions found.
                  </td>
                </tr>
              ) : (
                completedJobs.map((j) => (
                  <tr key={j.job_id} className="group hover:bg-indigo-50/40 transition-colors">
                    <td className="pl-6 py-3 font-mono text-xs font-bold text-slate-500">
                      {j.created_at || 'Recently'}
                    </td>
                    <td className="py-3">
                      <p className="font-black text-slate-900 text-xs truncate max-w-xs">{j.file_name}</p>
                    </td>
                    <td className="text-center py-3">
                      <span className="font-mono text-xs font-black text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-100">
                        {j.summary?.carriers_found?.join(', ') || 'MAEU'}
                      </span>
                    </td>
                    <td className="text-center py-3">
                      <span className="font-mono text-xs font-black text-emerald-600 inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {j.summary?.total_rows || 0} rows
                      </span>
                    </td>
                    <td className="py-3 font-mono text-xs text-slate-600 font-bold truncate max-w-xs">
                      {j.output_file_name || `Freightify_Upload_${j.job_id}.xlsm`}
                    </td>
                    <td className="pr-6 text-center py-3">
                      <div className="flex items-center justify-center gap-2">
                        <button onClick={() => onSelectJob(j.job_id)} className="btn-secondary text-xs py-1.5 px-3 rounded-xl border-slate-200">
                          <Eye className="w-3.5 h-3.5" /> Inspect
                        </button>
                        <a
                          href={api.getDownloadUrl(j.job_id)}
                          target="_blank"
                          rel="noreferrer"
                          className="btn-shiny-emerald text-xs py-1.5 px-3.5 rounded-xl shadow-xs"
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
