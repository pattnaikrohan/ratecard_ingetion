import React, { useState, useEffect } from 'react';
import { Download, RefreshCw, Search, Filter, ArrowLeft, CheckCircle2, Cpu, AlertCircle } from 'lucide-react';
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



  useEffect(() => {
    if (!jobId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    let isSubscribed = true;

    const fetchJob = async () => {
      try {
        const data = await api.getJob(jobId);
        if (!isSubscribed) return;

        setJobData(data);
        setIsLoading(false);

        // Only overwrite local rates if initial load or if actively processing
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
        if (isSubscribed) setIsLoading(false);
      }
    };

    fetchJob();

    // Poll ONLY while worker is actively processing
    const interval = setInterval(() => {
      if (!jobData || ['QUEUED', 'PARSING', 'NORMALIZING', 'VALIDATING'].includes(jobData?.status)) {
        fetchJob();
      }
    }, 1000);

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
      // Save & re-validate any user-typed modifications first
      await api.revalidateJob(jobId, rates);
      await api.approveJob(jobId, 'PARTIAL');
      const downloadUrl = api.getDownloadUrl(jobId);
      window.open(downloadUrl, '_blank');
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
      <div className="card-elevated p-12 text-center space-y-4">
        <h3 className="text-xl font-bold text-slate-900">No Job Selected for Review</h3>
        <p className="text-sm text-slate-500 font-medium">Please select an ingestion job from the Dashboard or Processing Queue to inspect.</p>
        <button onClick={onBackToDashboard} className="btn-shiny-indigo">
          <ArrowLeft className="w-4 h-4" /> Return to Dashboard
        </button>
      </div>
    );
  }

  const isWorkerProcessing = (jobData && ['QUEUED', 'PARSING', 'NORMALIZING', 'VALIDATING'].includes(jobData.status)) || (isLoading && !jobData);
  const isFailed = jobData?.status === 'FAILED';

  const filteredRates = rates.filter((r) => {
    const matchesSearch =
      (r.origin_locode || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.destination_locode || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.carrier_scac || '').toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = statusFilter === 'ALL' || r.validation_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const summary = jobData?.summary || {};

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <button onClick={onBackToDashboard} className="text-xs text-indigo-600 hover:text-indigo-800 flex items-center gap-1 font-bold mb-1">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
          </button>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-black text-slate-900">Rate Review & Master Data Alignment</h2>
            <span className="badge-pill badge-valid text-[10px]">{jobData?.file_name || 'Loading...'}</span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleRevalidate}
            disabled={isRevalidating || isWorkerProcessing || rates.length === 0}
            className="btn-outline text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRevalidating ? 'animate-spin' : ''}`} />
            Re-Validate Rows
          </button>

          <button
            onClick={handleApproveAndDownload}
            disabled={isApproving || isWorkerProcessing || rates.length === 0}
            className="btn-shiny-emerald text-xs"
          >
            <Download className="w-4 h-4" />
            {isApproving ? 'Generating .xlsm...' : 'Export Freightify Upload Sheet (.xlsm)'}
          </button>
        </div>
      </div>

      {/* Processing Loader Banner */}
      {isWorkerProcessing && (
        <div className="bg-indigo-900 text-white rounded-2xl p-5 border border-indigo-700 shadow-xl flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Cpu className="w-6 h-6 text-sky-400 animate-spin shrink-0" />
            <div>
              <p className="text-sm font-extrabold text-white">Carrier Parsing & Master Data Validation Engine Active...</p>
              <p className="text-xs text-slate-300 font-medium">Extracting rate matrix, unpivoting container types, and checking 13,670 UNLOCODEs ({jobData?.progress || 40}% complete)</p>
            </div>
          </div>
          <div className="w-48 h-2 bg-indigo-950 rounded-full overflow-hidden shrink-0">
            <div className="h-full bg-sky-400 transition-all duration-300" style={{ width: `${jobData?.progress || 40}%` }} />
          </div>
        </div>
      )}

      {/* Error Banner if Job Failed */}
      {isFailed && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-2xl p-5 shadow-sm space-y-2">
          <div className="flex items-center gap-2 text-red-700 font-bold text-sm">
            <AlertCircle className="w-5 h-5" /> Parsing Failed for {jobData?.file_name}
          </div>
          <p className="text-xs text-red-600 font-mono">
            {jobData?.logs?.length > 0 ? jobData.logs[jobData.logs.length - 1] : 'Extraction error encountered.'}
          </p>
        </div>
      )}

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="card-elevated p-3.5 text-center">
          <p className="text-[10px] text-slate-400 uppercase font-extrabold">Total Rates</p>
          <p className="text-lg font-black text-slate-900 mt-0.5">{summary.total_rows || rates.length}</p>
        </div>
        <div className="card-elevated p-3.5 text-center">
          <p className="text-[10px] text-emerald-600 uppercase font-extrabold">Valid Rows</p>
          <p className="text-lg font-black text-emerald-600 mt-0.5">{summary.valid_rows || 0}</p>
        </div>
        <div className="card-elevated p-3.5 text-center">
          <p className="text-[10px] text-amber-600 uppercase font-extrabold">Warnings</p>
          <p className="text-lg font-black text-amber-600 mt-0.5">{summary.warning_rows || 0}</p>
        </div>
        <div className="card-elevated p-3.5 text-center">
          <p className="text-[10px] text-rose-600 uppercase font-extrabold">Errors</p>
          <p className="text-lg font-black text-rose-600 mt-0.5">{summary.error_rows || 0}</p>
        </div>
        <div className="card-elevated p-3.5 text-center">
          <p className="text-[10px] text-sky-600 uppercase font-extrabold">Processing Speed</p>
          <p className="text-lg font-black text-sky-600 mt-0.5">{summary.processing_time_ms ? `${summary.processing_time_ms} ms` : '—'}</p>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="card-elevated p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 px-3.5 py-2 rounded-xl w-80">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Filter LOCODE, city, or SCAC..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="bg-transparent border-none text-xs text-slate-900 placeholder-slate-400 focus:outline-none w-full font-bold"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs text-slate-500 font-extrabold">Status Filter:</span>
          {['ALL', 'VALID', 'WARNING', 'ERROR', 'CRITICAL'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                statusFilter === st ? 'bg-indigo-600 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Interactive HITL Data Review Table */}
      <div className="card-elevated overflow-hidden border border-slate-200">
        <div className="max-h-[580px] overflow-y-auto overflow-x-auto">
          <table className="custom-table min-w-[1550px] align-middle">
            <thead>
              <tr>
                <th className="min-w-[100px] text-center">Status</th>
                <th className="min-w-[110px] text-center">SCAC</th>
                <th className="min-w-[240px] text-left">Origin Port (LOCODE)</th>
                <th className="min-w-[240px] text-left">Destination Port (LOCODE)</th>
                <th className="min-w-[130px] text-center">Load Type</th>
                <th className="min-w-[140px] text-right">OFR Amount</th>
                <th className="min-w-[100px] text-center">Currency</th>
                <th className="min-w-[250px] text-center">Validity Window</th>
                <th className="min-w-[140px] text-center">Contract No</th>
                <th className="min-w-[280px] text-left">Validation Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rates.length === 0 ? (
                <tr>
                  <td colSpan={10} className="text-center py-16 text-slate-400 text-xs font-medium">
                    {isWorkerProcessing ? (
                      <div className="flex flex-col items-center justify-center gap-3">
                        <Cpu className="w-8 h-8 text-indigo-600 animate-spin" />
                        <div>
                          <p className="text-sm font-bold text-slate-800">Carrier Parsing & Master Data Engine Active...</p>
                          <p className="text-xs text-slate-400 mt-0.5">Unpivoting rate matrix & checking 13,670 UNLOCODEs ({jobData?.progress || 40}% complete)</p>
                        </div>
                      </div>
                    ) : isFailed ? (
                      <div className="flex flex-col items-center justify-center gap-2 text-rose-600">
                        <AlertCircle className="w-8 h-8 text-rose-500" />
                        <p className="text-sm font-bold">File Parsing Failed</p>
                        <p className="text-xs text-rose-500 font-mono max-w-md text-center">
                          {jobData?.logs?.length > 0 ? jobData.logs[jobData.logs.length - 1] : 'Extraction error encountered.'}
                        </p>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center gap-2 text-slate-400">
                        <AlertCircle className="w-8 h-8 text-slate-300" />
                        <p className="text-sm font-bold text-slate-700">No Rate Rows Extracted</p>
                        <p className="text-xs text-slate-400">No valid rate rows were found in this rate card file.</p>
                      </div>
                    )}
                  </td>
                </tr>
              ) : filteredRates.length === 0 ? (
                <tr>
                  <td colSpan={10} className="text-center py-12 text-slate-400 text-xs font-medium">
                    No rate rows matching the selected search/status filter.
                  </td>
                </tr>
              ) : (
                filteredRates.map((row, filterIdx) => {
                  const actualIdx = rates.indexOf(row);
                  const targetIdx = actualIdx !== -1 ? actualIdx : filterIdx;
                  const errorItems = (row.validation_items || []).filter((v: any) => v.severity === 'ERROR' || v.severity === 'CRITICAL');
                  const warningItems = (row.validation_items || []).filter((v: any) => v.severity === 'WARNING');

                  return (
                    <tr key={filterIdx} className={`h-12 hover:bg-slate-50/80 transition-colors ${row.validation_status === 'ERROR' ? 'bg-rose-50/50' : ''}`}>
                      <td className="align-middle text-center py-2 px-3">
                        <span className={`badge-pill ${
                          row.validation_status === 'VALID' ? 'badge-valid' :
                          row.validation_status === 'WARNING' ? 'badge-warning' :
                          row.validation_status === 'ERROR' ? 'badge-error' : 'badge-critical'
                        }`}>
                          {row.validation_status}
                        </span>
                      </td>
                      <td className="align-middle text-center py-2 px-3">
                        <input
                          type="text"
                          value={row.carrier_scac}
                          onChange={(e) => handleCellChange(targetIdx, 'carrier_scac', e.target.value)}
                          className="table-cell-input text-xs font-mono font-extrabold h-9 text-indigo-700 text-center w-full min-w-[80px]"
                        />
                      </td>
                      <td className="align-middle py-2 px-3">
                        <div className="flex items-center gap-1.5 h-9 bg-white border border-slate-300 rounded-lg px-2.5 shadow-2xs focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100 min-w-[220px]">
                          <input
                            type="text"
                            value={row.origin_locode}
                            placeholder="Type UNLOCODE or city..."
                            onChange={(e) => {
                              handleCellChange(targetIdx, 'origin_locode', e.target.value.toUpperCase());
                              handleCellChange(targetIdx, 'origin_raw', e.target.value);
                            }}
                            className="bg-transparent border-none text-xs font-mono font-extrabold text-indigo-700 w-full focus:outline-none placeholder:text-slate-300"
                          />
                          {row.origin_name && (
                            <span className="text-[11px] text-slate-400 font-medium truncate border-l border-slate-200 pl-2 shrink-0 max-w-[110px]">
                              {row.origin_name}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="align-middle py-2 px-3">
                        <div className="flex items-center gap-1.5 h-9 bg-white border border-slate-300 rounded-lg px-2.5 shadow-2xs focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-100 min-w-[220px]">
                          <input
                            type="text"
                            value={row.destination_locode}
                            placeholder="Type UNLOCODE or city..."
                            onChange={(e) => {
                              handleCellChange(targetIdx, 'destination_locode', e.target.value.toUpperCase());
                              handleCellChange(targetIdx, 'destination_raw', e.target.value);
                            }}
                            className="bg-transparent border-none text-xs font-mono font-extrabold text-indigo-700 w-full focus:outline-none placeholder:text-slate-300"
                          />
                          {row.destination_name && (
                            <span className="text-[11px] text-slate-400 font-medium truncate border-l border-slate-200 pl-2 shrink-0 max-w-[110px]">
                              {row.destination_name}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="align-middle text-center py-2 px-3">
                        <select
                          value={row.load_type}
                          onChange={(e) => handleCellChange(targetIdx, 'load_type', e.target.value)}
                          className="select-clean text-xs h-9 font-bold cursor-pointer text-center w-full min-w-[100px]"
                        >
                          {['20GP', '40GP', '40HC', '45GP', '45HC', '20DG', '40DG', '45DG', '20RF', '40RF', '20NOR', '40NOR', '20FR', '40FR', '20OT', '40OT', '20TK', 'LCL'].map((lt) => (
                            <option key={lt} value={lt}>{lt}</option>
                          ))}
                        </select>
                      </td>
                      <td className="align-middle text-right py-2 px-3">
                        <input
                          type="number"
                          value={row.ofr_amount}
                          onChange={(e) => handleCellChange(targetIdx, 'ofr_amount', parseFloat(e.target.value) || 0)}
                          className="table-cell-input text-xs font-mono h-9 text-emerald-600 font-black text-right w-full min-w-[100px] px-3"
                        />
                      </td>
                      <td className="align-middle text-center py-2 px-3">
                        <input
                          type="text"
                          value={row.ofr_currency || 'USD'}
                          onChange={(e) => handleCellChange(targetIdx, 'ofr_currency', e.target.value.toUpperCase())}
                          className="table-cell-input text-xs font-mono font-bold h-9 text-slate-700 text-center w-full min-w-[70px]"
                        />
                      </td>
                      <td className="align-middle text-center py-2 px-3">
                        <div className="flex items-center gap-1 min-w-[220px]">
                          <input
                            type="text"
                            value={row.validity_start || ''}
                            placeholder="YYYY-MM-DD"
                            onChange={(e) => handleCellChange(targetIdx, 'validity_start', e.target.value)}
                            className="table-cell-input text-[11px] font-mono font-bold h-9 text-slate-800 text-center w-full"
                          />
                          <span className="text-indigo-500 font-extrabold shrink-0">→</span>
                          <input
                            type="text"
                            value={row.validity_end || ''}
                            placeholder="YYYY-MM-DD"
                            onChange={(e) => handleCellChange(targetIdx, 'validity_end', e.target.value)}
                            className="table-cell-input text-[11px] font-mono font-bold h-9 text-slate-800 text-center w-full"
                          />
                        </div>
                      </td>
                      <td className="align-middle text-center py-2 px-3">
                        <input
                          type="text"
                          value={row.contract_number || ''}
                          placeholder="Contract #"
                          onChange={(e) => handleCellChange(targetIdx, 'contract_number', e.target.value)}
                          className="table-cell-input text-xs font-mono font-semibold h-9 text-slate-700 text-center w-full min-w-[110px]"
                        />
                      </td>
                      <td className="align-middle py-2 px-3">
                        <div className="h-9 flex items-center text-xs text-slate-600 font-medium min-w-[260px]">
                          {errorItems.length > 0 ? (
                            <div className="truncate text-rose-600 font-bold">
                              • {errorItems[0].message}
                            </div>
                          ) : warningItems.length > 0 ? (
                            <div className="truncate text-amber-700 font-bold">
                              • {warningItems[0].message}
                            </div>
                          ) : (
                            <span className="text-emerald-600 font-bold flex items-center gap-1.5">
                              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" /> Validated against 13,670 LOCODEs
                            </span>
                          )}
                        </div>
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
