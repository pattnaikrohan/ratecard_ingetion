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
  Sparkles,
  Zap,
  Globe2,
  FileText
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
  { label: 'Ingesting Rate Cards', desc: 'Parsing EML, PDF, PNG & Excel files', tag: 'INGEST' },
  { label: 'Carrier SCAC Recognition', desc: 'Auto-detecting ocean carrier code', tag: 'CARRIER' },
  { label: 'Matrix Unpivoting', desc: 'Mapping 20GP, 40GP, 40HC, 45GP, DG', tag: 'MATRIX' },
  { label: '13,670 UNLOCODE Alignment', desc: 'Matching origin & destination ports', tag: 'UNLOCODE' },
  { label: 'Freightify .xlsm Generation', desc: 'Building standardized upload sheet', tag: 'FREIGHTIFY' },
];

/* ── Posh Holographic AI Core Graphic (Frosted Teal Glass, Dual Orbital Rings & Dynamic Live Metrics) ── */
const RateBridgeCore: React.FC<{ 
  activeStage: number; 
  happy?: boolean; 
  hasFailed?: boolean;
  totalRates: number;
}> = ({ activeStage, happy, hasFailed, totalRates }) => (
  <div className="relative w-64 h-64 sm:w-72 sm:h-72 md:w-80 md:h-80 flex flex-col items-center justify-center select-none shrink-0">
    
    {/* Volumetric Glowing Ambient Aura */}
    <div className={`absolute inset-0 rounded-full blur-3xl opacity-60 transition-all duration-700 ${
      hasFailed 
        ? 'bg-rose-500/25' 
        : happy 
        ? 'bg-emerald-400/35' 
        : 'bg-gradient-to-tr from-[#00AFAF]/45 via-teal-400/30 to-sky-400/30'
    }`} />

    {/* Outer Orbital Compass Ring (Clockwise) */}
    <div 
      className={`absolute inset-1 rounded-full border-2 border-dashed transition-colors duration-500 ${
        hasFailed ? 'border-rose-300/80' : happy ? 'border-emerald-300/80' : 'border-[#00AFAF]/50'
      }`}
      style={{ animation: 'spin-slow 22s linear infinite' }}
    />

    {/* Inner Counter-Rotating Precision Ring (Counter-Clockwise) */}
    <div 
      className="absolute inset-6 rounded-full border border-dashed border-teal-300/40"
      style={{ animation: 'spin-reverse 16s linear infinite' }}
    />

    {/* Inner Frosted Glass Nav Orb */}
    <div className="absolute inset-9 rounded-full border border-teal-200/80 bg-white/70 backdrop-blur-xl shadow-[inset_0_2px_12px_rgba(0,175,175,0.1)]" />

    {/* Central Luxury Porcelain Core Node */}
    <div className="relative w-44 h-44 sm:w-48 sm:h-48 rounded-[36px] bg-white border border-slate-200/90 shadow-[0_20px_50px_rgba(0,175,175,0.12)] flex flex-col items-center justify-center p-5 text-center transition-all duration-500">
      {hasFailed ? (
        <div className="flex flex-col items-center gap-2 animate-bounce">
          <div className="w-14 h-14 rounded-2xl bg-rose-500 text-white flex items-center justify-center shadow-lg shadow-rose-200">
            <AlertCircle className="w-7 h-7" />
          </div>
          <span className="text-xs font-black text-rose-600 uppercase tracking-wider">Parsing Error</span>
        </div>
      ) : happy ? (
        <div className="flex flex-col items-center gap-2">
          <div className="relative">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500 text-white flex items-center justify-center shadow-lg shadow-emerald-200 animate-pulse">
              <CheckCircle2 className="w-7 h-7" />
            </div>
            <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-[#00AFAF] border-2 border-white animate-ping" />
          </div>
          <div className="space-y-0.5 mt-1">
            <span className="text-[11px] font-black text-emerald-700 uppercase tracking-widest font-mono bg-emerald-50 px-3 py-0.5 rounded-full border border-emerald-200 inline-block">
              Standardized ✓
            </span>
            <p className="text-[10px] text-slate-500 font-bold">
              {totalRates.toLocaleString('en-US')} Rates Validated
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <div className="relative">
            <div 
              style={{ backgroundColor: '#00AFAF' }}
              className="w-13 h-13 rounded-2xl text-white flex items-center justify-center shadow-lg shadow-[#00AFAF]/30"
            >
              <Ship className="w-7 h-7 text-white animate-pulse" />
            </div>
            <div className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-white animate-ping" />
          </div>
          
          <div className="space-y-1">
            <span className="text-[10px] font-black uppercase tracking-widest text-[#008f8f] font-mono bg-[#00AFAF]/10 px-3 py-0.5 rounded-full border border-[#00AFAF]/20 inline-block truncate max-w-[150px]">
              {STAGES[activeStage]?.label || 'Standardizing'}
            </span>
            <p className="text-[10px] text-slate-400 font-bold truncate max-w-[150px]">
              {STAGES[activeStage]?.desc}
            </p>
          </div>
        </div>
      )}
    </div>

    <style>{`
      @keyframes spin-slow { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      @keyframes spin-reverse { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
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

  // Continuous parallel polling for active job statuses
  useEffect(() => {
    if (!isOpen || files.length === 0) return;

    const poll = setInterval(async () => {
      const validIds = jobIds.filter((id) => id && !id.startsWith('failed_'));
      if (validIds.length === 0) return;
      try {
        const promises = validIds.map(async (id) => {
          try {
            const data = await api.getJob(id);
            return [id, data];
          } catch {
            return [id, { status: 'FAILED', progress: 100, log_msg: 'Server error fetching job.' }];
          }
        });
        const results = await Promise.all(promises);
        setJobStates((prev) => {
          const next = { ...prev };
          results.forEach(([id, data]) => {
            if (id) next[id as string] = data;
          });
          return next;
        });
      } catch { /* silent */ }
    }, 600);

    return () => { clearInterval(poll); };
  }, [isOpen, files.length, jobIds]);

  // Accurate Multi-File Batch Progress Calculation:
  // Each file represents (100 / totalFiles)% of the overall progress
  const totalFiles = Math.max(1, files.length);

  const { computedBatchProgress, allJobsFinished, finishedCount, failedCount, successCount } = React.useMemo(() => {
    if (files.length === 0) {
      return { computedBatchProgress: 0, allJobsFinished: false, finishedCount: 0, failedCount: 0, successCount: 0 };
    }

    let progressSum = 0;
    let finished = 0;
    let failed = 0;
    let success = 0;

    for (let i = 0; i < files.length; i++) {
      const jobId = jobIds[i];

      // If job not yet assigned
      if (!jobId) {
        if (i < activeIndex) {
          progressSum += 80;
        } else if (i === activeIndex) {
          progressSum += 25;
        } else {
          progressSum += 0;
        }
        continue;
      }

      // Explicit upload failure
      if (jobId.startsWith('failed_')) {
        failed++;
        finished++;
        progressSum += 100;
        continue;
      }

      const job = jobStates[jobId];
      if (!job) {
        if (i < activeIndex) progressSum += 85;
        else if (i === activeIndex) progressSum += 35;
        continue;
      }

      const status = job.status;
      const isDone = ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(status);
      const isFail = status === 'FAILED';

      if (isDone) {
        success++;
        finished++;
        progressSum += 100;
      } else if (isFail) {
        failed++;
        finished++;
        progressSum += 100;
      } else {
        const itemProg = typeof job.progress === 'number' ? job.progress : (i === activeIndex ? 50 : 20);
        progressSum += Math.max(15, Math.min(95, itemProg));
      }
    }

    const allFinished = finished === files.length && jobIds.length === files.length && jobIds.every(Boolean);
    const overallPct = allFinished ? 100 : Math.min(99, Math.round(progressSum / totalFiles));

    return {
      computedBatchProgress: Math.max(overallPct, files.length > 0 ? 5 : 0),
      allJobsFinished: allFinished,
      finishedCount: finished,
      failedCount: failed,
      successCount: success,
    };
  }, [files.length, jobIds, jobStates, activeIndex, totalFiles]);

  // Synchronize smooth progress transition
  useEffect(() => {
    if (allJobsFinished) {
      setShowComplete(true);
      setSimulatedProgress(100);
    } else {
      setSimulatedProgress(computedBatchProgress);
    }
  }, [allJobsFinished, computedBatchProgress]);

  if (!isOpen) return null;

  const allFailed = files.length > 0 && failedCount === files.length;
  const hasPartialErrors = failedCount > 0 && !allFailed;

  // Calculate total extracted rates across jobs
  const totalExtractedRates = jobIds.reduce((sum, id) => {
    const j = jobStates[id];
    return sum + (j?.total_rows || j?.summary?.total_rows || j?.canonical?.rates?.length || 0);
  }, 0);

  const displayProgress = showComplete ? 100 : simulatedProgress;
  const currentStage = displayProgress < 20 ? 0 : displayProgress < 40 ? 1 : displayProgress < 60 ? 2 : displayProgress < 80 ? 3 : 4;

  // ── MINIMIZED WIDGET DOCK (Bottom Right) ──
  if (isMinimized) {
    return createPortal(
      <div className="fixed bottom-6 right-6 z-[9999] bg-white/95 backdrop-blur-xl border border-slate-200/90 shadow-[0_12px_40px_rgba(0,175,175,0.16)] rounded-3xl p-4 flex items-center gap-4 animate-fade-in select-none max-w-md">
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
                : `Rate Pipeline Active (${finishedCount}/${files.length})`}
            </span>
            <span className="text-xs font-black text-[#00AFAF] font-mono">{displayProgress}%</span>
          </div>
          <div className="w-full h-2 bg-slate-100 rounded-full mt-1.5 overflow-hidden border border-slate-200/60">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                allFailed ? 'bg-rose-500' : showComplete ? 'bg-emerald-500' : 'bg-gradient-to-r from-[#00AFAF] via-teal-400 to-emerald-400'
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
      
      {/* Background Volumetric Ambient Lighting */}
      <div className="absolute top-0 right-0 w-[700px] h-[700px] bg-gradient-to-bl from-[#00AFAF]/15 via-teal-500/8 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[700px] h-[700px] bg-gradient-to-tr from-sky-500/10 via-[#00AFAF]/8 to-transparent rounded-full blur-3xl pointer-events-none" />

      {/* Top Header Window Controls */}
      <div className="absolute top-6 right-8 z-50 flex items-center gap-2.5">
        <button
          onClick={() => setIsMinimized(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-2xl bg-white/90 hover:bg-white text-slate-700 font-black text-xs transition-all border border-slate-200/90 shadow-2xs backdrop-blur-md"
          title="Minimize to bottom dock"
        >
          <Minus className="w-3.5 h-3.5 text-slate-500" /> Minimize
        </button>
        <button
          onClick={onClose}
          className="p-2 rounded-2xl bg-white/90 hover:bg-white text-slate-500 hover:text-slate-900 transition-all border border-slate-200/90 shadow-2xs backdrop-blur-md"
          title="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* ── TOP HERO TITLE & EXECUTIVE STATS BAR ── */}
      <header className="relative z-10 pt-8 pb-2 px-6 text-center shrink-0">
        <div className="flex justify-center items-center gap-2 mb-2.5">
          <span className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-black tracking-widest uppercase shadow-2xs border ${
            allFailed ? 'bg-rose-50 text-rose-700 border-rose-200' :
            hasPartialErrors ? 'bg-amber-50 text-amber-700 border-amber-200' :
            'text-[#008f8f] border-[#00AFAF]/25 bg-[#00AFAF]/10'
          }`}>
            <Sparkles className="w-3.5 h-3.5 text-[#00AFAF]" />
            RateBridge Autonomous Conversion Blueprint
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl md:text-4xl font-black text-slate-900 tracking-tight">
          {showComplete
            ? (hasPartialErrors ? `Pipeline Completed (${successCount} Succeeded, ${failedCount} Failed)` : allFailed ? 'Ingestion Pipeline Failed' : 'Cargo Rate Cards Parsed & Standardized!')
            : `Autonomous Rate Standardization (${finishedCount}/${files.length})`}
        </h1>

        {/* Live Metric Chips Ribbon */}
        <div className="flex flex-wrap items-center justify-center gap-2.5 mt-3">
          <span className="px-3 py-1 rounded-xl bg-white border border-slate-200 text-slate-700 font-mono text-xs font-black shadow-2xs flex items-center gap-1.5">
            <FileText className="w-3.5 h-3.5 text-[#00AFAF]" />
            {files.length} Files Ingested
          </span>
          <span className="px-3 py-1 rounded-xl bg-white border border-slate-200 text-slate-700 font-mono text-xs font-black shadow-2xs flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-amber-500" />
            {totalExtractedRates.toLocaleString('en-US')} Rates Extracted
          </span>
          <span className="px-3 py-1 rounded-xl bg-white border border-slate-200 text-slate-700 font-mono text-xs font-black shadow-2xs flex items-center gap-1.5">
            <Globe2 className="w-3.5 h-3.5 text-emerald-600" />
            13,670 UNLOCODE Aligned
          </span>
          <span className="px-3 py-1 rounded-xl bg-[#00AFAF]/10 border border-[#00AFAF]/25 text-[#008f8f] font-mono text-xs font-black shadow-2xs">
            {displayProgress}% Overall Progress
          </span>
        </div>
      </header>

      {/* ── MAIN 3-STAGE CONVEYOR PIPELINE ── */}
      <main className="relative z-10 flex-1 flex items-center justify-center min-h-0 px-4 sm:px-6 md:px-8 py-2 overflow-x-auto">
        <div className="w-full max-w-6xl mx-auto flex items-center justify-between gap-3 sm:gap-6 md:gap-8">
          
          {/* ── LEFT DOCK: Origin Cargo Ingestion Card ── */}
          <div className="w-60 sm:w-72 md:w-80 shrink-0 flex flex-col justify-center bg-white/95 backdrop-blur-2xl p-5 rounded-[32px] border border-slate-200/90 shadow-[0_16px_40px_-8px_rgba(0,175,175,0.08)] relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-[#00AFAF] via-teal-400 to-[#00AFAF]" />
            
            <div className="flex items-center justify-between mb-3.5 px-1">
              <span className="text-xs font-black text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Anchor className="w-4 h-4 text-[#00AFAF]" /> Origin Rate Cards
              </span>
              <span className="text-[11px] font-black text-[#008f8f] font-mono bg-[#00AFAF]/10 px-2.5 py-0.5 rounded-full border border-[#00AFAF]/20">
                {files.length} Files
              </span>
            </div>

            <div className="max-h-[270px] overflow-y-auto space-y-2.5 pr-1 custom-scrollbar">
              {files.map((f, i) => {
                const jobId = jobIds[i];
                const job = jobId ? jobStates[jobId] : null;
                const isFailed = jobId?.startsWith('failed_') || job?.status === 'FAILED';
                const isDone = ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(job?.status) || (showComplete && !isFailed);
                const isActive = !isDone && !isFailed && (i === activeIndex || (!job && i <= activeIndex));
                const ext = f.name.split('.').pop()?.toUpperCase() || 'FILE';
                const ratesCount = job?.total_rows || job?.summary?.total_rows || (job?.canonical?.rates || []).length || 0;

                return (
                  <div
                    key={i}
                    className={`p-3 rounded-2xl border transition-all duration-300 flex items-center gap-3 ${
                      isFailed ? 'bg-rose-50/90 border-rose-300 shadow-2xs' :
                      isDone ? 'bg-emerald-50/80 border-emerald-300/80 shadow-2xs' :
                      isActive ? 'bg-white border-2 border-[#00AFAF] shadow-lg shadow-[#00AFAF]/15 ring-4 ring-[#00AFAF]/10 scale-[1.02]' :
                      'bg-slate-50 border-slate-200 opacity-60'
                    }`}
                  >
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-black text-xs shrink-0 ${
                      isFailed ? 'bg-rose-500 text-white shadow-2xs' :
                      isDone ? 'bg-emerald-600 text-white shadow-2xs' :
                      isActive ? 'bg-[#00AFAF] text-white shadow-md shadow-[#00AFAF]/30 animate-pulse' :
                      'bg-slate-200 text-slate-500'
                    }`}>
                      {isFailed ? <AlertCircle className="w-4 h-4" /> : isDone ? <CheckCircle2 className="w-4 h-4" /> : ext}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-1">
                        <p className="text-xs font-black text-slate-900 truncate" title={f.name}>{f.name}</p>
                        <span className="text-[9px] font-mono font-bold text-slate-400 uppercase shrink-0">.{ext}</span>
                      </div>
                      <p className={`text-[10px] font-black uppercase tracking-wider mt-0.5 flex items-center gap-1 ${
                        isFailed ? 'text-rose-600' : isDone ? 'text-emerald-700' : isActive ? 'text-[#008f8f]' : 'text-slate-400'
                      }`}>
                        {isFailed ? '● Error' : isDone ? `● Parsed (${ratesCount > 0 ? `${ratesCount} Rates` : 'Done'})` : isActive ? '● Extracting Matrices...' : 'Queued'}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── LEFT PIPELINE CONNECTOR ── */}
          <div className="flex-1 min-w-[36px] flex flex-col items-center justify-center gap-2 self-center">
            <div className="w-full h-3 bg-slate-100 rounded-full relative overflow-hidden shadow-inner border border-slate-200/80">
              <div
                className={`absolute inset-y-0 rounded-full transition-all duration-500 ${
                  allFailed ? 'bg-rose-500' : 'bg-gradient-to-r from-[#00AFAF] via-teal-400 to-[#00AFAF]'
                }`}
                style={{ width: `${displayProgress}%` }}
              />
            </div>
            <span className="text-[10px] font-black text-[#008f8f] uppercase tracking-widest font-mono text-center px-2 py-0.5 rounded-full bg-[#00AFAF]/10 border border-[#00AFAF]/20 shadow-2xs">
              {!showComplete ? '⚡ Unpivoting' : 'Loaded ✓'}
            </span>
          </div>

          {/* ── CENTER HOLOGRAPHIC SHIP AI NODE ── */}
          <div className="shrink-0 flex flex-col items-center justify-center relative self-center">
            <RateBridgeCore 
              activeStage={currentStage} 
              happy={showComplete && successCount > 0} 
              hasFailed={allFailed}
              totalRates={totalExtractedRates}
            />
            
            <div className="mt-3 px-4 py-1.5 rounded-2xl bg-white border border-slate-200/90 shadow-md shadow-[#00AFAF]/10 flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${allFailed ? 'bg-rose-500' : 'bg-emerald-500 animate-pulse'}`} />
              <span className="text-xs font-black text-slate-800">
                {allFailed ? 'Parsing Interrupted' : STAGES[currentStage]?.label}
              </span>
            </div>
          </div>

          {/* ── RIGHT PIPELINE CONNECTOR ── */}
          <div className="flex-1 min-w-[36px] flex flex-col items-center justify-center gap-2 self-center">
            <div className="w-full h-3 bg-emerald-50 rounded-full relative overflow-hidden shadow-inner border border-emerald-200/60">
              <div
                className={`absolute inset-y-0 rounded-full transition-all duration-500 ${
                  allFailed ? 'bg-rose-400' : 'bg-gradient-to-r from-[#00AFAF] via-teal-400 to-emerald-500'
                }`}
                style={{ width: `${displayProgress}%` }}
              />
            </div>
            <span className="text-[10px] font-black text-emerald-700 uppercase tracking-widest font-mono text-center px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 shadow-2xs">
              {!showComplete ? '🌐 13,670 Ports' : 'Discharged ✓'}
            </span>
          </div>

          {/* ── RIGHT DOCK: Freightify Workbooks Card ── */}
          <div className="w-60 sm:w-72 md:w-80 shrink-0 flex flex-col justify-center bg-white/95 backdrop-blur-2xl p-5 rounded-[32px] border border-slate-200/90 shadow-[0_16px_40px_-8px_rgba(0,175,175,0.08)] relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-600" />
            
            <div className="flex items-center justify-between mb-3.5 px-1">
              <span className="text-xs font-black text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <FileSpreadsheet className="w-4 h-4 text-emerald-600" /> Freightify Exports
              </span>
              <span className="text-[11px] font-black text-emerald-700 font-mono bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                .XLSM Deliverables
              </span>
            </div>

            <div className="max-h-[270px] overflow-y-auto space-y-2.5 pr-1 custom-scrollbar">
              {files.map((f, i) => {
                const jobId = jobIds[i];
                const job = jobId ? jobStates[jobId] : null;
                const isFailed = jobId?.startsWith('failed_') || job?.status === 'FAILED';
                const isDone = ['COMPLETED', 'NEEDS_REVIEW', 'APPROVED'].includes(job?.status) || (showComplete && !isFailed);
                const outName = `${f.name.replace(/\.[^/.]+$/, "")}_Freightify.xlsm`;

                return (
                  <div
                    key={i}
                    className={`p-3 rounded-2xl border transition-all duration-500 flex items-center gap-3 ${
                      isFailed ? 'bg-rose-50/90 border-rose-200' :
                      isDone ? 'bg-emerald-50/80 border-emerald-300/80 shadow-2xs' :
                      'bg-slate-50 border-slate-200 opacity-50'
                    }`}
                  >
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-black text-xs shrink-0 ${
                      isFailed ? 'bg-rose-500 text-white' :
                      isDone ? 'bg-emerald-600 text-white shadow-2xs' :
                      'bg-slate-200 text-slate-400'
                    }`}>
                      {isFailed ? <AlertCircle className="w-4 h-4" /> : isDone ? <ShieldCheck className="w-4 h-4" /> : '📊'}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-black text-slate-900 truncate" title={outName}>
                        {outName}
                      </p>
                      <p className={`text-[10px] font-extrabold uppercase tracking-wider mt-0.5 flex items-center gap-1 ${
                        isFailed ? 'text-rose-600' : isDone ? 'text-emerald-700' : 'text-slate-400'
                      }`}>
                        {isFailed ? '● Failed' : isDone ? '● Validated & Ready' : 'Waiting for Parser'}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

        </div>
      </main>

      {/* ── FOOTER ACTIONS BAR ── */}
      <footer className="relative z-10 pb-8 pt-4 px-6 shrink-0 text-center bg-white/80 backdrop-blur-xl border-t border-slate-200/80">
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
              className="px-7 py-2.5 rounded-2xl text-white font-black text-xs transition-all shadow-lg shadow-[#00AFAF]/25 hover:brightness-105 inline-flex items-center gap-2 hover:scale-[1.02]"
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
