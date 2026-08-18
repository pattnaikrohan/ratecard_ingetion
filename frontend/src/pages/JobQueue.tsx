import React, { useState } from 'react';
import { FileCode, Eye, CheckCircle2, X, ListFilter, Cpu } from 'lucide-react';
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
    <div className="w-full flex-1 flex flex-col min-h-0 space-y-4 animate-fade-in select-none overflow-y-auto custom-scrollbar text-slate-900 pr-1">
      
      {/* ── TOP HERO BANNER ── */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-5 text-white shadow-xl border border-indigo-900/40 relative overflow-hidden shrink-0 flex items-center justify-between gap-6">
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-cyan-300 text-[10px] font-black uppercase tracking-widest flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" /> Worker Execution Queue
            </span>
          </div>
          <h2 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
            Async Ingestion & Normalization Pipeline
          </h2>
          <p className="text-xs text-slate-300 font-medium mt-1">
            Real-time status of carrier rate sheet parsing, container unpivoting, and UNLOCODE validation
          </p>
        </div>
      </div>

      {/* ── QUEUE TABLE CARD ── */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-sm flex-1 min-h-0 flex flex-col overflow-hidden">
        <div className="px-6 py-3.5 flex items-center justify-between border-b border-slate-100 bg-slate-50/70 shrink-0">
          <div className="flex items-center gap-2">
            <ListFilter className="w-4 h-4 text-indigo-600" />
            <h3 className="text-xs font-black text-slate-900 uppercase tracking-wider">Active Pipeline Jobs ({jobs.length})</h3>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0">
          <table className="custom-table w-full align-middle text-slate-900">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase text-[10px] tracking-wider font-extrabold">
                <th className="pl-6 text-left py-3">Job ID</th>
                <th className="text-left py-3">Source File</th>
                <th className="text-center py-3">Status</th>
                <th className="text-center py-3">Progress</th>
                <th className="text-center py-3">Total / Valid / Error</th>
                <th className="text-center py-3">Execution Time</th>
                <th className="pr-6 text-center py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-16 text-slate-400 text-xs font-medium">
                    No ingestion jobs in queue.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.job_id} className="group hover:bg-indigo-50/40 transition-colors">
                    <td className="pl-6 py-3">
                      <span className="font-mono text-xs font-black text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-100">
                        {job.job_id}
                      </span>
                    </td>
                    <td className="py-3">
                      <p className="font-black text-slate-900 text-xs truncate max-w-xs">{job.file_name}</p>
                    </td>
                    <td className="text-center py-3">
                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider inline-flex items-center gap-1 border ${
                        job.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                        job.status === 'NEEDS_REVIEW' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        job.status === 'FAILED' ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-slate-100 text-slate-700 border-slate-200'
                      }`}>
                        {job.status === 'COMPLETED' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                        {job.status}
                      </span>
                    </td>
                    <td className="text-center py-3">
                      <div className="w-28 mx-auto">
                        <div className="flex justify-between text-[11px] text-slate-500 font-mono font-bold mb-1">
                          <span>{job.progress || 0}%</span>
                        </div>
                        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              job.status === 'COMPLETED' ? 'bg-emerald-500' : job.status === 'FAILED' ? 'bg-rose-500' : 'bg-indigo-600'
                            }`}
                            style={{ width: `${job.progress || 0}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="text-center py-3">
                      <span className="font-mono text-xs font-bold">
                        <span className="text-slate-900 font-black">{job.summary?.total_rows || 0}</span>
                        <span className="text-slate-300 mx-1">/</span>
                        <span className="text-emerald-600 font-black">{job.summary?.valid_rows || 0}</span>
                        <span className="text-slate-300 mx-1">/</span>
                        <span className="text-rose-600 font-black">{job.summary?.error_rows || 0}</span>
                      </span>
                    </td>
                    <td className="text-center py-3">
                      <span className="font-mono text-xs font-semibold text-slate-500">
                        {job.summary?.processing_time_ms ? `${job.summary.processing_time_ms.toFixed(0)}ms` : '—'}
                      </span>
                    </td>
                    <td className="pr-6 text-center py-3">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => onSelectJob(job.job_id)}
                          className="btn-primary text-xs py-1.5 px-3 rounded-xl shadow-xs"
                        >
                          <Eye className="w-3.5 h-3.5" /> Inspect
                        </button>
                        <button
                          onClick={() => handleViewLogs(job.job_id)}
                          className="btn-secondary text-xs py-1.5 px-3 rounded-xl border-slate-200"
                        >
                          <FileCode className="w-3.5 h-3.5" /> Logs
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

      {/* Log Modal */}
      {selectedLogJob && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-3xl w-full max-w-3xl shadow-2xl overflow-hidden border border-slate-100 animate-fade-in">
            <div className="px-6 py-4 flex items-center justify-between border-b border-slate-100 bg-slate-50/70">
              <div className="flex items-center gap-2">
                <FileCode className="w-5 h-5 text-indigo-600" />
                <h3 className="text-sm font-black text-slate-900">Execution Logs: {selectedLogJob}</h3>
              </div>
              <button onClick={() => setSelectedLogJob(null)} className="w-8 h-8 rounded-xl hover:bg-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-700 transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="bg-slate-950 p-5 font-mono text-xs text-emerald-400 max-h-96 overflow-y-auto space-y-1">
              {logs.length === 0 ? (
                <p className="text-slate-500">No log entries found.</p>
              ) : (
                logs.map((log, i) => <p key={i}>{log}</p>)
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
