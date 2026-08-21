import React, { useState, useEffect } from 'react';
import { Download, RefreshCw, Search, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { api } from '../services/api';

interface RateReviewGridProps {
  jobId: string | null;
  onBackToDashboard: () => void;
}

export const RateReviewGrid: React.FC<RateReviewGridProps> = ({ jobId, onBackToDashboard }) => {
  const [jobData, setJobData] = useState<any>(null);
  const [rates, setRates] = useState<any[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
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

  const isWorkerProcessing = (jobData && ['QUEUED', 'PARSING', 'NORMALIZING', 'VALIDATING'].includes(jobData.status)) || (isLoading && !jobData);


  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 150;

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, statusFilter]);

  const filteredRates = rates.filter((r) => {
    const matchesSearch =
      (r.origin_locode || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.destination_locode || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.carrier_scac || '').toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = statusFilter === 'ALL' || r.validation_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // const totalPages = Math.max(1, Math.ceil(filteredRates.length / pageSize));
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedRates = filteredRates.slice(startIndex, startIndex + pageSize);

  const summary = jobData?.summary || {};

  return (
    <div className="w-full space-y-8 animate-fade-in text-slate-900 pb-20">
      
      {/* ── TOP HERO HEADER (Posh Ambient Glassmorphic Card) ── */}
      <div className="bg-white/95 backdrop-blur-xl rounded-3xl p-8 border border-slate-200/80 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.04)] relative overflow-hidden shrink-0 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-bl from-[#00AFAF]/12 via-indigo-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative z-10 space-y-2.5">
          <button onClick={onBackToDashboard} className="text-xs text-[#00AFAF] hover:underline flex items-center gap-1 font-bold mb-1">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
          </button>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
              Rate Review & Master Data Alignment
            </h1>
            <span className="px-3.5 py-1 rounded-full bg-[#00AFAF]/10 border border-[#00AFAF]/25 text-[#008f8f] font-mono text-xs font-black">
              {jobData?.file_name || 'Loading...'}
            </span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="relative z-10 flex items-center gap-3 shrink-0">
          <button
            onClick={handleRevalidate}
            disabled={isRevalidating || isWorkerProcessing || rates.length === 0}
            className="px-4 py-2.5 rounded-2xl bg-white hover:bg-slate-50 text-slate-700 font-black text-xs transition-all border border-slate-200 shadow-2xs inline-flex items-center gap-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRevalidating ? 'animate-spin' : ''}`} />
            <span>Re-Validate Rows</span>
          </button>

          <button
            onClick={handleApproveAndDownload}
            disabled={isApproving || isWorkerProcessing || rates.length === 0}
            style={{ backgroundColor: '#00AFAF' }}
            className="px-6 py-2.5 rounded-2xl text-white font-black text-xs transition-all shadow-md shadow-[#00AFAF]/20 hover:brightness-105 inline-flex items-center gap-2 disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            <span>{isApproving ? 'Generating .xlsm...' : 'Export Freightify .XLSM'}</span>
          </button>
        </div>
      </div>

      {/* ── 4-COLUMN SUMMARY STATS ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-2xs text-center">
          <p className="text-[11px] text-slate-400 uppercase font-black">Total Extracted Rates</p>
          <p className="text-2xl font-black text-slate-900 font-mono mt-1">{summary.total_rows || rates.length}</p>
        </div>
        <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-2xs text-center">
          <p className="text-[11px] text-emerald-600 uppercase font-black">Valid Rates</p>
          <p className="text-2xl font-black text-emerald-600 font-mono mt-1">{summary.valid_rows || 0}</p>
        </div>
        <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-2xs text-center">
          <p className="text-[11px] text-amber-600 uppercase font-black">Warnings</p>
          <p className="text-2xl font-black text-amber-600 font-mono mt-1">{summary.warning_rows || 0}</p>
        </div>
        <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-2xs text-center">
          <p className="text-[11px] text-rose-600 uppercase font-black">Errors / Quarantined</p>
          <p className="text-2xl font-black text-rose-600 font-mono mt-1">{summary.error_rows || 0}</p>
        </div>
      </div>

      {/* ── DATA GRID CARD ── */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] overflow-hidden flex flex-col relative">
        <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-[#00AFAF] via-indigo-600 to-purple-600" />

        {/* Filter Toolbar */}
        <div className="px-8 py-4.5 flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 bg-slate-50/70">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search ports, UNLOCODE, or SCAC..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-2 rounded-xl bg-white border border-slate-200 text-xs font-medium text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#00AFAF]/20 focus:border-[#00AFAF] w-64 shadow-2xs"
              />
            </div>

            {/* Status Filter */}
            <div className="flex items-center bg-slate-200/70 p-1 rounded-xl text-xs font-black">
              {['ALL', 'VALID', 'WARNING', 'ERROR'].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-3 py-1 rounded-lg transition-all ${
                    statusFilter === s ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div className="text-xs text-slate-400 font-mono font-bold">
            Showing {filteredRates.length > 0 ? startIndex + 1 : 0} - {Math.min(startIndex + pageSize, filteredRates.length)} of {filteredRates.length}
          </div>
        </div>

        {/* Grid Table */}
        <div className="overflow-x-auto">
          <table className="custom-table w-full align-middle text-slate-900 text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 uppercase text-[10px] tracking-wider font-extrabold">
                <th className="pl-8 text-left py-3.5">Status</th>
                <th className="text-left py-3.5">Carrier</th>
                <th className="text-left py-3.5">Origin Port</th>
                <th className="text-left py-3.5">Destination Port</th>
                <th className="text-center py-3.5">Type</th>
                <th className="text-right py-3.5">Base Rate</th>
                <th className="text-center py-3.5">Curr</th>
                <th className="text-center py-3.5">Validity</th>
                <th className="pr-8 text-center py-3.5">Surcharges</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {paginatedRates.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-20 text-slate-400 font-medium">
                    No rate rows found matching filter criteria.
                  </td>
                </tr>
              ) : (
                paginatedRates.map((r, idx) => {
                  const actualIdx = startIndex + idx;
                  const isValid = r.validation_status === 'VALID';
                  const isWarn = r.validation_status === 'WARNING';

                  return (
                    <tr key={actualIdx} className="hover:bg-slate-50/70 transition-colors">
                      <td className="pl-8 py-3">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider inline-flex items-center gap-1 border ${
                          isValid ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                          isWarn ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-rose-50 text-rose-700 border-rose-200'
                        }`}>
                          {isValid && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                          {r.validation_status || 'VALID'}
                        </span>
                      </td>
                      <td className="py-3 font-mono font-black text-indigo-700">
                        {r.carrier_scac || 'MAEU'}
                      </td>
                      <td className="py-3">
                        <input
                          type="text"
                          value={r.origin_locode || ''}
                          onChange={(e) => handleCellChange(actualIdx, 'origin_locode', e.target.value)}
                          className="px-2 py-1 rounded bg-slate-50 border border-slate-200 font-mono text-xs font-black text-slate-900 w-24 focus:bg-white focus:border-[#00AFAF]"
                        />
                        <span className="text-[10px] text-slate-400 ml-1.5 truncate max-w-xs">{r.origin_raw}</span>
                      </td>
                      <td className="py-3">
                        <input
                          type="text"
                          value={r.destination_locode || ''}
                          onChange={(e) => handleCellChange(actualIdx, 'destination_locode', e.target.value)}
                          className="px-2 py-1 rounded bg-slate-50 border border-slate-200 font-mono text-xs font-black text-slate-900 w-24 focus:bg-white focus:border-[#00AFAF]"
                        />
                        <span className="text-[10px] text-slate-400 ml-1.5 truncate max-w-xs">{r.destination_raw}</span>
                      </td>
                      <td className="text-center py-3 font-mono font-bold text-slate-700">
                        {r.load_type || '20GP'}
                      </td>
                      <td className="text-right py-3 font-mono font-black text-slate-900">
                        <input
                          type="number"
                          value={r.base_rate ?? 0}
                          onChange={(e) => handleCellChange(actualIdx, 'base_rate', parseFloat(e.target.value) || 0)}
                          className="px-2 py-1 rounded bg-slate-50 border border-slate-200 font-mono text-xs font-black text-right text-slate-900 w-20 focus:bg-white focus:border-[#00AFAF]"
                        />
                      </td>
                      <td className="text-center py-3 font-mono text-slate-500 font-bold">
                        {r.currency || 'USD'}
                      </td>
                      <td className="text-center py-3 font-mono text-[10px] text-slate-500">
                        {r.validity_start ? `${r.validity_start} → ${r.validity_end || ''}` : <span className="text-amber-600 italic">Missing</span>}
                      </td>
                      <td className="pr-8 text-center py-3">
                        {(r.charges || []).length > 0 ? (
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono font-bold text-[10px] border border-slate-200">
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
      </div>

    </div>
  );
};
