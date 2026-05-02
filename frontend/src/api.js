import axios from 'axios';

const API_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
});

export const getDatasets = () => api.get('/lidar/datasets');

export const uploadDataset = (datasetName, file, onUploadProgress) => {
  const formData = new FormData();
  formData.append('dataset_name', datasetName);
  formData.append('file', file);
  
  return api.post('/lidar/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress,
  });
};

export const processDataset = (datasetId, maxDepth = 8, pointThreshold = 5000000) => {
  return api.post(`/lidar/process/${datasetId}`, {
    max_depth: maxDepth,
    point_threshold: pointThreshold,
  });
};

export const downloadZone = async (datasetId, bbox) => {
  const response = await api.post(`/lidar/nodes/${datasetId}/zone`, bbox, {
    responseType: 'blob', // Important for downloading files
  });
  
  // Create a link to download the blob
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `zone_${datasetId}.laz`);
  document.body.appendChild(link);
  link.click();
  link.parentNode.removeChild(link);
  window.URL.revokeObjectURL(url);
};

export default api;
