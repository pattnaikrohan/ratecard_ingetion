import React, { useEffect, useState } from 'react';
import { Cpu, CheckCircle2, Sparkles, ArrowRight, ShieldCheck, RefreshCw } from 'lucide-react';
import { api } from '../services/api';

interface BatchProcessingModalProps {
  isOpen: boolean;
  onClose: () => void;
  files: File[];
  jobIds: string[];
  onInspectJob: (jobId: string) => void;
}

export const BatchProcessingModal: React.FC<BatchProcessingModalProps> = ({ isOpen, onClose, files, jobIds, onInspectJob }) => {
  const [jobStates, setJobStates] = useState<Record<string, any>>({});
  const [overallProgress, setOverallProgress] = useState(0);

  useEffect(() => {
    if (!isOpen || files.length === 0) return;

    // Start polling job states
    const interval = setInterval(async () => {
      if (jobIds.length === 0) return;

      try {
        const updated: Record<string, any> = {};
        let totalProg = 0;

        for (const id of jobIds) {
          try {
            const data = await api.getJob(id);
            updated[id] = data;
            totalProg += data.progress || 0;
          } catch (err) {
            updated[id] = { status: 'FAILED', progress: 100, log_msg: 'Job not found or server error.' };
            totalProg += 100;
          }
        }

        setJobStates(updated);
        setOverallProgress(Math.round(totalProg / jobIds.length));

        const allFinished = Object.values(updated).every((j) =>
          ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED', 'FAILED'].includes(j.status)
        );

        if (allFinished) {
          clearInterval(interval);
        }
      } catch (err) {
        console.error('Error polling batch status:', err);
      }
    }, 600);

    return () => clearInterval(interval);
  }, [isOpen, files, jobIds]);

  if (!isOpen) return null;

  const isAllComplete = jobIds.length > 0 && jobIds.length === files.length && jobIds.every((id) => {
    const st = jobStates[id]?.status;
    return ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(st);
  });

  const getPipelineStageMessage = (job: any, isUploading: boolean) => {
    if (isUploading || !job) return 'Uploading file & initializing high-speed parser...';
    const prog = job.progress || 0;
    if (prog < 25) return 'Extracting rate matrix & email attachments...';
    if (prog < 50) return 'Un-pivoting 20GP/40GP/40HC container columns...';
    if (prog < 75) return 'Aligning port cities against 13,670 UNLOCODEs...';
    if (prog < 95) return 'Validating dates, currencies & OFR surcharge inclusions...';
    return 'Completed! Freightify workbook ready for download.';
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
      <div className="card-elevated w-full max-w-3xl bg-white border border-slate-200 text-slate-900 p-7 space-y-6 shadow-2xl rounded-2xl relative overflow-hidden">
        
        {/* Top Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-sky-500 to-emerald-400 p-0.5 shadow-md">
              <div className="w-full h-full bg-white rounded-[10px] flex items-center justify-center">
                <Cpu className="w-5 h-5 text-indigo-600 animate-spin" />
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-black text-slate-900">Carrier Rate Sheet Ingestion Engine</h3>
                <span className="badge-pill badge-valid text-[10px]">
                  <Sparkles className="w-3 h-3 text-indigo-600" /> Active Batch
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Parsing carrier matrices, aligning 13,670 UNLOCODEs, and populating Freightify workbooks
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-900 flex items-center justify-center transition-colors font-bold text-xs"
          >
            ✕
          </button>
        </div>

        {/* Overall Progress Tracker */}
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
          <div className="flex justify-between items-center text-xs font-extrabold">
            <span className="text-slate-600 uppercase tracking-wider">Overall Batch Execution Progress</span>
            <span className="text-indigo-600 font-mono text-sm">{overallProgress}%</span>
          </div>
          <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-600 via-sky-500 to-emerald-500 transition-all duration-300 shadow-sm"
              style={{ width: `${Math.max(overallProgress, 15)}%` }}
            />
          </div>
        </div>

        {/* Instant File Cards (Rendered Immediately) */}
        <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
          {files.map((file, index) => {
            const jobId = jobIds[index];
            const job = jobId ? jobStates[jobId] : null;
            const prog = job?.progress || (jobId ? 20 : 10);
            const status = job?.status || (jobId ? 'PARSING' : 'UPLOADING');
            const isDone = ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(status);

            return (
              <div
                key={index}
                className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:border-indigo-300 transition-all space-y-2.5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-xs">
                      {index + 1}
                    </div>
                    <div>
                      <p className="text-xs font-extrabold text-slate-900 font-mono truncate max-w-sm">
                        {file.name}
                      </p>
                      <p className="text-[11px] text-indigo-600 font-bold mt-0.5">
                        {getPipelineStageMessage(job, !jobId)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {isDone ? (
                      <span className="badge-pill badge-valid">
                        <CheckCircle2 className="w-3.5 h-3.5" /> {job?.summary?.total_rows || 0} Rows
                      </span>
                    ) : (
                      <span className="badge-pill badge-warning">
                        <RefreshCw className="w-3 h-3 animate-spin" /> {prog}%
                      </span>
                    )}

                    {isDone && jobId && (
                      <button
                        onClick={() => {
                          onInspectJob(jobId);
                          onClose();
                        }}
                        className="btn-shiny-indigo text-xs py-1 px-3"
                      >
                        Inspect <ArrowRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar per File */}
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      isDone ? 'bg-emerald-500' : 'bg-indigo-600'
                    }`}
                    style={{ width: `${prog}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between border-t border-slate-100 pt-4">
          <div className="flex items-center gap-2 text-xs text-slate-500 font-bold">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Master Data Active: 13,670 LOCODEs & 164 Carriers</span>
          </div>

          <div className="flex items-center gap-3">
            {isAllComplete && jobIds.length > 0 ? (
              <button
                onClick={() => {
                  onInspectJob(jobIds[0]);
                  onClose();
                }}
                className="btn-shiny-emerald text-xs"
              >
                Inspect Results <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button onClick={onClose} className="btn-outline text-xs">
                Minimize & Process in Background
              </button>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
