import React, { useState } from 'react';
import { 
  UploadCloud, 
  CheckCircle2, 
  Layers, 
  Sparkles, 
  Trash2, 
  AlertTriangle, 
  Eye, 

} from 'lucide-react';
import { api } from '../services/api';

interface IngestHubProps {
  onJobCreated: (jobId: string) => void;
  recentJobs: any[];
  exportPolicy: string;
  setExportPolicy: (policy: string) => void;
  onStartBatchProcessing: (files: File[], notes?: string) => void;
}

export const IngestHub: React.FC<IngestHubProps> = ({
  onJobCreated,
  recentJobs,
  exportPolicy,
  setExportPolicy,
  onStartBatchProcessing
}) => {
  const [dragOver, setDragOver] = useState(false);
  const [notesText, setNotesText] = useState('');
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

  return (
    <div className="w-full space-y-8 animate-fade-in text-slate-900 pb-20">
      
      {/* ── TOP HERO HEADER (Posh Ambient Glassmorphic Card) ── */}
      <div className="bg-white/95 backdrop-blur-xl rounded-3xl p-8 border border-slate-200/80 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.04)] relative overflow-hidden shrink-0 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-bl from-[#00AFAF]/12 via-indigo-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative z-10 space-y-2.5 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="px-3.5 py-1 rounded-full bg-[#00AFAF]/10 border border-[#00AFAF]/25 text-[#008f8f] text-xs font-black uppercase tracking-wider flex items-center gap-1.5 shadow-2xs">
              <Sparkles className="w-3.5 h-3.5 text-[#00AFAF]" />
              RateBridge Ingestion Workspace
            </span>
            <span className="px-3.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-emerald-700 text-xs font-mono font-black flex items-center gap-1.5 shadow-2xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Parsers & Autonomous AI Ready
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Carrier Rate Ingestion Workspace
          </h1>
          <p className="text-sm text-slate-500 font-medium leading-relaxed">
            Drop carrier rate cards (.EML, .MSG, .XLSX, .XLSM, .PDF, .PNG, .JPG) to automatically unpivot container matrices, parse surcharges, and generate standardized Freightify workbooks.
          </p>
        </div>

        {/* Export Policy Segmented Selector */}
        <div className="relative z-10 flex items-center gap-2 bg-slate-100/90 p-1.5 rounded-2xl border border-slate-200/80 shrink-0">
          <span className="text-[11px] font-black text-slate-500 uppercase tracking-wider pl-2 pr-1">Policy:</span>
          {['STRICT', 'PARTIAL', 'WARNING_PERMISSIVE'].map((p) => (
            <button
              key={p}
              onClick={() => setExportPolicy(p)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-black transition-all ${
                exportPolicy === p
                  ? 'bg-white text-[#00AFAF] shadow-sm border border-slate-200/80'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              {p === 'WARNING_PERMISSIVE' ? 'Permissive' : p.charAt(0) + p.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </div>

      {/* ── CENTRAL INGESTION CARD (Single Elegant Dropzone & Notes) ── */}
      <div className="bg-white rounded-3xl p-8 border border-slate-200/90 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] space-y-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-[#00AFAF] via-indigo-600 to-purple-600" />
        
        {/* Dropzone Box */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('rateFileInput')?.click()}
          className={`relative border-2 border-dashed rounded-3xl py-12 px-6 text-center transition-all duration-300 cursor-pointer ${
            dragOver
              ? 'border-[#00AFAF] bg-[#00AFAF]/10 scale-[1.01] shadow-xl'
              : 'border-slate-300/90 bg-gradient-to-b from-slate-50/60 via-white to-slate-50/40 hover:border-[#00AFAF] hover:bg-[#00AFAF]/5 shadow-inner'
          }`}
        >
          <input
            type="file"
            id="rateFileInput"
            className="hidden"
            accept=".eml,.msg,.xlsx,.xls,.xlsm,.pdf,.png,.jpg,.jpeg,.tiff,.txt"
            multiple
            onChange={(e) => e.target.files && handleMultiFileUpload(e.target.files)}
          />

          <div className="flex flex-col items-center gap-3.5">
            <div 
              style={{ backgroundColor: '#00AFAF' }}
              className={`w-16 h-16 rounded-3xl flex items-center justify-center transition-all duration-300 shadow-lg ${
                dragOver ? 'scale-110 shadow-[#00AFAF]/40' : 'shadow-[#00AFAF]/25'
              }`}
            >
              <UploadCloud className="w-8 h-8 text-white" />
            </div>

            <div>
              <p className="text-base sm:text-lg font-black text-slate-900 tracking-tight">
                Click to browse rate cards or drag & drop files here
              </p>
              <p className="text-xs text-slate-500 font-medium mt-1">
                Supports single files or batch folders up to 50 rate cards simultaneously
              </p>

              {/* Supported Format Pills */}
              <div className="flex flex-wrap items-center justify-center gap-2 mt-5">
                {[
                  { name: '.EML / .MSG Emails', color: 'bg-purple-50 text-purple-700 border-purple-200' },
                  { name: '.XLSX / .XLSM Sheets', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
                  { name: '.PDF Schedules', color: 'bg-rose-50 text-rose-700 border-rose-200' },
                  { name: '.PNG / .JPG Matrices', color: 'bg-sky-50 text-sky-700 border-sky-200' },
                  { name: 'Spot Quotes & Text', color: 'bg-amber-50 text-amber-700 border-amber-200' },
                ].map((ext) => (
                  <span key={ext.name} className={`text-[11px] font-black px-3.5 py-1 rounded-xl border ${ext.color}`}>
                    {ext.name}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Supplementary Email Notes & Contract Details Box */}
        <div className="p-5 rounded-3xl bg-slate-50 border border-slate-200/80 space-y-2.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-black text-slate-800 flex items-center gap-2 uppercase tracking-wider">
              <Sparkles className="w-4 h-4 text-[#00AFAF]" />
              Supplementary Email Notes & Contract Details (Optional)
            </label>
            {notesText && (
              <button
                type="button"
                onClick={() => setNotesText('')}
                className="text-xs font-bold text-rose-500 hover:text-rose-700 bg-rose-50 px-2.5 py-0.5 rounded-lg border border-rose-100 transition-all"
              >
                Clear Notes
              </button>
            )}
          </div>
          <textarea
            value={notesText}
            onChange={(e) => setNotesText(e.target.value)}
            rows={2}
            placeholder="Paste supplier email text, contract number (e.g. 299952465), validity dates (e.g. 01-Aug-2026 to 31-Aug-2026), or standard charges (e.g. Documentation Fee $80 NZD, BAF $200 USD)..."
            className="w-full text-xs font-medium text-slate-800 bg-white border border-slate-200 rounded-2xl p-3.5 focus:outline-none focus:ring-2 focus:ring-[#00AFAF]/20 focus:border-[#00AFAF] transition-all placeholder:text-slate-400 custom-scrollbar resize-y shadow-2xs"
          />
          <p className="text-[11px] text-slate-400 font-medium">
            💡 The AI pipeline automatically extracts contract numbers, validity windows, and surcharges from these notes and merges them into every row.
          </p>
        </div>

      </div>

      {/* ── INGESTION HISTORY & WORKBOOKS TABLE ── */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] overflow-hidden flex flex-col">
        <div className="px-8 py-5 flex items-center justify-between border-b border-slate-100 bg-slate-50/70 shrink-0">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-[#00AFAF]" />
            <h3 className="text-xs font-black text-slate-900 uppercase tracking-wider">
              Ingested Rate Sheets & Workbooks ({recentJobs.length})
            </h3>
          </div>

          {recentJobs.length > 0 && (
            <button
              onClick={() => setShowClearModal(true)}
              className="text-xs font-black text-rose-600 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 px-3.5 py-1.5 rounded-xl transition-all flex items-center gap-1.5 border border-rose-200 shadow-2xs"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear History</span>
            </button>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="custom-table w-full align-middle text-slate-900 text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase text-[10px] tracking-wider font-extrabold">
                <th className="pl-8 text-left py-4">Carrier</th>
                <th className="text-left py-4">Rate File Source</th>
                <th className="text-left py-4">Contract / Validity</th>
                <th className="text-center py-4">Rates Extracted</th>
                <th className="text-center py-4">Status</th>
                <th className="pr-8 text-right py-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentJobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-16 text-slate-400 font-medium">
                    No rate files uploaded yet. Drag & drop files above to start.
                  </td>
                </tr>
              ) : (
                recentJobs.map((job) => {
                  const can = job.canonical || {};
                  const carrier = can.carrier_code || job.carrier_code || 'UNKN';
                  const rowCount = (can.rates || []).length || job.total_rows || 0;
                  const contract = can.contract_number || job.contract_number || '—';
                  const validity = can.validity_start ? `${can.validity_start} → ${can.validity_end || ''}` : '—';

                  return (
                    <tr key={job.job_id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="pl-8 py-4 font-mono font-black text-indigo-700">
                        <span className="px-2.5 py-1 rounded-lg bg-indigo-50 border border-indigo-100">
                          {carrier}
                        </span>
                      </td>
                      <td className="py-4 font-black text-slate-900 max-w-xs truncate">
                        {job.file_name}
                      </td>
                      <td className="py-4 text-slate-500 font-mono text-[11px]">
                        <div>{contract !== '—' ? contract : <span className="text-slate-400 italic">No Contract</span>}</div>
                        <div className="text-[10px] text-slate-400">{validity}</div>
                      </td>
                      <td className="text-center py-4 font-mono font-bold text-slate-900">
                        {rowCount.toLocaleString('en-US')}
                      </td>
                      <td className="text-center py-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider inline-flex items-center gap-1 border ${
                          job.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                          job.status === 'NEEDS_REVIEW' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                          'bg-slate-100 text-slate-700 border-slate-200'
                        }`}>
                          {job.status === 'COMPLETED' && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                          {job.status}
                        </span>
                      </td>
                      <td className="pr-8 text-right py-4 space-x-2">
                        <button
                          onClick={() => onJobCreated(job.job_id)}
                          style={{ backgroundColor: '#00AFAF' }}
                          className="px-3.5 py-1.5 rounded-xl text-white font-black text-xs transition-all shadow-sm shadow-[#00AFAF]/20 inline-flex items-center gap-1.5"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Review Rates</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── DUPLICATE CONFLICT MODAL ── */}
      {duplicateConflict && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-3xl p-7 max-w-md w-full border border-slate-200 shadow-2xl space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-black text-slate-900">Duplicate File Detected</h3>
              <p className="text-xs text-slate-500 font-medium mt-1">
                A rate card with filename <strong className="text-slate-900">"{duplicateConflict.file.name}"</strong> has already been processed previously.
              </p>
            </div>
            <div className="flex gap-3 pt-2">
              <button
                onClick={handleConfirmReplaceDuplicate}
                style={{ backgroundColor: '#00AFAF' }}
                className="flex-1 py-2.5 rounded-xl text-white font-black text-xs transition-all shadow-md shadow-[#00AFAF]/20"
              >
                Re-process & Overwrite
              </button>
              <button
                onClick={handleSkipDuplicate}
                className="flex-1 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-black text-xs transition-all"
              >
                Skip This File
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── CLEAR HISTORY MODAL ── */}
      {showClearModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-3xl p-7 max-w-md w-full border border-slate-200 shadow-2xl space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center">
              <Trash2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-black text-slate-900">Clear Rate Ingestion History?</h3>
              <p className="text-xs text-slate-500 font-medium mt-1">
                This will clear all past job logs and reset the queue table. Master data and self-learned dictionaries will remain safely preserved.
              </p>
            </div>
            <div className="flex gap-3 pt-2">
              <button
                disabled={isClearing}
                onClick={handleConfirmClearData}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-black text-xs transition-all shadow-md shadow-rose-600/20 disabled:opacity-50"
              >
                {isClearing ? 'Clearing...' : 'Yes, Clear History'}
              </button>
              <button
                disabled={isClearing}
                onClick={() => setShowClearModal(false)}
                className="flex-1 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-black text-xs transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
