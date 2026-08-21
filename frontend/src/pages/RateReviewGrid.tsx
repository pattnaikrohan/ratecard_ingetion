import React, { useState, useEffect, useMemo } from 'react';
import { 
  Download, 
  RefreshCw, 
  Search, 
  ArrowLeft, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle
} from 'lucide-react';
import { api } from '../services/api';

interface RateReviewGridProps {
  jobId: string | null;
  onBackToDashboard: () => void;
}

export const RateReviewGrid: React.FC<RateReviewGridProps> = ({ jobId, onBackToDashboard }) => {
  const [jobData, setJobData] = useState<any>(null);
  const [rates, setRates] = useState<any[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'VALID' | 'WARNING' | 'ERROR'>('ALL');
  const [isRevalidating, setIsRevalidating] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const fetchingRef = React.useRef(false);

  useEffect(() => {
    if (!jobId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    let isSubscribed = true;

    const fetchJob = async () => {
      if (fetchingRef.current) return;
      fetchingRef.current = true;
      try {
        const data = await api.getJob(jobId);
        if (!isSubscribed) return;

        setJobData(data);
        setIsLoading(false);

        const isProcessing = ['QUEUED', 'PARSING', 'NORMALIZING', 'VALIDATING'].includes(data.status);
        if (data.canonical && data.canonical.rates) {
          setRates((prev) => {
            if (prev.length === 0 || isProcessing) {
              return data.canonical.rates;
            }
            return prev;
          });
        }
      } catch (err) {
        console.error('Error fetching job details:', err);
        if (isSubscribed) {
          setIsLoading(false);
          setJobData({ status: 'FAILED', logs: ['Job not found or server error.'] });
        }
      } finally {
        fetchingRef.current = false;
      }
    };

    fetchJob();

    const interval = setInterval(() => {
      if (jobData && ['QUEUED', 'PARSING', 'NORMALIZING', 'VALIDATING'].includes(jobData.status)) {
        fetchJob();
      }
    }, 2500);

    return () => {
      isSubscribed = false;
      clearInterval(interval);
    };
  }, [jobId, jobData?.status]);

  const handleCellChange = (rowIndex: number, field: string, value: any) => {
    const updated = [...rates];
    updated[rowIndex] = { ...updated[rowIndex], [field]: value };
    setRates(updated);
  };

  const handleRevalidate = async () => {
    if (!jobId) return;
    try {
      setIsRevalidating(true);
      await api.revalidateJob(jobId, rates);
      const data = await api.getJob(jobId);
      setJobData(data);
      if (data.canonical && data.canonical.rates) {
        setRates(data.canonical.rates);
      }
      alert('Rows successfully re-validated against Master Data!');
    } catch (err) {
      alert('Error re-validating rows: ' + err);
    } finally {
      setIsRevalidating(false);
    }
  };

  const handleApproveAndDownload = async () => {
    if (!jobId) return;
    try {
      setIsApproving(true);
      await api.revalidateJob(jobId, rates);
      await api.approveJob(jobId, 'PARTIAL');

      const downloadUrl = api.getDownloadUrl(jobId);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `Freightify_Upload_${jobId}.xlsm`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      const data = await api.getJob(jobId);
      setJobData(data);
      if (data.canonical && data.canonical.rates) {
        setRates(data.canonical.rates);
      }
    } catch (err) {
      alert('Error generating Freightify workbook: ' + err);
    } finally {
      setIsApproving(false);
    }
  };

  const isWorkerProcessing = (jobData && ['QUEUED', 'PARSING', 'NORMALIZING', 'VALIDATING'].includes(jobData.status)) || (isLoading && !jobData);

  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 100;

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, statusFilter]);

  // Counts for filter pills
  const counts = useMemo(() => {
    let valid = 0;
    let warning = 0;
    let error = 0;
    rates.forEach((r) => {
      if (r.validation_status === 'VALID') valid++;
      else if (r.validation_status === 'WARNING') warning++;
      else if (r.validation_status === 'ERROR' || r.validation_status === 'CRITICAL') error++;
    });
    return { total: rates.length, valid, warning, error };
  }, [rates]);

  const filteredRates = rates.filter((r) => {
    const matchesSearch =
      (r.origin_locode || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.origin_raw || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.destination_locode || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.destination_raw || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.carrier_scac || '').toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus =
      statusFilter === 'ALL' ||
      (statusFilter === 'VALID' && r.validation_status === 'VALID') ||
      (statusFilter === 'WARNING' && r.validation_status === 'WARNING') ||
      (statusFilter === 'ERROR' && (r.validation_status === 'ERROR' || r.validation_status === 'CRITICAL'));

    return matchesSearch && matchesStatus;
  });

  const totalPages = Math.max(1, Math.ceil(filteredRates.length / pageSize));
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedRates = filteredRates.slice(startIndex, startIndex + pageSize);

  const displayFileName = 
    jobData?.file_name || 
    jobData?.canonical?.file_name || 
    jobData?.output_file_name || 
    (jobId ? `Rate Card #${jobId}` : 'Rate Card Details');

  const carrierName = jobData?.canonical?.carrier_code || jobData?.carrier_code || jobData?.summary?.carriers_found?.[0] || 'Standardized Rates';

  if (!jobId) {
    return (
      <div className="bg-white rounded-3xl p-16 text-center space-y-4 border border-slate-200 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)]">
        <h3 className="text-xl font-black text-slate-900">No Rate Card Selected for Review</h3>
        <p className="text-sm text-slate-500 font-medium">Please select an ingestion job from the Dashboard or Rate Ingestion Hub to inspect.</p>
        <button 
          onClick={onBackToDashboard} 
          style={{ backgroundColor: '#00AFAF' }}
          className="px-6 py-3 rounded-2xl text-white font-black text-xs transition-all shadow-md shadow-[#00AFAF]/20 inline-flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" /> Return to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="w-full space-y-4 animate-fade-in text-slate-900 pb-20">
      
      {/* ── TOP STREAMLINED CONTROL HEADER ── */}
      <div className="bg-white/95 backdrop-blur-xl rounded-2xl px-6 py-4 border border-slate-200/80 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.03)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        
        {/* Left: Back Link, Title, Filename & Carrier */}
        <div className="space-y-1">
          <button 
            onClick={onBackToDashboard} 
            className="text-[11px] text-[#00AFAF] hover:underline flex items-center gap-1 font-black uppercase tracking-wider"
          >
            <ArrowLeft className="w-3 h-3" /> Back to Dashboard
          </button>
          
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-lg sm:text-xl font-black text-slate-900 tracking-tight">
              Rate Review & Master Data Alignment
            </h1>
            <span className="px-2.5 py-0.5 rounded-lg bg-[#00AFAF]/10 border border-[#00AFAF]/25 text-[#008f8f] font-mono text-xs font-black truncate max-w-xs" title={displayFileName}>
              {displayFileName}
            </span>
            <span className="px-2 py-0.5 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-700 font-mono text-xs font-black">
              {carrierName}
            </span>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={handleRevalidate}
            disabled={isRevalidating || isWorkerProcessing || rates.length === 0}
            className="px-3.5 py-2 rounded-xl bg-white hover:bg-slate-50 text-slate-700 font-black text-xs transition-all border border-slate-200 shadow-2xs inline-flex items-center gap-1.5 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRevalidating ? 'animate-spin text-[#00AFAF]' : ''}`} />
            <span>Re-Validate</span>
          </button>

          <button
            onClick={handleApproveAndDownload}
            disabled={isApproving || isWorkerProcessing || rates.length === 0}
            style={{ backgroundColor: '#00AFAF' }}
            className="px-4 py-2 rounded-xl text-white font-black text-xs transition-all shadow-md shadow-[#00AFAF]/20 hover:brightness-105 inline-flex items-center gap-1.5 disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{isApproving ? 'Generating .xlsm...' : 'Export Freightify .XLSM'}</span>
          </button>
        </div>
      </div>

      {/* ── COMPACT HORIZONTAL STAT CHIPS (Saves 150px vertical height) ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white rounded-2xl py-2.5 px-4 border border-slate-200/80 shadow-2xs flex items-center justify-between">
          <span className="text-[11px] font-black text-slate-500 uppercase tracking-wider">Total Rates</span>
          <span className="font-mono text-base font-black text-slate-900">{counts.total.toLocaleString('en-US')}</span>
        </div>
        <div className="bg-white rounded-2xl py-2.5 px-4 border border-slate-200/80 shadow-2xs flex items-center justify-between">
          <span className="text-[11px] font-black text-emerald-700 uppercase tracking-wider flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Valid
          </span>
          <span className="font-mono text-base font-black text-emerald-600">{counts.valid.toLocaleString('en-US')}</span>
        </div>
        <div className="bg-white rounded-2xl py-2.5 px-4 border border-slate-200/80 shadow-2xs flex items-center justify-between">
          <span className="text-[11px] font-black text-amber-700 uppercase tracking-wider flex items-center gap-1">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> Warnings
          </span>
          <span className="font-mono text-base font-black text-amber-600">{counts.warning.toLocaleString('en-US')}</span>
        </div>
        <div className="bg-white rounded-2xl py-2.5 px-4 border border-slate-200/80 shadow-2xs flex items-center justify-between">
          <span className="text-[11px] font-black text-rose-700 uppercase tracking-wider flex items-center gap-1">
            <XCircle className="w-3.5 h-3.5 text-rose-600" /> Errors
          </span>
          <span className="font-mono text-base font-black text-rose-600">{counts.error.toLocaleString('en-US')}</span>
        </div>
      </div>

      {/* ── DATA GRID CARD ── */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.03)] overflow-hidden flex flex-col relative">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-[#00AFAF] via-indigo-600 to-purple-600" />

        {/* Filter Toolbar */}
        <div className="px-6 py-3.5 flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/70">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search ports, UNLOCODE, or SCAC..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 pr-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs font-medium text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#00AFAF]/20 focus:border-[#00AFAF] w-56 shadow-2xs"
              />
            </div>

            {/* Status Filter Segmented Selector */}
            <div className="flex items-center bg-slate-200/70 p-0.5 rounded-xl text-xs font-black">
              {[
                { id: 'ALL', label: `All (${counts.total})` },
                { id: 'VALID', label: `Valid (${counts.valid})` },
                { id: 'WARNING', label: `Warnings (${counts.warning})` },
                { id: 'ERROR', label: `Errors (${counts.error})` },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setStatusFilter(tab.id as any)}
                  className={`px-3 py-1 rounded-lg transition-all ${
                    statusFilter === tab.id 
                      ? 'bg-white text-slate-900 shadow-2xs' 
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="text-xs text-slate-500 font-mono font-bold">
            Showing {filteredRates.length > 0 ? startIndex + 1 : 0} - {Math.min(startIndex + pageSize, filteredRates.length)} of {filteredRates.length}
          </div>
        </div>

        {/* Grid Table */}
        <div className="overflow-x-auto">
          <table className="custom-table w-full align-middle text-slate-900 text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase text-[10px] tracking-wider font-extrabold">
                <th className="pl-6 text-left py-3">Status & Diagnostics</th>
                <th className="text-left py-3">Carrier</th>
                <th className="text-left py-3">Origin Port</th>
                <th className="text-left py-3">Destination Port</th>
                <th className="text-center py-3">Type</th>
                <th className="text-right py-3">Base Rate (OFR)</th>
                <th className="text-center py-3">Curr</th>
                <th className="text-center py-3">Validity Window</th>
                <th className="pr-6 text-center py-3">Attached Surcharges</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {paginatedRates.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-16 text-slate-400 font-medium">
                    No rate rows found matching current search/filter.
                  </td>
                </tr>
              ) : (
                paginatedRates.map((r, idx) => {
                  const actualIdx = startIndex + idx;
                  const isValid = r.validation_status === 'VALID';
                  const isWarn = r.validation_status === 'WARNING';
                  const isErr = r.validation_status === 'ERROR' || r.validation_status === 'CRITICAL';
                  const hasZeroRate = r.base_rate === 0 || r.ofr_amount === 0;

                  // Compute validation messages
                  const messages: string[] = [];
                  if (Array.isArray(r.validation_items) && r.validation_items.length > 0) {
                    r.validation_items.forEach((item: any) => {
                      if (item.message) messages.push(item.message);
                      else if (item.reason_code) messages.push(item.reason_code.replace(/_/g, ' '));
                    });
                  }
                  if (Array.isArray(r.validation_messages)) {
                    r.validation_messages.forEach((m: string) => {
                      if (!messages.includes(m)) messages.push(m);
                    });
                  }
                  if (messages.length === 0 && isWarn) {
                    if (hasZeroRate) messages.push("Base Ocean Freight Rate is $0.00 (Subject to Surcharges)");
                    if (!r.validity_start) messages.push("Missing validity start date");
                  }

                  return (
                    <tr 
                      key={actualIdx} 
                      className={`transition-colors ${
                        isWarn ? 'bg-amber-50/40 hover:bg-amber-100/50 border-l-4 border-l-amber-400' :
                        isErr ? 'bg-rose-50/40 hover:bg-rose-100/50 border-l-4 border-l-rose-500' :
                        'hover:bg-slate-50/70'
                      }`}
                    >
                      {/* Status Column with explicit validation message */}
                      <td className="pl-6 py-2.5 space-y-1">
                        <div className="flex items-center gap-1.5">
                          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider inline-flex items-center gap-1 border ${
                            isValid ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                            isWarn ? 'bg-amber-100 text-amber-800 border-amber-300' : 'bg-rose-100 text-rose-800 border-rose-300'
                          }`}>
                            {isValid && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                            {isWarn && <AlertTriangle className="w-3 h-3 text-amber-600" />}
                            {isErr && <XCircle className="w-3 h-3 text-rose-600" />}
                            {r.validation_status || 'VALID'}
                          </span>
                        </div>

                        {/* Validation Diagnostic Tag */}
                        {messages.length > 0 && (
                          <div className="text-[10px] text-amber-800 font-bold bg-amber-100/80 px-2 py-0.5 rounded-md border border-amber-200 max-w-xs truncate" title={messages.join('; ')}>
                            ⚠️ {messages[0]}
                          </div>
                        )}
                      </td>

                      <td className="py-2.5 font-mono font-black text-indigo-700">
                        {r.carrier_scac || 'GSL'}
                      </td>

                      {/* Origin Port */}
                      <td className="py-2.5">
                        <div className="flex items-center gap-1.5">
                          <input
                            type="text"
                            value={r.origin_locode || ''}
                            onChange={(e) => handleCellChange(actualIdx, 'origin_locode', e.target.value)}
                            className="px-2 py-1 rounded-lg bg-white border border-slate-200 font-mono text-xs font-black text-slate-900 w-24 focus:ring-2 focus:ring-[#00AFAF]/20 focus:border-[#00AFAF]"
                          />
                          <span className="text-[10px] text-slate-400 font-medium truncate max-w-[120px]" title={r.origin_raw}>
                            {r.origin_raw || r.origin_locode}
                          </span>
                        </div>
                      </td>

                      {/* Destination Port */}
                      <td className="py-2.5">
                        <div className="flex items-center gap-1.5">
                          <input
                            type="text"
                            value={r.destination_locode || ''}
                            onChange={(e) => handleCellChange(actualIdx, 'destination_locode', e.target.value)}
                            className="px-2 py-1 rounded-lg bg-white border border-slate-200 font-mono text-xs font-black text-slate-900 w-24 focus:ring-2 focus:ring-[#00AFAF]/20 focus:border-[#00AFAF]"
                          />
                          <span className="text-[10px] text-slate-400 font-medium truncate max-w-[120px]" title={r.destination_raw}>
                            {r.destination_raw || r.destination_locode}
                          </span>
                        </div>
                      </td>

                      {/* Load Type */}
                      <td className="text-center py-2.5 font-mono font-black text-slate-800">
                        {r.load_type || '20GP'}
                      </td>

                      {/* Base Rate Input (Highlighted with amber if $0.00) */}
                      <td className="text-right py-2.5 font-mono font-black text-slate-900">
                        <div className="inline-flex items-center gap-1">
                          <input
                            type="number"
                            value={r.base_rate ?? r.ofr_amount ?? 0}
                            onChange={(e) => handleCellChange(actualIdx, 'base_rate', parseFloat(e.target.value) || 0)}
                            className={`px-2 py-1 rounded-lg font-mono text-xs font-black text-right w-20 focus:ring-2 focus:ring-[#00AFAF]/20 ${
                              hasZeroRate 
                                ? 'bg-amber-100 border-2 border-amber-400 text-amber-950 font-black' 
                                : 'bg-white border border-slate-200 text-slate-900'
                            }`}
                            title={hasZeroRate ? "Base Rate is $0.00 — edit inline if needed" : ""}
                          />
                        </div>
                      </td>

                      {/* Currency */}
                      <td className="text-center py-2.5 font-mono text-slate-500 font-bold">
                        {r.currency || r.ofr_currency || 'USD'}
                      </td>

                      {/* Validity */}
                      <td className="text-center py-2.5 font-mono text-[10px] text-slate-600">
                        {r.validity_start ? (
                          <div>
                            <div>{r.validity_start}</div>
                            <div className="text-slate-400">→ {r.validity_end || 'Open'}</div>
                          </div>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200 font-bold">
                            Missing
                          </span>
                        )}
                      </td>

                      {/* Attached Surcharges */}
                      <td className="pr-6 text-center py-2.5">
                        {(r.charges || []).length > 0 ? (
                          <span className="px-2 py-0.5 rounded-lg bg-white border border-slate-200 text-slate-700 font-mono font-bold text-[10px] shadow-2xs" title={r.charges.map((c: any) => `${c.charge_code}: ${c.amount} ${c.currency}`).join(', ')}>
                            +{r.charges.length} Surcharges
                          </span>
                        ) : (
                          <span className="text-slate-400 text-[10px]">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        {totalPages > 1 && (
          <div className="px-6 py-3 bg-slate-50/80 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-500 font-medium">
              Page {currentPage} of {totalPages} ({filteredRates.length} rows)
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1 rounded-lg bg-white border border-slate-200 font-black text-slate-700 disabled:opacity-40"
              >
                Previous
              </button>
              <button
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                className="px-3 py-1 rounded-lg bg-white border border-slate-200 font-black text-slate-700 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

    </div>
  );
};
