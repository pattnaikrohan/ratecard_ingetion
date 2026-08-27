import { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { AnalyticsDashboard } from './pages/AnalyticsDashboard';
import { IngestHub } from './pages/IngestHub';
import { JobQueue } from './pages/JobQueue';
import { RateReviewGrid } from './pages/RateReviewGrid';
import { HistoryPage } from './pages/History';
import { SettingsPage } from './pages/Settings';
import { BatchProcessingDock } from './components/BatchProcessingDock';
import { api } from './services/api';
import { Trash2, AlertTriangle, X } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [masterDataStatus, setMasterDataStatus] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [exportPolicy, setExportPolicy] = useState('PARTIAL');
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  // Persistent Batch Processing Dock State across all navigation tabs
  const [batchDockState, setBatchDockState] = useState<{
    isOpen: boolean;
    files: File[];
    jobIds: string[];
    activeIndex: number;
  }>({
    isOpen: false,
    files: [],
    jobIds: [],
    activeIndex: 0,
  });

  useEffect(() => {
    // Initial fetch for all data
    loadInitialData();

    // Periodic lightweight polling for jobs and metrics
    const interval = setInterval(() => {
      if (document.hidden) return; // Don't poll when tab is backgrounded
      loadPeriodicData();
    }, 4000);

    // Instant re-sync when computer wakes from sleep or network reconnects
    const handleDeviceWake = () => {
      if (!document.hidden && navigator.onLine) {
        loadPeriodicData();
      }
    };
    window.addEventListener('online', handleDeviceWake);
    document.addEventListener('visibilitychange', handleDeviceWake);

    return () => {
      clearInterval(interval);
      window.removeEventListener('online', handleDeviceWake);
      document.removeEventListener('visibilitychange', handleDeviceWake);
    };
  }, []);

  const loadInitialData = async (retryCount: number = 0) => {
    try {
      const [jobsData, mdData, metricsData] = await Promise.all([
        api.listJobs(40),
        api.getMasterData(),
        api.getMetrics(),
      ]);
      if (Array.isArray(jobsData)) {
        // Retry resilience: if backend returned 0 jobs but we previously had data,
        // the Azure backend may still be restoring from blob. Retry after a brief delay.
        const lastKnownCount = parseInt(sessionStorage.getItem('rb_last_job_count') || '0', 10);
        if (jobsData.length === 0 && lastKnownCount > 0 && retryCount < 2) {
          console.warn(`[RateBridge] Got 0 jobs but expected ~${lastKnownCount}. Retrying in 2s (attempt ${retryCount + 1}/2)...`);
          setTimeout(() => loadInitialData(retryCount + 1), 2000);
          return;
        }
        setJobs(jobsData);
        // Persist last known job count for retry detection across hard refreshes
        if (jobsData.length > 0) {
          sessionStorage.setItem('rb_last_job_count', String(jobsData.length));
        }
      }
      if (mdData) setMasterDataStatus(mdData);
      if (metricsData) setMetrics(metricsData);
    } catch (err) {
      console.error('Error fetching initial data:', err);
      // On network error during initial load, retry once after 3s
      if (retryCount < 2) {
        setTimeout(() => loadInitialData(retryCount + 1), 3000);
      }
    }
  };

  const loadPeriodicData = async () => {
    try {
      const [jobsData, metricsData] = await Promise.all([
        api.listJobs(40),
        api.getMetrics(),
      ]);
      if (Array.isArray(jobsData)) {
        setJobs((prevJobs) => {
          const prevKey = prevJobs.map((j) => `${j.job_id}:${j.status}:${j.progress}:${j.output_file_name}`).join('|');
          const nextKey = jobsData.map((j) => `${j.job_id}:${j.status}:${j.progress}:${j.output_file_name}`).join('|');
          return prevKey === nextKey ? prevJobs : jobsData;
        });
      }
      if (metricsData) setMetrics(metricsData);
    } catch (err) {
      console.error('Error fetching periodic data:', err);
    }
  };

  const loadData = async () => {
    await loadInitialData();
  };

  const handleSelectJob = (jobId: string) => {
    setSelectedJobId(jobId);
    setActiveTab('review');
  };

  const handleConfirmClearData = async () => {
    try {
      setIsClearing(true);
      await api.clearJobs();
      setJobs([]);
      setSelectedJobId(null);
      setBatchDockState({ isOpen: false, files: [], jobIds: [], activeIndex: 0 });
      await loadData();
      setIsClearModalOpen(false);
    } catch (err) {
      console.error('Error clearing data:', err);
    } finally {
      setIsClearing(false);
    }
  };

  const handleStartBatchProcessing = async (fileArray: File[], notes?: string) => {
    if (fileArray.length === 0) return;
    setBatchDockState({
      isOpen: true,
      files: fileArray,
      jobIds: new Array(fileArray.length).fill(''),
      activeIndex: 0,
    });

    for (let i = 0; i < fileArray.length; i++) {
      setBatchDockState((prev) => ({ ...prev, activeIndex: i }));
      try {
        const res = await api.uploadFile(fileArray[i], exportPolicy, notes);
        setBatchDockState((prev) => {
          const updated = [...prev.jobIds];
          updated[i] = res.job_id;
          return { ...prev, jobIds: updated };
        });
      } catch (err) {
        console.error(`Error uploading file ${fileArray[i].name}:`, err);
        setBatchDockState((prev) => {
          const updated = [...prev.jobIds];
          updated[i] = `failed_${Date.now()}`;
          return { ...prev, jobIds: updated };
        });
      }
    }
  };

  return (
    <div className="h-screen w-screen flex bg-[#f8fafc] text-slate-900 overflow-hidden font-sans antialiased">
      {/* Left Navigation Pane (Posh Light Sidebar) */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        masterDataStatus={masterDataStatus}
        onClearData={() => setIsClearModalOpen(true)}
      />

      {/* Right Workspace Pane (Smooth Native Scrolling Container) */}
      <div className="flex-1 h-screen min-w-0 overflow-y-auto overflow-x-hidden bg-[#f8fafc]">
        <main className="w-full min-h-full p-6 lg:p-8 pb-32">
          {activeTab === 'dashboard' && (
            <AnalyticsDashboard
              recentJobs={jobs}
              metrics={metrics}
              masterDataStatus={masterDataStatus}
              onSelectJob={handleSelectJob}
              onNavigateToIngest={() => setActiveTab('ingest')}
              onClearData={() => setIsClearModalOpen(true)}
            />
          )}

          {activeTab === 'ingest' && (
            <IngestHub
              onJobCreated={handleSelectJob}
              recentJobs={jobs}
              exportPolicy={exportPolicy}
              setExportPolicy={setExportPolicy}
              onStartBatchProcessing={handleStartBatchProcessing}
            />
          )}

          {activeTab === 'queue' && (
            <JobQueue
              jobs={jobs}
              onSelectJob={handleSelectJob}
            />
          )}

          {activeTab === 'review' && (
            <RateReviewGrid
              jobId={selectedJobId}
              jobs={jobs}
              onSelectJob={setSelectedJobId}
              onNavigateToIngest={() => setActiveTab('ingest')}
              onBackToDashboard={() => setActiveTab('dashboard')}
            />
          )}

          {activeTab === 'history' && (
            <HistoryPage
              jobs={jobs}
              onSelectJob={handleSelectJob}
            />
          )}

          {activeTab === 'settings' && (
            <SettingsPage
              exportPolicy={exportPolicy}
              setExportPolicy={setExportPolicy}
              masterDataStatus={masterDataStatus}
              onMasterDataReloaded={loadData}
            />
          )}
        </main>
      </div>

      {/* Persistent Ultra-Posh Batch Processing Dock */}
      <BatchProcessingDock
        isOpen={batchDockState.isOpen}
        onClose={() => setBatchDockState((prev) => ({ ...prev, isOpen: false }))}
        files={batchDockState.files}
        jobIds={batchDockState.jobIds}
        activeIndex={batchDockState.activeIndex}
        onInspectJob={handleSelectJob}
      />

      {/* Clear Data Confirmation Modal */}
      {isClearModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200/90 relative animate-in zoom-in-95 duration-200">
            <button
              onClick={() => setIsClearModalOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 p-2 rounded-xl hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3.5 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-rose-50 border border-rose-100 flex items-center justify-center shrink-0">
                <Trash2 className="w-6 h-6 text-rose-600" />
              </div>
              <div>
                <h3 className="text-base font-black text-slate-900">Clear Ingested Data</h3>
                <p className="text-xs text-slate-500 font-medium">Persistent Database Reset</p>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-amber-50/80 border border-amber-200/80 mb-6 text-xs text-amber-800 space-y-1.5">
              <div className="flex items-center gap-1.5 font-bold text-amber-900">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>Permanent Action</span>
              </div>
              <p>
                This will wipe all rate cards, extracted rows, metrics telemetry, and SQLite/Azure Blob records.
                Your data remains permanently persistent across page refreshes until you click this button.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setIsClearModalOpen(false)}
                disabled={isClearing}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmClearData}
                disabled={isClearing}
                className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-black shadow-lg shadow-rose-600/20 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isClearing ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Wiping Database...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    <span>Wipe & Reset Everything</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
