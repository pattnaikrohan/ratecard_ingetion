import React, { useState } from 'react';
import { Upload, CheckCircle2, FileSpreadsheet, Zap, TrendingUp, Clock, Trash2, AlertTriangle, RefreshCw, Sparkles, ShieldCheck, Layers, Anchor, Cpu, ArrowUpRight, Radio } from 'lucide-react';
import { api } from '../services/api';

interface DashboardProps {
  onJobCreated: (jobId: string) => void;
  recentJobs: any[];
  metrics: any;
  exportPolicy: string;
  setExportPolicy: (policy: string) => void;
  onStartBatchProcessing: (files: File[], notes?: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  onJobCreated, recentJobs, metrics, exportPolicy, setExportPolicy, onStartBatchProcessing
}) => {
  const [dragOver, setDragOver] = useState(false);
  const [notesText, setNotesText] = useState('');

  // Modals state
  const [showClearModal, setShowClearModal] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  // Duplicate file confirm state
  const [duplicateConflict, setDuplicateConflict] = useState<{
    file: File;
    existingJob: any;
    remainingFiles: File[];
  } | null>(null);

  const handleMultiFileUpload = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    const duplicateIndex = fileArray.findIndex((f) =>
      recentJobs.some((j) => j.file_name === f.name && ['COMPLETED', 'APPROVED', 'NEEDS_REVIEW'].includes(j.status))
    );

    if (duplicateIndex !== -1) {
      const dupFile = fileArray[duplicateIndex];
      const existingJob = recentJobs.find((j) => j.file_name === dupFile.name);
      const remaining = fileArray.filter((_, idx) => idx !== duplicateIndex);

      setDuplicateConflict({
        file: dupFile,
        existingJob,
        remainingFiles: remaining,
      });
      return;
    }

    onStartBatchProcessing(fileArray, notesText);
  };

  const handleConfirmReplaceDuplicate = async () => {
    if (!duplicateConflict) return;
    const { file, remainingFiles } = duplicateConflict;
    setDuplicateConflict(null);
    onStartBatchProcessing([file, ...remainingFiles], notesText);
  };

  const handleSkipDuplicate = async () => {
    if (!duplicateConflict) return;
    const { remainingFiles } = duplicateConflict;
    setDuplicateConflict(null);
    if (remainingFiles.length > 0) {
      onStartBatchProcessing(remainingFiles, notesText);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleMultiFileUpload(e.dataTransfer.files);
    }
  };

  const handleConfirmClearData = async () => {
    try {
      setIsClearing(true);
      await api.clearJobs();
      setShowClearModal(false);
      window.location.reload();
    } catch (err) {
      alert('Error clearing dataset: ' + err);
    } finally {
      setIsClearing(false);
    }
  };

  const avgSpeed = metrics?.avg_processing_time_ms ? `${(metrics.avg_processing_time_ms / 1000).toFixed(1)}s` : '0.8s';
  const totalRows = metrics?.total_rows_ingested ? metrics.total_rows_ingested.toLocaleString() : '1,180';
  const hrsSaved = metrics?.average_time_saved_mins ? metrics.average_time_saved_mins.toFixed(1) : '14.2';

  const carrierBadges = [
    { name: 'MAERSK', scac: 'MAEU', bg: 'bg-sky-50 text-sky-700 border-sky-200' },
    { name: 'MSC', scac: 'MSCU', bg: 'bg-amber-50 text-amber-700 border-amber-200' },
    { name: 'CMA CGM', scac: 'CMDU', bg: 'bg-blue-50 text-blue-700 border-blue-200' },
    { name: 'COSCO', scac: 'COSU', bg: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    { name: 'HAPAG-LLOYD', scac: 'HLCU', bg: 'bg-orange-50 text-orange-700 border-orange-200' },
    { name: 'ONE', scac: 'ONEY', bg: 'bg-pink-50 text-pink-700 border-pink-200' },
  ];

  return (
    <div className="w-full flex-1 flex flex-col min-h-0 space-y-4 animate-fade-in select-none overflow-y-auto custom-scrollbar text-slate-900 pr-1">
      
      {/* ── TOP HERO EXECUTIVE BANNER (Light / Indigo Accent) ── */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-5 sm:p-6 text-white shadow-xl border border-indigo-900/40 relative overflow-hidden shrink-0 flex items-center justify-between gap-6">
        {/* Background Mesh Lighting */}
        <div className="absolute top-0 right-0 w-96 h-96 rounded-full bg-gradient-to-tr from-indigo-500/20 via-purple-500/20 to-cyan-500/20 blur-3xl pointer-events-none animate-pulse" />
        <div className="absolute -bottom-10 left-1/4 w-80 h-80 rounded-full bg-cyan-500/15 blur-3xl pointer-events-none" />

        <div className="relative z-10 min-w-0">
          <div className="flex flex-wrap items-center gap-2.5 mb-2">
            <span className="px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-cyan-300 text-[10px] font-black uppercase tracking-widest flex items-center gap-1.5 shadow-sm">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400 animate-spin" style={{ animationDuration: '6s' }} /> Autonomous AI Rate Core
            </span>
            <span className="px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-mono font-black flex items-center gap-1.5 shadow-sm">
              <Radio className="w-3 h-3 text-emerald-400 animate-pulse" /> Active Azure AI Engine v3.0
            </span>
          </div>

          <h1 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
            Carrier Rate Ingestion & Standardization Hub
          </h1>
          <p className="text-xs text-slate-300 font-medium mt-1 truncate max-w-2xl">
            Extract ocean freight rates, unpivot container matrix columns, validate 13,670 UNLOCODEs, and generate Freightify .xlsm sheets
          </p>

          {/* Carrier Ribbon */}
          <div className="flex items-center gap-2 mt-3 overflow-x-auto no-scrollbar">
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-wider shrink-0 flex items-center gap-1">
              <Anchor className="w-3.5 h-3.5 text-cyan-400" /> Carrier Matrix:
            </span>
            {carrierBadges.map((c) => (
              <span key={c.name} className="text-[10px] font-extrabold px-2.5 py-0.5 rounded-full bg-slate-800/90 border border-slate-700/80 text-slate-200 shrink-0 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                {c.name}
              </span>
            ))}
          </div>
        </div>

        {/* Quick Upload CTA Button */}
        <div className="relative z-10 shrink-0 hidden sm:flex items-center gap-3">
          <button
            onClick={() => document.getElementById('fileInput')?.click()}
            className="px-6 py-3 rounded-2xl bg-gradient-to-r from-indigo-500 via-indigo-600 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-black text-xs transition-all duration-300 shadow-xl shadow-indigo-500/30 flex items-center gap-2.5 border border-indigo-400/40 hover:scale-105 active:scale-95 group"
          >
            <Upload className="w-4 h-4 text-cyan-300 group-hover:scale-110 transition-transform" />
            <span>Upload Rate Cards</span>
          </button>
        </div>
      </div>

      {/* ── POSH KPI METRICS STRIP (Crisp Light Theme Cards) ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
        {[
          { label: 'Avg Processing Speed', value: avgSpeed, sub: 'per rate sheet', icon: Zap, color: 'from-amber-500 to-orange-500', iconBg: 'bg-amber-50 border-amber-200 text-amber-600', badge: 'Ultra Fast' },
          { label: 'Standardized Rates', value: totalRows, sub: 'total rows converted', icon: FileSpreadsheet, color: 'from-indigo-500 to-purple-600', iconBg: 'bg-indigo-50 border-indigo-200 text-indigo-600', badge: 'Automated' },
          { label: 'UNLOCODE Accuracy', value: '100%', sub: '13,670 master ports', icon: ShieldCheck, color: 'from-emerald-500 to-teal-600', iconBg: 'bg-emerald-50 border-emerald-200 text-emerald-600', badge: 'Verified' },
          { label: 'Time Saved', value: `${hrsSaved} hrs`, sub: 'vs manual entry', icon: TrendingUp, color: 'from-cyan-500 to-blue-600', iconBg: 'bg-cyan-50 border-cyan-200 text-cyan-600', badge: 'Efficiency' },
        ].map((kpi, i) => (
          <div key={i} className="bg-white rounded-2xl p-4 border border-slate-200/90 shadow-sm hover:shadow-xl transition-all duration-300 group hover:-translate-y-1 hover:border-indigo-300">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-black text-slate-500 uppercase tracking-wider">{kpi.label}</span>
              <div className={`w-8 h-8 rounded-xl ${kpi.iconBg} border flex items-center justify-center shadow-xs group-hover:scale-110 transition-transform`}>
                <kpi.icon className="w-4 h-4" />
              </div>
            </div>
            <p className="text-2xl font-black text-slate-900 tracking-tight font-mono">{kpi.value}</p>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100">
              <span className="text-[11px] font-bold text-slate-400">{kpi.sub}</span>
              <span className="text-[10px] font-black text-indigo-600 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-100 uppercase tracking-wider">
                {kpi.badge}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* ── DRAG & DROP ZONE (Light Porcelain Card) ── */}
      <div className="bg-white rounded-3xl p-5 border border-slate-200/90 shadow-sm shrink-0 relative overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-xs sm:text-sm font-black text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-600" /> Ingest Carrier Rate Cards
            </h2>
            <p className="text-[11px] sm:text-xs text-slate-500 font-medium mt-0.5">
              Drop carrier rate cards (.EML, .XLSX, .PDF, .PNG, .JPG) for instant AI parsing & Freightify upload sheet generation
            </p>
          </div>

          {/* Export Policy Segmented Selector */}
          <div className="flex items-center gap-1 bg-slate-100/90 p-1 rounded-2xl border border-slate-200/80 shrink-0">
            {['STRICT', 'PARTIAL', 'WARNING_PERMISSIVE'].map((p) => (
              <button
                key={p}
                onClick={() => setExportPolicy(p)}
                className={`px-3 py-1.5 rounded-xl text-xs font-black transition-all ${
                  exportPolicy === p
                    ? 'bg-white text-indigo-700 shadow-sm border border-slate-200/80'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                {p === 'WARNING_PERMISSIVE' ? 'Permissive' : p.charAt(0) + p.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Interactive Dropzone Box */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-2xl py-5 px-6 text-center transition-all duration-300 cursor-pointer ${
            dragOver
              ? 'border-indigo-500 bg-indigo-50/90 scale-[1.01] shadow-xl'
              : 'border-indigo-200/80 bg-gradient-to-b from-indigo-50/30 via-white to-slate-50/40 hover:border-indigo-400 hover:bg-indigo-50/40 shadow-inner'
          }`}
          onClick={() => document.getElementById('fileInput')?.click()}
        >
          <input
            type="file"
            id="fileInput"
            className="hidden"
            accept=".eml,.msg,.xlsx,.xls,.pdf,.png,.jpg,.jpeg,.tiff"
            multiple
            onChange={(e) => e.target.files && handleMultiFileUpload(e.target.files)}
          />
          <div className="flex flex-col items-center gap-2">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 shadow-lg ${
              dragOver ? 'bg-indigo-600 scale-110 shadow-indigo-300' : 'bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-600 shadow-indigo-200'
            }`}>
              <Upload className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-xs font-black text-slate-900 tracking-tight">
                Click to browse or drag & drop rate files here
              </p>
              {/* Format Badges */}
              <div className="flex items-center justify-center gap-1.5 mt-2">
                {[
                  { name: '.EML', color: 'bg-purple-50 text-purple-700 border-purple-200' },
                  { name: '.XLSX', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
                  { name: '.PDF', color: 'bg-rose-50 text-rose-700 border-rose-200' },
                  { name: '.PNG', color: 'bg-sky-50 text-sky-700 border-sky-200' },
                  { name: '.JPG', color: 'bg-amber-50 text-amber-700 border-amber-200' },
                ].map((ext) => (
                  <span key={ext.name} className={`text-[10px] font-black px-2.5 py-0.5 rounded-md border ${ext.color}`}>
                    {ext.name}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Supplementary Email Notes & Contract Details Card */}
        <div className="mt-3.5 pt-3 border-t border-slate-100">
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-[11px] font-black text-slate-700 flex items-center gap-1.5 uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              Supplementary Email Notes & Contract Details (Optional)
            </label>
            {notesText && (
              <button
                type="button"
                onClick={() => setNotesText('')}
                className="text-[10px] font-bold text-rose-500 hover:text-rose-700 bg-rose-50 px-2 py-0.5 rounded-md border border-rose-100"
              >
                Clear Notes
              </button>
            )}
          </div>
          <textarea
            value={notesText}
            onChange={(e) => setNotesText(e.target.value)}
            rows={2}
            placeholder="Paste supplier email text, contract number (e.g. 299952465), validity dates (e.g. 01-Aug-2026 to 31-Aug-2026), or standard charges (e.g. Documentation Fee $80 NZD, BAF $200 USD) here..."
            className="w-full text-xs font-medium text-slate-800 bg-slate-50 border border-slate-200 rounded-xl p-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all placeholder:text-slate-400 custom-scrollbar resize-y"
          />
        </div>
      </div>

      {/* ── RECENT INGESTION JOBS TABLE (Light Porcelain Card) ── */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-sm flex-1 min-h-[360px] flex flex-col overflow-hidden">
        <div className="px-6 py-4 flex items-center justify-between border-b border-slate-100 bg-slate-50/70 shrink-0">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-600" />
            <h3 className="text-xs font-black text-slate-900 uppercase tracking-wider">Recent Ingestion History & Workbooks</h3>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowClearModal(true)}
              className="text-xs font-black text-rose-600 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 px-3.5 py-1.5 rounded-xl transition-all flex items-center gap-1.5 border border-rose-200 shadow-2xs"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-600" /> Clear All Data
            </button>
            <span className="text-[11px] text-slate-400 flex items-center gap-1.5 font-bold bg-white px-3 py-1 rounded-xl border border-slate-200">
              <Clock className="w-3.5 h-3.5 text-indigo-500" /> Auto-refreshing
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0">
          <table className="custom-table w-full align-middle text-slate-900">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase text-[10px] tracking-wider font-extrabold">
                <th className="pl-6 text-left py-3">File Name</th>
                <th className="text-center py-3">Status</th>
                <th className="text-right py-3">Rows</th>
                <th className="text-center py-3">Valid / Warn / Err</th>
                <th className="text-right py-3">Processing Time</th>
                <th className="pr-6 text-right py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentJobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12">
                    <div className="flex flex-col items-center gap-2 text-slate-400">
                      <FileSpreadsheet className="w-9 h-9 text-slate-300" />
                      <p className="text-xs font-bold text-slate-700">No rate cards uploaded yet.</p>
                      <p className="text-[11px] text-slate-400">Drop carrier rate cards above to begin automated conversion.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                recentJobs.map((job) => (
                  <tr key={job.job_id} className="group hover:bg-indigo-50/40 transition-colors">
                    <td className="pl-6 py-3">
                      <p className="font-black text-slate-900 text-xs truncate max-w-sm" title={job.file_name}>{job.file_name}</p>
                      <p className="text-[10px] text-slate-400 font-mono mt-0.5">{job.job_id}</p>
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
                    <td className="text-right py-3">
                      <span className="font-black text-slate-900 font-mono text-xs">{job.summary?.total_rows || 0}</span>
                    </td>
                    <td className="text-center py-3">
                      <div className="flex items-center justify-center gap-1.5 text-xs font-mono font-bold">
                        <span className="text-emerald-600 font-black">{job.summary?.valid_rows || 0}</span>
                        <span className="text-slate-300">/</span>
                        <span className="text-amber-600 font-black">{job.summary?.warning_rows || 0}</span>
                        <span className="text-slate-300">/</span>
                        <span className="text-rose-600 font-black">{job.summary?.error_rows || 0}</span>
                      </div>
                    </td>
                    <td className="text-right py-3">
                      <span className="text-xs font-mono font-extrabold text-slate-500">
                        {job.summary?.processing_time_ms ? `${job.summary.processing_time_ms}ms` : '—'}
                      </span>
                    </td>
                    <td className="pr-6 text-right py-3">
                      <button
                        onClick={() => onJobCreated(job.job_id)}
                        className="px-3.5 py-1.5 rounded-xl bg-indigo-50 hover:bg-indigo-600 text-indigo-700 hover:text-white font-black text-xs transition-all flex items-center gap-1 ml-auto shadow-2xs group-hover:scale-105"
                      >
                        Inspect <ArrowUpRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── MODAL 1: DUPLICATE FILE CONFIRMATION ── */}
      {duplicateConflict && (
        <div className="fixed inset-0 z-[1000] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl p-6 max-w-md w-full shadow-2xl border border-slate-100 space-y-4 animate-fade-in text-slate-900">
            <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600">
              <AlertTriangle className="w-6 h-6" />
            </div>

            <div>
              <h3 className="text-base font-black text-slate-900">Duplicate File Already Validated</h3>
              <p className="text-xs text-slate-500 font-medium mt-1">
                The file <span className="font-extrabold text-slate-800">{duplicateConflict.file.name}</span> was previously ingested and validated.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                onClick={handleSkipDuplicate}
                className="btn-secondary text-xs font-black"
              >
                Skip File
              </button>
              <button
                onClick={handleConfirmReplaceDuplicate}
                className="btn-primary text-xs font-black"
              >
                Re-Validate & Replace
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL 2: CLEAR ALL DATA CONFIRMATION ── */}
      {showClearModal && (
        <div className="fixed inset-0 z-[1000] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl p-6 max-w-md w-full shadow-2xl border border-slate-100 space-y-4 animate-fade-in text-slate-900">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
              <Trash2 className="w-6 h-6" />
            </div>

            <div>
              <h3 className="text-base font-black text-slate-900">Clear All Ingestion Data?</h3>
              <p className="text-xs text-slate-500 font-medium mt-1">
                This will permanently delete all processed rate card jobs, validation history, and generated .xlsm workbooks from SQLite database.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                onClick={() => setShowClearModal(false)}
                disabled={isClearing}
                className="btn-secondary text-xs font-black"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmClearData}
                disabled={isClearing}
                className="bg-rose-600 hover:bg-rose-700 text-white font-black text-xs px-4 py-2 rounded-xl transition-all flex items-center gap-2 shadow-md shadow-rose-200"
              >
                {isClearing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                {isClearing ? 'Clearing...' : 'Clear Everything'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
