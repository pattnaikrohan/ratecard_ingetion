import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowRight, X, Minus, Maximize2, CheckCircle2, ShieldCheck, FileSpreadsheet, AlertCircle, Ship, Anchor, Compass } from 'lucide-react';
import { api } from '../services/api';

interface BatchProcessingDockProps {
  isOpen: boolean;
  onClose: () => void;
  files: File[];
  jobIds: string[];
  activeIndex: number;
  onInspectJob: (jobId: string) => void;
}

const STAGES = [
  { label: 'Ingesting Rate Cards', desc: 'Parsing EML, PDF & Excel files', icon: '⚓' },
  { label: 'Carrier SCAC Recognition', desc: 'Auto-detecting ocean carrier', icon: '🔍' },
  { label: 'Rate Matrix Unpivoting', desc: 'Mapping 20GP, 40GP, 40HC, 45GP, DG', icon: '⚡' },
  { label: '13,670 UNLOCODE Alignment', desc: 'Matching origin & destination ports', icon: '🌐' },
  { label: 'Freightify .xlsm Generation', desc: 'Building standardized upload sheet', icon: '📦' },
];

/* ── Light Theme Ship & Neural Rate Core Graphic Component ── */
const ShipBlueprintCore: React.FC<{ activeStage: number; happy?: boolean; hasFailed?: boolean }> = ({ activeStage, happy, hasFailed }) => (
  <div className="relative w-56 h-56 sm:w-64 sm:h-64 md:w-72 md:h-72 flex flex-col items-center justify-center select-none shrink-0">
    {/* Soft Ambient Light Aura */}
    <div className={`absolute inset-0 rounded-full blur-3xl opacity-60 ${
      hasFailed ? 'bg-rose-400/30' : happy ? 'bg-emerald-400/30' : 'bg-gradient-to-tr from-indigo-300/40 via-sky-200/40 to-blue-400/30'
    }`} />

    {/* Outer Ship Compass Ring */}
    <div className={`absolute inset-2 rounded-full border-2 border-dashed ${
      hasFailed ? 'border-rose-300' : 'border-indigo-300/60'
    }`}
      style={{ animation: 'spin-slow 24s linear infinite' }}
    />

    {/* Inner Vessel Nav Ring */}
    <div className="absolute inset-8 rounded-full border border-sky-300/80 bg-white/40 backdrop-blur-md shadow-inner" />

    {/* Central Ship Core Node */}
    <div className="relative w-36 h-36 sm:w-40 sm:h-40 md:w-44 md:h-44 rounded-3xl bg-white border border-slate-200/90 shadow-2xl shadow-indigo-100 flex flex-col items-center justify-center p-4 text-center">
      {hasFailed ? (
        <div className="flex flex-col items-center gap-2 animate-bounce">
          <div className="w-12 h-12 rounded-2xl bg-rose-500 text-white flex items-center justify-center shadow-lg shadow-rose-200">
            <AlertCircle className="w-7 h-7" />
          </div>
          <span className="text-xs font-black text-rose-600 uppercase tracking-wider">Parsing Error</span>
        </div>
      ) : happy ? (
        <div className="flex flex-col items-center gap-2 animate-bounce">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500 text-white flex items-center justify-center shadow-lg shadow-emerald-200">
            <CheckCircle2 className="w-7 h-7" />
          </div>
          <span className="text-xs font-black text-emerald-600 uppercase tracking-wider">Blueprint Ready</span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <div className="relative">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-sky-500 text-white flex items-center justify-center shadow-xl shadow-indigo-200">
              <Ship className="w-6 h-6 text-white animate-pulse" />
            </div>
            <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-white animate-ping" />
          </div>
          <div className="space-y-0.5">
            <span className="text-[10px] font-black uppercase tracking-widest text-indigo-700 font-mono bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-100 inline-block truncate max-w-[130px]">
              {STAGES[activeStage]?.label || 'Ingesting'}
            </span>
            <p className="text-[10px] text-slate-400 font-bold truncate max-w-[140px] mt-0.5">
              {STAGES[activeStage]?.desc}
            </p>
          </div>
        </div>
      )}
    </div>

    <style>{`
      @keyframes spin-slow { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    `}</style>
  </div>
);

