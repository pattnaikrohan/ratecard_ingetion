import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { 
  ArrowRight, 
  X, 
  Minus, 
  Maximize2, 
  CheckCircle2, 
  ShieldCheck, 
  FileSpreadsheet, 
  AlertCircle, 
  Ship, 
  Anchor, 
  Sparkles
} from 'lucide-react';
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
  { label: 'Ingesting Rate Cards', desc: 'Parsing EML, PDF, PNG & Excel files' },
  { label: 'Carrier SCAC Recognition', desc: 'Auto-detecting ocean carrier code' },
  { label: 'Matrix Unpivoting', desc: 'Mapping 20GP, 40GP, 40HC, 45GP, DG' },
  { label: '13,670 UNLOCODE Alignment', desc: 'Matching origin & destination ports' },
  { label: 'Freightify .xlsm Generation', desc: 'Building standardized upload sheet' },
];

/* ── Posh RateBridge Core Graphic (Frosted Teal Glass & Orbital Bloom) ── */
const RateBridgeCore: React.FC<{ activeStage: number; happy?: boolean; hasFailed?: boolean }> = ({ activeStage, happy, hasFailed }) => (
  <div className="relative w-56 h-56 sm:w-64 sm:h-64 md:w-72 md:h-72 flex flex-col items-center justify-center select-none shrink-0">
    
    {/* Ambient Glow Aura */}
    <div className={`absolute inset-0 rounded-full blur-3xl opacity-50 ${
      hasFailed 
        ? 'bg-rose-400/30' 
        : happy 
        ? 'bg-emerald-400/30' 
        : 'bg-gradient-to-tr from-[#00AFAF]/40 via-teal-300/30 to-sky-300/30'
    }`} />

    {/* Outer Orbital Compass Ring */}
    <div 
      className={`absolute inset-2 rounded-full border-2 border-dashed ${
        hasFailed ? 'border-rose-300' : 'border-[#00AFAF]/40'
      }`}
      style={{ animation: 'spin-slow 24s linear infinite' }}
    />

    {/* Inner Glass Nav Ring */}
    <div className="absolute inset-8 rounded-full border border-teal-200/80 bg-white/60 backdrop-blur-md shadow-inner" />

    {/* Central Luxury Node Card */}
    <div className="relative w-36 h-36 sm:w-40 sm:h-40 md:w-44 md:h-44 rounded-3xl bg-white border border-slate-200/90 shadow-2xl shadow-teal-900/5 flex flex-col items-center justify-center p-4 text-center">
      {hasFailed ? (
        <div className="flex flex-col items-center gap-2 animate-bounce">
          <div className="w-12 h-12 rounded-2xl bg-rose-500 text-white flex items-center justify-center shadow-lg shadow-rose-200">
            <AlertCircle className="w-6 h-6" />
          </div>
          <span className="text-xs font-black text-rose-600 uppercase tracking-wider">Parsing Error</span>
        </div>
      ) : happy ? (
        <div className="flex flex-col items-center gap-2 animate-bounce">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500 text-white flex items-center justify-center shadow-lg shadow-emerald-200">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <span className="text-xs font-black text-emerald-600 uppercase tracking-wider">Standardized ✓</span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <div className="relative">
            <div 
              style={{ backgroundColor: '#00AFAF' }}
              className="w-12 h-12 rounded-2xl text-white flex items-center justify-center shadow-lg shadow-[#00AFAF]/25"
            >
              <Ship className="w-6 h-6 text-white animate-pulse" />
            </div>
            <div className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-white animate-ping" />
          </div>
          <div className="space-y-0.5">
            <span className="text-[10px] font-black uppercase tracking-widest text-[#008f8f] font-mono bg-[#00AFAF]/10 px-2.5 py-0.5 rounded-full border border-[#00AFAF]/20 inline-block truncate max-w-[130px]">
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
          } catch {
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

  // Calculate total extracted rates across jobs
  const totalExtractedRates = jobIds.reduce((sum, id) => {
    const j = jobStates[id];
    return sum + (j?.total_rows || j?.summary?.total_rows || j?.canonical?.rates?.length || 0);
  }, 0);

  const displayProgress = showComplete ? 100 : Math.max(simulatedProgress, showComplete ? 100 : 10);
  const currentStage = displayProgress < 20 ? 0 : displayProgress < 40 ? 1 : displayProgress < 60 ? 2 : displayProgress < 80 ? 3 : 4;

  // ── MINIMIZED WIDGET DOCK (Bottom Right) ──
  if (isMinimized) {
    return createPortal(
      <div className="fixed bottom-6 right-6 z-[9999] bg-white/95 backdrop-blur-xl border border-slate-200/90 shadow-[0_8px_32px_rgba(0,0,0,0.12)] rounded-3xl p-4 flex items-center gap-4 animate-fade-in select-none max-w-md">
        <div 
          style={{ backgroundColor: '#00AFAF' }}
          className={`w-11 h-11 rounded-2xl text-white flex items-center justify-center shrink-0 shadow-md ${
            allFailed ? 'bg-rose-500 shadow-rose-200' : 'shadow-[#00AFAF]/25'
          }`}
        >
          {allFailed ? <AlertCircle className="w-5 h-5" /> : <Ship className="w-5 h-5 animate-pulse" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-black text-slate-900 truncate">
              {showComplete
                ? (hasPartialErrors ? `Batch Ingested (${successCount} Passed, ${failedCount} Failed)` : 'Ingestion Complete ✓')
                : `Rate Pipeline Active (${successCount + failedCount}/${files.length})`}
            </span>
            <span className="text-xs font-black text-[#00AFAF] font-mono">{displayProgress}%</span>
          </div>
          <div className="w-full h-2 bg-slate-100 rounded-full mt-1.5 overflow-hidden border border-slate-200/60">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                allFailed ? 'bg-rose-500' : showComplete ? 'bg-emerald-500' : 'bg-gradient-to-r from-[#00AFAF] to-teal-500'
              }`}
              style={{ width: `${displayProgress}%` }}
            />
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setIsMinimized(false)}
            className="p-2 rounded-xl hover:bg-slate-100 text-slate-500 hover:text-slate-900 transition-colors"
            title="Maximize overlay"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-slate-100 text-slate-400 hover:text-rose-600 transition-colors"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>,
      document.body
    );
  }

  // ── FULL SCREEN LUXURY SHIP BLUEPRINT MODAL ──
  return createPortal(
    <div className="fixed inset-0 top-0 left-0 w-screen h-screen z-[9999] overflow-hidden flex flex-col justify-between select-none animate-fade-in bg-[#f8fafc]">
      
      {/* Background Subtle Ambient Aura */}
      <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-gradient-to-bl from-[#00AFAF]/12 via-teal-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-gradient-to-tr from-sky-500/8 via-[#00AFAF]/5 to-transparent rounded-full blur-3xl pointer-events-none" />

      {/* Top Header Controls */}
      <div className="absolute top-6 right-8 z-50 flex items-center gap-2.5">
        <button
          onClick={() => setIsMinimized(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-2xl bg-white hover:bg-slate-50 text-slate-700 font-black text-xs transition-all border border-slate-200/90 shadow-2xs"
          title="Minimize to bottom dock"
        >
          <Minus className="w-3.5 h-3.5 text-slate-500" /> Minimize
        </button>
        <button
          onClick={onClose}
          className="p-2 rounded-2xl bg-white hover:bg-slate-50 text-slate-500 hover:text-slate-900 transition-all border border-slate-200/90 shadow-2xs"
          title="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* ── TOP HERO TITLE BAR ── */}
      <header className="relative z-10 pt-8 pb-2 px-6 text-center shrink-0">
        <span className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-black tracking-widest uppercase mb-3 shadow-2xs border ${
          allFailed ? 'bg-rose-50 text-rose-700 border-rose-200' :
          hasPartialErrors ? 'bg-amber-50 text-amber-700 border-amber-200' :
          'bg-white text-[#008f8f] border-[#00AFAF]/25 bg-[#00AFAF]/10'
        }`}>
          <Sparkles className="w-3.5 h-3.5 text-[#00AFAF]" />
          RateBridge Autonomous Conversion Blueprint
        </span>

        <h1 className="text-2xl sm:text-3xl md:text-4xl font-black text-slate-900 tracking-tight">
          {showComplete
            ? (hasPartialErrors ? `Pipeline Complete (${successCount} Succeeded, ${failedCount} Failed)` : allFailed ? 'Ingestion Pipeline Failed' : 'Cargo Rate Cards Parsed & Standardized!')
            : `Standardizing Rate Cards (${successCount + failedCount}/${files.length})`}
        </h1>

        <p className="text-xs sm:text-xs md:text-sm font-medium text-slate-500 mt-1 max-w-lg mx-auto truncate">
          {showComplete
            ? `Successfully unpivoted and validated ${totalExtractedRates.toLocaleString('en-US')} rate rows from ${successCount} file(s).`
            : `Active Cargo: ${files[activeIndex]?.name || ''}`}
        </p>
      </header>

      {/* ── MAIN 3-STAGE CONVEYOR PIPELINE ── */}
      <main className="relative z-10 flex-1 flex items-center justify-center min-h-0 px-4 sm:px-6 md:px-8 py-2 overflow-x-auto">
        <div className="w-full max-w-6xl mx-auto flex items-center justify-between gap-3 sm:gap-5 md:gap-8">
          
          {/* LEFT DOCK: Origin Cargo Ingestion Card */}
          <div className="w-56 sm:w-64 md:w-72 shrink-0 flex flex-col justify-center bg-white p-5 rounded-3xl border border-slate-200/90 shadow-xl shadow-slate-200/50 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-[#00AFAF] to-teal-600" />
            
            <div className="flex items-center justify-between mb-3.5 px-1">
              <span className="text-xs font-black text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Anchor className="w-4 h-4 text-[#00AFAF]" /> Origin Rate Cards
              </span>
              <span className="text-[11px] font-black text-[#008f8f] font-mono bg-[#00AFAF]/10 px-2.5 py-0.5 rounded-full border border-[#00AFAF]/20">
                {files.length} Files
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
                      isFailed ? 'bg-rose-50/90 border-rose-300 shadow-2xs' :
                      isDone ? 'bg-emerald-50/90 border-emerald-300 shadow-2xs' :
                      isActive ? 'bg-white border-[#00AFAF] shadow-lg shadow-[#00AFAF]/10 ring-2 ring-[#00AFAF]/20 scale-[1.01]' :
                      'bg-slate-50 border-slate-200 opacity-60'
                    }`}
                  >
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-black text-xs shrink-0 ${
                      isFailed ? 'bg-rose-500 text-white shadow-2xs' :
                      isDone ? 'bg-emerald-600 text-white shadow-2xs' :
                      isActive ? 'bg-[#00AFAF] text-white shadow-md shadow-[#00AFAF]/25 animate-pulse' :
                      'bg-slate-200 text-slate-500'
                    }`}>
                      {isFailed ? <AlertCircle className="w-4 h-4" /> : isDone ? <CheckCircle2 className="w-4 h-4" /> : '📄'}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-black text-slate-900 truncate" title={f.name}>{f.name}</p>
                      <p className={`text-[10px] font-black uppercase tracking-wider mt-0.5 ${
                        isFailed ? 'text-rose-600' : isDone ? 'text-emerald-700' : isActive ? 'text-[#008f8f]' : 'text-slate-400'
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
            <div className="w-full h-2.5 bg-slate-100 rounded-full relative overflow-hidden shadow-inner border border-slate-200/80">
              <div
                className={`absolute inset-y-0 rounded-full transition-all duration-300 ${
                  allFailed ? 'bg-rose-500' : 'bg-gradient-to-r from-[#00AFAF] via-teal-400 to-[#00AFAF]'
                }`}
                style={{ width: `${simulatedProgress}%` }}
              />
            </div>
            <span className="text-[10px] font-black text-[#008f8f] uppercase tracking-widest font-mono text-center truncate">
              {!showComplete ? 'In Transit →' : 'Loaded ✓'}
            </span>
          </div>

          {/* CENTER SHIP CORE NODE */}
          <div className="shrink-0 flex flex-col items-center justify-center relative self-center">
            <RateBridgeCore activeStage={currentStage} happy={showComplete && successCount > 0} hasFailed={allFailed} />
            <div className="mt-3 px-4 py-1.5 rounded-2xl bg-white border border-slate-200/90 shadow-md shadow-slate-200/40 flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${allFailed ? 'bg-rose-500' : 'bg-emerald-500 animate-pulse'}`} />
              <span className="text-xs font-black text-slate-800">
                {allFailed ? 'Parsing Failed' : STAGES[currentStage]?.label}
              </span>
            </div>
          </div>

          {/* RIGHT PIPELINE CONNECTOR */}
          <div className="flex-1 min-w-[30px] flex flex-col items-center justify-center gap-1.5 self-center">
            <div className="w-full h-2.5 bg-emerald-50 rounded-full relative overflow-hidden shadow-inner border border-emerald-200/60">
              <div
                className={`absolute inset-y-0 rounded-full transition-all duration-300 ${
                  allFailed ? 'bg-rose-400' : 'bg-gradient-to-r from-[#00AFAF] via-teal-400 to-emerald-500'
                }`}
                style={{ width: `${simulatedProgress}%` }}
              />
            </div>
            <span className="text-[10px] font-black text-emerald-700 uppercase tracking-widest font-mono text-center truncate">
              {!showComplete ? '→ Standardizing' : 'Discharged ✓'}
            </span>
          </div>

          {/* RIGHT DOCK: Freightify Workbooks Card */}
          <div className="w-56 sm:w-64 md:w-72 shrink-0 flex flex-col justify-center bg-white p-5 rounded-3xl border border-slate-200/90 shadow-xl shadow-slate-200/50 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 to-teal-600" />
            
            <div className="flex items-center justify-between mb-3.5 px-1">
              <span className="text-xs font-black text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <FileSpreadsheet className="w-4 h-4 text-emerald-600" /> Freightify Exports
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
                      isDone ? 'bg-emerald-50/90 border-emerald-300 shadow-2xs' :
                      'bg-slate-50 border-slate-200 opacity-50'
                    }`}
                  >
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-black text-xs shrink-0 ${
                      isFailed ? 'bg-rose-500 text-white' :
                      isDone ? 'bg-emerald-600 text-white shadow-2xs' :
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

      {/* ── FOOTER ACTIONS ── */}
      <footer className="relative z-10 pb-8 pt-4 px-6 shrink-0 text-center bg-white/70 backdrop-blur-xl border-t border-slate-200/80">
        <div className="flex justify-center items-center gap-3">
          <button
            onClick={() => setIsMinimized(true)}
            className="px-6 py-2.5 rounded-2xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 font-black text-xs transition-all shadow-2xs"
          >
            Minimize
          </button>
          <button
            onClick={onClose}
            className="px-6 py-2.5 rounded-2xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 font-black text-xs transition-all shadow-2xs"
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
              style={{ backgroundColor: '#00AFAF' }}
              className="px-6 py-2.5 rounded-2xl text-white font-black text-xs transition-all shadow-md shadow-[#00AFAF]/20 hover:brightness-105 inline-flex items-center gap-2"
            >
              <span>Inspect Converted Rate Cards</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </footer>
    </div>,
    document.body
  );
};
