import axios from 'axios';

const API_BASE_URL = import.meta.env.PROD
  ? 'https://ratebridge-b6ephcg7anbfajdp.australiaeast-01.azurewebsites.net/api'
  : '/api';

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

// Resilient response interceptor that suppresses sleep/suspend noise
client.interceptors.response.use(
  (response) => response,
  (error) => {
    // If request was cancelled or suspended by OS sleep or tab backgrounding
    if (
      error?.code === 'ERR_NETWORK_IO_SUSPENDED' ||
      error?.message?.includes('ERR_NETWORK_IO_SUSPENDED') ||
      (typeof navigator !== 'undefined' && !navigator.onLine)
    ) {
      return Promise.reject({
        isSuspended: true,
        message: 'Network I/O suspended (device sleep or offline mode)',
      });
    }
    return Promise.reject(error);
  }
);

// Screen Wake Lock API to prevent device from sleeping during long multi-file rate batches
let activeWakeLock: any = null;

export const requestWakeLock = async () => {
  try {
    if ('wakeLock' in navigator && !activeWakeLock) {
      activeWakeLock = await (navigator as any).wakeLock.request('screen');
      activeWakeLock.addEventListener('release', () => {
        activeWakeLock = null;
      });
    }
  } catch {
    // Graceful fallback if unsupported or rejected by user settings
  }
};

export const releaseWakeLock = () => {
  try {
    if (activeWakeLock) {
      activeWakeLock.release().catch(() => {});
      activeWakeLock = null;
    }
  } catch {
    // Ignore
  }
};

export const api = {
  uploadFile: async (file: File, exportPolicy: string = 'PARTIAL', notes?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('export_policy', exportPolicy);
    if (notes && notes.trim()) {
      formData.append('notes', notes.trim());
    }

    const response = await client.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  uploadFilesBatch: async (files: File[], exportPolicy: string = 'PARTIAL', notes?: string) => {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    formData.append('export_policy', exportPolicy);
    if (notes && notes.trim()) {
      formData.append('notes', notes.trim());
    }

    const response = await client.post('/upload-batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  listJobs: async (limit: number = 30) => {
    const response = await client.get(`/jobs?limit=${limit}`);
    return response.data;
  },

  getJob: async (jobId: string) => {
    const response = await client.get(`/jobs/${jobId}`);
    return response.data;
  },

  getJobLogs: async (jobId: string) => {
    const response = await client.get(`/jobs/${jobId}/logs`);
    return response.data;
  },

  revalidateJob: async (jobId: string, rates: any[]) => {
    const response = await client.post(`/jobs/${jobId}/revalidate`, rates);
    return response.data;
  },

  approveJob: async (jobId: string, exportPolicy: string = 'PARTIAL') => {
    const response = await client.post(`/jobs/${jobId}/approve?export_policy=${exportPolicy}`);
    return response.data;
  },

  getDownloadUrl: (jobId: string) => {
    return `${API_BASE_URL}/jobs/${jobId}/download`;
  },

  downloadJobExport: async (jobId: string, customFilename?: string) => {
    const response = await client.get(`/jobs/${jobId}/download`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], {
      type: 'application/vnd.ms-excel.sheet.macroEnabled.12',
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = customFilename || `Freightify_Upload_${jobId}.xlsm`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  getMasterData: async () => {
    const response = await client.get('/master-data');
    return response.data;
  },

  reloadMasterData: async () => {
    const response = await client.post('/master-data/reload');
    return response.data;
  },

  getMetrics: async () => {
    const response = await client.get('/metrics');
    return response.data;
  },

  clearJobs: async () => {
    const response = await client.post('/jobs/clear');
    return response.data;
  },
  clearAllJobs: async () => {
    const response = await client.post('/jobs/clear');
    return response.data;
  },
};
