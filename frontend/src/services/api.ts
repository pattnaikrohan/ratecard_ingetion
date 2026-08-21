import axios from 'axios';

const API_BASE_URL = import.meta.env.PROD
  ? 'https://ratebridge-b6ephcg7anbfajdp.australiaeast-01.azurewebsites.net/api'
  : '/api';

export const api = {
  uploadFile: async (file: File, exportPolicy: string = 'PARTIAL', notes?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('export_policy', exportPolicy);
    if (notes && notes.trim()) {
      formData.append('notes', notes.trim());
    }

    const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
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

    const response = await axios.post(`${API_BASE_URL}/upload-batch`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  listJobs: async (limit: number = 30) => {
    const response = await axios.get(`${API_BASE_URL}/jobs?limit=${limit}`);
    return response.data;
  },

  getJob: async (jobId: string) => {
    const response = await axios.get(`${API_BASE_URL}/jobs/${jobId}`);
    return response.data;
  },

  getJobLogs: async (jobId: string) => {
    const response = await axios.get(`${API_BASE_URL}/jobs/${jobId}/logs`);
    return response.data;
  },

  revalidateJob: async (jobId: string, rates: any[]) => {
    const response = await axios.post(`${API_BASE_URL}/jobs/${jobId}/revalidate`, rates);
    return response.data;
  },

  approveJob: async (jobId: string, exportPolicy: string = 'PARTIAL') => {
    const response = await axios.post(`${API_BASE_URL}/jobs/${jobId}/approve?export_policy=${exportPolicy}`);
    return response.data;
  },

  getDownloadUrl: (jobId: string) => {
    return `${API_BASE_URL}/jobs/${jobId}/download`;
  },

  downloadJobExport: async (jobId: string, customFilename?: string) => {
    const response = await axios.get(`${API_BASE_URL}/jobs/${jobId}/download`, {
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
    const response = await axios.get(`${API_BASE_URL}/master-data`);
    return response.data;
  },

  reloadMasterData: async () => {
    const response = await axios.post(`${API_BASE_URL}/master-data/reload`);
    return response.data;
  },

  getMetrics: async () => {
    const response = await axios.get(`${API_BASE_URL}/metrics`);
    return response.data;
  },

  clearJobs: async () => {
    const response = await axios.post(`${API_BASE_URL}/jobs/clear`);
    return response.data;
  },
  clearAllJobs: async () => {
    const response = await axios.post(`${API_BASE_URL}/jobs/clear`);
    return response.data;
  },
};
