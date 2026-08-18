import axios from 'axios';

const API_BASE_URL = '/api';

export const api = {
  uploadFile: async (file: File, exportPolicy: string = 'PARTIAL') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('export_policy', exportPolicy);

    const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  uploadFilesBatch: async (files: File[], exportPolicy: string = 'PARTIAL') => {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    formData.append('export_policy', exportPolicy);

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
};
