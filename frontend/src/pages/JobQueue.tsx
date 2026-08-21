import React, { useState } from 'react';
import { FileCode, Eye, CheckCircle2, X, ListFilter, Sparkles } from 'lucide-react';
import { api } from '../services/api';

interface JobQueueProps {
  jobs: any[];
  onSelectJob: (jobId: string) => void;
}

export const JobQueue: React.FC<JobQueueProps> = ({ jobs, onSelectJob }) => {
  const [selectedLogJob, setSelectedLogJob] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  const handleViewLogs = async (jobId: string) => {
    try {
      const res = await api.getJobLogs(jobId);
      setLogs(res.logs || []);
      setSelectedLogJob(jobId);
    } catch (err) {
      alert('Error fetching job logs: ' + err);
    }
  };

  return (
    <div className="w-full space-y-8 animate-fade-in text-slate-900 pb-20">
      
      {/* ── TOP HERO HEADER (Posh Ambient Glassmorphic Card) ── */}
      <div className="bg-white/95 backdrop-blur-xl rounded-3xl p-8 border border-slate-200/80 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.04)] relative overflow-hidden shrink-0 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-bl from-[#00AFAF]/12 via-indigo-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative z-10 space-y-2.5 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="px-3.5 py-1 rounded-full bg-[#00AFAF]/10 border border-[#00AFAF]/25 text-[#008f8f] text-xs font-black uppercase tracking-wider flex items-center gap-1.5 shadow-2xs">
              <Sparkles className="w-3.5 h-3.5 text-[#00AFAF]" />
              RateBridge Execution Queue
            </span>
            <span className="px-3.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-emerald-700 text-xs font-mono font-black flex items-center gap-1.5 shadow-2xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Async Pipeline Active
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Asynchronous Ingestion Pipeline
          </h1>
          <p className="text-sm text-slate-500 font-medium leading-relaxed">
            Real-time tracking of rate matrix unpivoting, autonomous AI fallback extractions, UNLOCODE resolution, and .xlsm generation.
          </p>
        </div>
      </div>

      {/* ── QUEUE TABLE CARD (Luxury Porcelain) ── */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] flex-1 min-h-0 flex flex-col overflow-hidden relative">
        <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-[#00AFAF] via-indigo-600 to-purple-600" />
        
        <div className="px-8 py-5 flex items-center justify-between border-b border-slate-100 bg-slate-50/70 shrink-0">
          <div className="flex items-center gap-2">
            <ListFilter className="w-4 h-4 text-[#00AFAF]" />
            <h3 className="text-xs font-black text-slate-900 uppercase tracking-wider">Active Pipeline Jobs ({jobs.length})</h3>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0">
          <table className="custom-table w-full align-middle text-slate-900 text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase text-[10px] tracking-wider font-extrabold">
                <th className="pl-8 text-left py-4">Job ID</th>
                <th className="text-left py-4">Source File</th>
                <th className="text-center py-4">Status</th>
                <th className="text-center py-4">Progress</th>
                <th className="text-center py-4">Rates / Valid</th>
                <th className="pr-8 text-center py-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-20 text-slate-400 font-medium">
                    No active ingestion jobs in queue.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.job_id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="pl-8 py-4">
                      <span className="font-mono text-xs font-black text-indigo-700 bg-indigo-50 px-3 py-1 rounded-xl border border-indigo-100">
                        {job.job_id}
                      </span>
                    </td>
                    <td className="py-4">
                      <p className="font-black text-slate-900 text-xs truncate max-w-xs">{job.file_name}</p>
                    </td>
                    <td className="text-center py-4">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider inline-flex items-center gap-1 border ${
                        job.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                        job.status === 'NEEDS_REVIEW' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        job.status === 'FAILED' ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-slate-100 text-slate-700 border-slate-200'
                      }`}>
                        {job.status === 'COMPLETED' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                        {job.status}
                      </span>
                    </td>
                    <td className="text-center py-4">
                      <div className="w-32 mx-auto">
                        <div className="flex justify-between text-[10px] text-slate-500 font-mono font-bold mb-1">
                          <span>{job.progress || 0}%</span>
                        </div>
                        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-[#00AFAF] to-indigo-600 transition-all duration-300 rounded-full"
                            style={{ width: `${job.progress || 0}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="text-center py-4 font-mono">
                      <span className="font-bold text-slate-900">{job.summary?.total_rows || 0}</span>
                      <span className="text-slate-400"> / </span>
                      <span className="font-bold text-emerald-600">{job.summary?.valid_rows || 0}</span>
                    </td>
                    <td className="pr-8 text-center py-4">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => handleViewLogs(job.job_id)}
                          className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-black text-xs transition-all border border-slate-200 shadow-2xs inline-flex items-center gap-1.5"
                        >
                          <FileCode className="w-3.5 h-3.5" /> Logs
                        </button>
                        <button
                          onClick={() => onSelectJob(job.job_id)}
                          style={{ backgroundColor: '#00AFAF' }}
                          className="px-3.5 py-1.5 rounded-xl text-white font-black text-xs transition-all shadow-sm shadow-[#00AFAF]/20 inline-flex items-center gap-1.5"
                        >
                          <Eye className="w-3.5 h-3.5" /> Inspect
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── LOGS MODAL ── */}
      {selectedLogJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-3xl p-7 max-w-2xl w-full border border-slate-200 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-black text-slate-900 flex items-center gap-2">
                <FileCode className="w-4 h-4 text-[#00AFAF]" /> Pipeline Logs: {selectedLogJob}
              </h3>
              <button
                onClick={() => setSelectedLogJob(null)}
                className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 bg-slate-950 rounded-2xl p-4 overflow-y-auto font-mono text-xs text-slate-300 space-y-1 custom-scrollbar">
              {logs.length === 0 ? (
                <p className="text-slate-500">No logs available for this job.</p>
              ) : (
                logs.map((l, i) => (
                  <p key={i} className="leading-relaxed">
                    <span className="text-slate-500">[{i + 1}]</span> {l}
                  </p>
                ))
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
