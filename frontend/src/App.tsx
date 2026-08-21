import { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { JobQueue } from './pages/JobQueue';
import { RateReviewGrid } from './pages/RateReviewGrid';
import { HistoryPage } from './pages/History';
import { SettingsPage } from './pages/Settings';
import { BatchProcessingDock } from './components/BatchProcessingDock';
import { api } from './services/api';

export function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [masterDataStatus, setMasterDataStatus] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [exportPolicy, setExportPolicy] = useState('PARTIAL');

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
    loadData();
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [jobsData, mdData, metricsData] = await Promise.all([
        api.listJobs(30),
        api.getMasterData(),
        api.getMetrics(),
      ]);
      setJobs(jobsData || []);
      setMasterDataStatus(mdData || null);
      setMetrics(metricsData || null);
    } catch (err) {
      console.error('Error fetching data:', err);
    }
  };

  const handleSelectJob = (jobId: string) => {
    setSelectedJobId(jobId);
    setActiveTab('review');
  };

  const handleStartBatchProcessing = async (fileArray: File[], notes?: string) => {
    if (fileArray.length === 0) return;
    setBatchDockState({
      isOpen: true,
      files: fileArray,
      jobIds: [],
      activeIndex: 0,
    });

    const createdJobIds: string[] = [];
    for (let i = 0; i < fileArray.length; i++) {
      setBatchDockState((prev) => ({ ...prev, activeIndex: i }));
      try {
        const res = await api.uploadFile(fileArray[i], exportPolicy, notes);
        createdJobIds.push(res.job_id);
        setBatchDockState((prev) => ({ ...prev, jobIds: [...createdJobIds] }));
      } catch (err) {
        console.error(`Error uploading file ${fileArray[i].name}:`, err);
      }
    }
  };

  return (
    <div className="h-screen w-screen flex bg-[#f8fafc] text-slate-900 overflow-hidden">
      {/* Left Navigation Pane (Dark Sidebar) */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        masterDataStatus={masterDataStatus}
      />

      {/* Right Workspace Pane (Light Theme Workspace) */}
      <div className="flex-1 h-screen flex flex-col min-w-0 overflow-hidden bg-[#f8fafc]">
        <main className="flex-1 w-full flex flex-col min-h-0 overflow-y-auto custom-scrollbar p-6">
          {activeTab === 'dashboard' && (
            <Dashboard
              onJobCreated={handleSelectJob}
              recentJobs={jobs}
              metrics={metrics}
              exportPolicy={exportPolicy}
              setExportPolicy={setExportPolicy}
              onStartBatchProcessing={handleStartBatchProcessing}
            />
          )}
          {activeTab === 'queue' && <JobQueue jobs={jobs} onSelectJob={handleSelectJob} />}
          {activeTab === 'review' && <RateReviewGrid jobId={selectedJobId} onBackToDashboard={() => setActiveTab('dashboard')} />}
          {activeTab === 'history' && <HistoryPage jobs={jobs} onSelectJob={handleSelectJob} />}
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

      {/* Persistent Root Batch Processing Dock */}
      <BatchProcessingDock
        isOpen={batchDockState.isOpen}
        onClose={() => setBatchDockState((prev) => ({ ...prev, isOpen: false }))}
        files={batchDockState.files}
        jobIds={batchDockState.jobIds}
        activeIndex={batchDockState.activeIndex}
        onInspectJob={handleSelectJob}
      />
    </div>
  );
}

export default App;