export const BatchProcessingDock: React.FC<BatchProcessingDockProps> = ({
  isOpen, onClose, files, jobIds, activeIndex, onInspectJob,
}) => {
  const [jobStates, setJobStates] = useState<Record<string, any>>({});
  const [simulatedProgress, setSimulatedProgress] = useState(0);
  const [showComplete, setShowComplete] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  useEffect(() => {

    if (isOpen && !isMinimized) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen, isMinimized]);

  useEffect(() => {
    if (!isOpen || files.length === 0) {
      setSimulatedProgress(0);
      setShowComplete(false);
      setIsMinimized(false);
      return;
    }
  }, [isOpen, files]);

  useEffect(() => {
    if (!isOpen || files.length === 0) return;

    const sim = setInterval(() => {
      setSimulatedProgress((prev) => {
        if (showComplete) return 100;
        const activeJobId = jobIds[activeIndex];
        const currentJob = activeJobId ? jobStates[activeJobId] : null;
        let realProg = 75;
        if (currentJob?.status === 'FAILED' || currentJob?.status === 'COMPLETED' || currentJob?.status === 'NEEDS_REVIEW' || currentJob?.status === 'APPROVED') {
          realProg = 100;
        } else if (currentJob?.progress) {
          realProg = currentJob.progress;
        }
        if (prev < realProg) return Math.min(prev + 5, realProg);
        return prev;
      });
    }, 100);

    const poll = setInterval(async () => {
      if (jobIds.length === 0) return;
      try {
        const updated: Record<string, any> = { ...jobStates };
        for (const id of jobIds) { 
          try {
            updated[id] = await api.getJob(id); 
          } catch (err) {
            updated[id] = { status: 'FAILED', progress: 100, log_msg: 'Job not found or server error.' };
          }
        }
        setJobStates(updated);
      } catch { /* silent */ }
    }, 500);

    return () => { clearInterval(sim); clearInterval(poll); };
  }, [isOpen, files.length, jobIds, activeIndex, showComplete, jobStates]);

  useEffect(() => {
    const allDone = jobIds.length > 0 && jobIds.length === files.length &&
      jobIds.every((id) => ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED', 'FAILED'].includes(jobStates[id]?.status));
    if (allDone) {
      setShowComplete(true);
      setSimulatedProgress(100);
    }
  }, [jobStates, jobIds, files]);

  if (!isOpen) return null;

  const failedCount = jobIds.filter((id) => jobStates[id]?.status === 'FAILED').length;
  const successCount = jobIds.filter((id) => ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(jobStates[id]?.status)).length;
  const allFailed = jobIds.length > 0 && failedCount === jobIds.length;
  const hasPartialErrors = failedCount > 0 && !allFailed;

  const displayProgress = showComplete ? 100 : Math.max(simulatedProgress, showComplete ? 100 : 10);
  const currentStage = displayProgress < 20 ? 0 : displayProgress < 40 ? 1 : displayProgress < 60 ? 2 : displayProgress < 80 ? 3 : 4;

  // ── MINIMIZED WIDGET DOCK (Bottom Right) ──
  if (isMinimized) {
    return createPortal(
      <div className="fixed bottom-6 right-6 z-[9999] bg-white border border-slate-200 shadow-2xl rounded-2xl p-4 flex items-center gap-4 animate-fade-in select-none max-w-md">
        <div className={`w-11 h-11 rounded-xl text-white flex items-center justify-center shrink-0 shadow-md ${
          allFailed ? 'bg-rose-500 shadow-rose-200' : 'bg-gradient-to-tr from-indigo-600 to-sky-600 shadow-indigo-200'
        }`}>
          {allFailed ? <AlertCircle className="w-5 h-5" /> : <Ship className="w-5 h-5 animate-pulse" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-black text-slate-900 truncate">
              {showComplete
                ? (hasPartialErrors ? `Batch Ingested (${successCount} Passed, ${failedCount} Failed)` : 'Ingestion Complete ✓')
                : `Ship Pipeline Active (${successCount + failedCount}/${files.length})`}
            </span>
            <span className="text-xs font-black text-indigo-600 font-mono">{displayProgress}%</span>
          </div>
          <div className="w-full h-2 bg-slate-100 rounded-full mt-1.5 overflow-hidden border border-slate-200/60">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                allFailed ? 'bg-rose-500' : showComplete ? 'bg-emerald-500' : 'bg-gradient-to-r from-indigo-500 to-sky-500'
              }`}
              style={{ width: `${displayProgress}%` }}
            />
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setIsMinimized(false)}
            className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-900 transition-colors"
            title="Maximize overlay"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-rose-600 transition-colors"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>,
      document.body
    );
  }

  // ── FULL SCREEN LIGHT THEME SHIP BLUEPRINT OVERLAY ──
  return createPortal(
    <div className="fixed inset-0 top-0 left-0 w-screen h-screen z-[9999] overflow-hidden flex flex-col justify-between select-none animate-fade-in bg-slate-50">
      <div className="absolute inset-0 bg-gradient-to-b from-slate-50 via-white to-indigo-50/20" />

      {/* Header Controls */}
      <div className="absolute top-6 right-8 z-50 flex items-center gap-2.5">
        <button
          onClick={() => setIsMinimized(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white hover:bg-slate-100 text-slate-700 font-bold text-xs transition-all border border-slate-200 shadow-xs"
          title="Minimize to bottom dock"
        >
          <Minus className="w-4 h-4" /> Minimize
        </button>
        <button
          onClick={onClose}
          className="p-2 rounded-xl bg-white hover:bg-slate-100 text-slate-500 hover:text-slate-900 transition-all border border-slate-200 shadow-xs"
          title="Close"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* HEADER TITLE BAR */}
      <header className="relative z-10 pt-6 pb-2 px-6 text-center shrink-0">
        <span className={`inline-flex items-center gap-2 px-4 py-1 rounded-full text-xs font-black tracking-widest uppercase mb-2 shadow-xs border ${
          allFailed ? 'bg-rose-50 text-rose-700 border-rose-200' :
          hasPartialErrors ? 'bg-amber-50 text-amber-700 border-amber-200' :
          'bg-white text-indigo-700 border-indigo-200'
        }`}>
          <Compass className="w-3.5 h-3.5 text-indigo-600" />
          Freight Rate Ingestion & Ship Cargo Blueprint
        </span>
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-black text-slate-900 tracking-tight">
          {showComplete
            ? (hasPartialErrors ? `Ship Cargo Pipeline Completed (${successCount} Succeeded, ${failedCount} Failed)` : allFailed ? 'Ingestion Pipeline Failed' : 'Cargo Rate Cards Parsed & Standardized!')
            : `Processing Rate Cards (${successCount + failedCount}/${files.length})`}
        </h1>
        <p className="text-xs sm:text-xs md:text-sm font-bold text-slate-500 mt-1 max-w-lg mx-auto truncate">
          {showComplete
            ? `Extracted and validated rates from ${successCount} file(s). ${failedCount > 0 ? `${failedCount} file(s) failed.` : ''}`
            : `Active Cargo: ${files[activeIndex]?.name || ''}`}
        </p>
      </header>

      {/* MAIN SHIP CARGO PIPELINE BLUEPRINT (Centered Vertically) */}
      <main className="relative z-10 flex-1 flex items-center justify-center min-h-0 px-4 sm:px-6 md:px-8 py-2 overflow-x-auto">
        <div className="w-full max-w-6xl mx-auto flex items-center justify-between gap-3 sm:gap-5 md:gap-8">
          
          {/* LEFT DOCK: Origin Cargo Ingestion */}
          <div className="w-56 sm:w-64 md:w-72 shrink-0 flex flex-col justify-center bg-white p-4 rounded-3xl border border-slate-200/90 shadow-xl shadow-slate-200/50">
            <div className="flex items-center justify-between mb-3 px-1">
              <span className="text-xs font-black text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <Anchor className="w-4 h-4 text-indigo-600" /> Origin Cargo Rates
              </span>
              <span className="text-[11px] font-black text-indigo-700 font-mono bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-100">
                {files.length} Rate Cards
              </span>
            </div>
            <div className="max-h-[260px] overflow-y-auto space-y-2.5 pr-1 custom-scrollbar">
              {files.map((f, i) => {
                const job = jobStates[jobIds[i]];
                const isFailed = job?.status === 'FAILED';
                const isDone = ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(job?.status);
                const isActive = (i === activeIndex || (!job && i <= activeIndex)) && !showComplete && !isFailed && !isDone;
                return (
                  <div
                    key={i}
                    className={`p-3 rounded-2xl border transition-all duration-300 flex items-center gap-3 ${
                      isFailed ? 'bg-rose-50/90 border-rose-300 shadow-xs' :
                      isDone ? 'bg-emerald-50/90 border-emerald-300 shadow-xs' :
                      isActive ? 'bg-white border-indigo-500 shadow-lg shadow-indigo-100 ring-2 ring-indigo-100 scale-[1.01]' :
                      'bg-slate-50 border-slate-200 opacity-60'
                    }`}
                  >
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-black text-xs shrink-0 ${
                      isFailed ? 'bg-rose-500 text-white shadow-xs' :
                      isDone ? 'bg-emerald-600 text-white shadow-xs' :
                      isActive ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200 animate-pulse' :
                      'bg-slate-200 text-slate-500'
                    }`}>
                      {isFailed ? <AlertCircle className="w-4 h-4" /> : isDone ? <CheckCircle2 className="w-4 h-4" /> : '📄'}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-black text-slate-900 truncate" title={f.name}>{f.name}</p>
                      <p className={`text-[10px] font-extrabold uppercase tracking-wider mt-0.5 ${
                        isFailed ? 'text-rose-600' : isDone ? 'text-emerald-700' : isActive ? 'text-indigo-600' : 'text-slate-400'
                      }`}>
                        {isFailed ? 'Error' : isDone ? 'Parsed ✓' : isActive ? 'Extracting...' : 'Queued'}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* LEFT PIPELINE CONNECTOR */}
          <div className="flex-1 min-w-[30px] flex flex-col items-center justify-center gap-1.5 self-center">
            <div className="w-full h-2.5 bg-indigo-100 rounded-full relative overflow-hidden shadow-inner border border-indigo-200/50">
              <div
                className={`absolute inset-y-0 rounded-full transition-all duration-300 ${
                  allFailed ? 'bg-rose-500' : 'bg-gradient-to-r from-indigo-500 via-sky-400 to-indigo-600'
                }`}
                style={{ width: `${simulatedProgress}%` }}
              />
            </div>
            <span className="text-[10px] font-black text-indigo-700 uppercase tracking-widest font-mono text-center truncate">
              {!showComplete ? 'In Transit →' : 'Loaded ✓'}
            </span>
          </div>

          {/* CENTER SHIP CORE NODE */}
          <div className="shrink-0 flex flex-col items-center justify-center relative self-center">
            <ShipBlueprintCore activeStage={currentStage} happy={showComplete && successCount > 0} hasFailed={allFailed} />
            <div className="mt-3 px-4 py-1.5 rounded-2xl bg-white border border-slate-200 shadow-md shadow-indigo-100 flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${allFailed ? 'bg-rose-500' : 'bg-emerald-500 animate-pulse'}`} />
              <span className="text-xs font-black text-slate-800">
                {allFailed ? 'Parsing Failed' : STAGES[currentStage]?.label}
              </span>
            </div>
          </div>

          {/* RIGHT PIPELINE CONNECTOR */}
          <div className="flex-1 min-w-[30px] flex flex-col items-center justify-center gap-1.5 self-center">
            <div className="w-full h-2.5 bg-emerald-100 rounded-full relative overflow-hidden shadow-inner border border-emerald-200/50">
              <div
                className={`absolute inset-y-0 rounded-full transition-all duration-300 ${
                  allFailed ? 'bg-rose-400' : 'bg-gradient-to-r from-indigo-500 via-sky-400 to-emerald-500'
                }`}
                style={{ width: `${simulatedProgress}%` }}
              />
            </div>
            <span className="text-[10px] font-black text-emerald-700 uppercase tracking-widest font-mono text-center truncate">
              {!showComplete ? '→ Standardizing' : 'Discharged ✓'}
            </span>
          </div>

          {/* RIGHT DOCK: Freightify Workbooks */}
          <div className="w-56 sm:w-64 md:w-72 shrink-0 flex flex-col justify-center bg-white p-4 rounded-3xl border border-slate-200/90 shadow-xl shadow-slate-200/50">
            <div className="flex items-center justify-between mb-3 px-1">
              <span className="text-xs font-black text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <FileSpreadsheet className="w-4 h-4 text-emerald-600" /> Freightify Deliverables
              </span>
              <span className="text-[11px] font-black text-emerald-700 font-mono bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                .XLSM
              </span>
            </div>
            <div className="max-h-[260px] overflow-y-auto space-y-2.5 pr-1 custom-scrollbar">
              {files.map((f, i) => {
                const job = jobStates[jobIds[i]];
                const isFailed = job?.status === 'FAILED';
                const isDone = ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(job?.status);
                return (
                  <div
                    key={i}
                    className={`p-3 rounded-2xl border transition-all duration-500 flex items-center gap-3 ${
                      isFailed ? 'bg-rose-50/90 border-rose-200' :
                      isDone ? 'bg-emerald-50/90 border-emerald-300 shadow-xs' :
                      'bg-slate-50 border-slate-200 opacity-50'
                    }`}
                  >
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-black text-xs shrink-0 ${
                      isFailed ? 'bg-rose-500 text-white' :
                      isDone ? 'bg-emerald-600 text-white shadow-xs' :
                      'bg-slate-200 text-slate-400'
                    }`}>
                      {isFailed ? '⚠️' : '📊'}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-black text-slate-900 truncate" title={`${f.name.replace(/\.[^/.]+$/, "")}_Freightify.xlsm`}>
                        {f.name.replace(/\.[^/.]+$/, "")}_Freightify.xlsm
                      </p>
                      <p className={`text-[10px] font-extrabold uppercase tracking-wider mt-0.5 flex items-center gap-1 ${
                        isFailed ? 'text-rose-600' : isDone ? 'text-emerald-700' : 'text-slate-400'
                      }`}>
                        {isFailed ? 'Failed' : isDone ? <><ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Validated</> : 'Waiting'}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

        </div>
      </main>

      {/* FOOTER ACTIONS */}
      <footer className="relative z-10 pb-8 pt-3 px-6 shrink-0 text-center bg-white/60 backdrop-blur-md border-t border-slate-200/60">
        <div className="flex justify-center items-center gap-3">
          <button
            onClick={() => setIsMinimized(true)}
            className="px-6 py-2.5 rounded-xl bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 font-bold text-sm transition-all shadow-xs"
          >
            Minimize
          </button>
          <button
            onClick={onClose}
            className="px-6 py-2.5 rounded-xl bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 font-bold text-sm transition-all shadow-xs"
          >
            Close
          </button>
          {jobIds.length > 0 && successCount > 0 && (
            <button
              onClick={() => {
                const firstSuccessId = jobIds.find((id) => ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(jobStates[id]?.status)) || jobIds[0];
                onInspectJob(firstSuccessId);
                onClose();
              }}
              className="btn-shiny-indigo text-sm py-2.5 px-6 rounded-xl shadow-lg shadow-indigo-100"
            >
              Inspect Converted Rate Cards <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </footer>
    </div>,
    document.body
  );
};
