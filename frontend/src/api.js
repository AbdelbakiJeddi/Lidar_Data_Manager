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

export const processDataset = (datasetId, tileSizeMeters = 0) => {
  return api.post(`/lidar/process/${datasetId}`, {
    tile_size_meters: tileSizeMeters,
  });
};

export const extractZone = async (minLon, minLat, maxLon, maxLat) => {
  const response = await api.post('/lidar/tiles/extract-zone', {
    min_lon: minLon,
    min_lat: minLat,
    max_lon: maxLon,
    max_lat: maxLat,
  }, {
    responseType: 'blob',
  });

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', 'zone_extraction.laz');
  document.body.appendChild(link);
  link.click();
  link.parentNode.removeChild(link);
  window.URL.revokeObjectURL(url);
};

export default api;
