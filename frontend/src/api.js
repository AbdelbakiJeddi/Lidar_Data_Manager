import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'auth_token';

const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem(TOKEN_KEY);
    }
    return Promise.reject(error);
  }
);

export const setToken = (token) => {
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_KEY);
  }
};

export const getToken = () => sessionStorage.getItem(TOKEN_KEY);

export const decodeTokenPayload = (token) => {
  if (!token) return null;
  try {
    const payloadPart = token.split('.')[1];
    if (!payloadPart) return null;
    const json = atob(payloadPart.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch (error) {
    return null;
  }
};

export const login = (username, password) => api.post('/auth/login', { username, password });
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
