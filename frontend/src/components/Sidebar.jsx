import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import { getDatasets, uploadDataset, processDataset, extractZone, getDatasetTiles, getCropPreviewUrl } from '../api';
import { useLidarStore } from '../store/useLidarStore';
import { Layers, Database, Upload, RefreshCw, X, Loader2, Download, Eye, AlertTriangle } from 'lucide-react';

export default function Sidebar() {
  const queryClient = useQueryClient();
  const { selectedDataset, setSelectedDataset, zFilters, setZFilters, clearZFilters, boundingBox, clearBoundingBox } = useLidarStore();
  
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadingFile, setUploadingFile] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [preparingPreview, setPreparingPreview] = useState(false);
  const [extractError, setExtractError] = useState('');
  
  // --- Data Fetching ---
  const { data: response, isLoading, isError } = useQuery({
    queryKey: ['datasets'],
    queryFn: async () => {
      const res = await getDatasets();
      return res.data;
    },
    refetchInterval: 10000,
  });

  // --- Upload Mutation ---
  const uploadMutation = useMutation({
    mutationFn: async (file) => {
      const datasetName = file.name.replace(/\.[^/.]+$/, "");
      return uploadDataset(datasetName, file, (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        setUploadProgress(percentCompleted);
      });
    },
    onSuccess: (res) => {
      // Trigger processing right after upload
      processMutation.mutate(res.data.dataset_id);
    },
    onSettled: () => {
      setUploadingFile(null);
      setUploadProgress(0);
    }
  });

  // --- Process Mutation ---
  const processMutation = useMutation({
    mutationFn: (datasetId) => processDataset(datasetId, 0),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    }
  });

  // --- Drag & Drop ---
  const onDrop = useCallback(acceptedFiles => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      setUploadingFile(file);
      setUploadProgress(0);
      uploadMutation.mutate(file);
    }
  }, [uploadMutation]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/octet-stream': ['.laz', '.las'] },
    multiple: false
  });

  // --- Extract Zone Handler ---
  const handleExtract = async () => {
    if (!boundingBox) return;
    setExtracting(true);
    setExtractError('');
    try {
      await extractZone(
        boundingBox.west,
        boundingBox.south,
        boundingBox.east,
        boundingBox.north,
      );
    } catch (err) {
      console.error('Extraction failed:', err);
      const message = err.response?.status === 404
        ? 'No data found in the selected area.'
        : 'Extraction failed. Please try again.';
      setExtractError(message);
    } finally {
      setExtracting(false);
    }
  };

  const datasets = response?.datasets || [];

  return (
    <div className="flex flex-col h-full bg-[#141418] p-5 text-white">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6 border-b border-gray-800 pb-5">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Layers size={20} className="text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight">LiDAR Manager</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-widest">Point Cloud Dashboard</p>
        </div>
      </div>

      {/* Upload Zone */}
      <div 
        {...getRootProps()} 
        className={`relative border-2 border-dashed rounded-2xl p-5 mb-6 text-center cursor-pointer transition-all duration-300 ${
          isDragActive 
            ? 'border-blue-400 bg-blue-500/10 shadow-lg shadow-blue-500/10' 
            : 'border-gray-700/50 hover:border-gray-600 hover:bg-gray-800/30'
        }`}
      >
        <input {...getInputProps()} />
        {uploadingFile ? (
          <div className="space-y-3">
            <div className="w-12 h-12 mx-auto rounded-full bg-blue-500/20 flex items-center justify-center">
              <Loader2 className="animate-spin text-blue-400" size={24} />
            </div>
            <p className="text-sm font-medium truncate px-2">{uploadingFile.name}</p>
            <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
              <div className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full rounded-full transition-all duration-300" style={{ width: `${uploadProgress}%` }}></div>
            </div>
            <p className="text-xs text-gray-500">{uploadProgress}%</p>
          </div>
        ) : (
          <div className="space-y-2">
            <div className={`w-12 h-12 mx-auto rounded-full flex items-center justify-center transition-colors ${isDragActive ? 'bg-blue-500/20' : 'bg-gray-800'}`}>
              <Upload className={isDragActive ? 'text-blue-400' : 'text-gray-500'} size={22} />
            </div>
            <p className="text-sm font-medium">Drop LAZ/LAS file here</p>
            <p className="text-xs text-gray-500">or click to browse</p>
          </div>
        )}
      </div>

      {/* Dataset List */}
      <div className="flex-1 overflow-y-auto mb-4 scrollbar-thin">
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-[11px] font-semibold text-gray-500 uppercase tracking-widest">
            Datasets
          </h2>
          <button 
            onClick={() => queryClient.invalidateQueries({ queryKey: ['datasets'] })} 
            className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
          >
            <RefreshCw size={14} />
          </button>
        </div>

        {isLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 rounded-xl bg-gray-800/30 animate-pulse" />
            ))}
          </div>
        )}
        {isError && (
          <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20">
            <p className="text-xs text-red-400 text-center">Error loading datasets</p>
          </div>
        )}

        <div className="space-y-2">
          {datasets.map((ds) => (
            <div 
              key={ds.id} 
              onClick={() => setSelectedDataset(ds)}
              className={`group p-4 rounded-xl cursor-pointer transition-all duration-200 border ${
                selectedDataset?.id === ds.id 
                  ? 'bg-gradient-to-br from-blue-500/15 to-indigo-500/15 border-blue-500/50 shadow-lg shadow-blue-500/10' 
                  : 'bg-gray-800/30 border-gray-800 hover:bg-gray-800/60 hover:border-gray-700'
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                  ds.status === 'processed' || ds.status === 'completed' 
                    ? 'bg-green-500/20' 
                    : 'bg-yellow-500/20'
                }`}>
                  <Database size={16} className={
                    ds.status === 'processed' || ds.status === 'completed' ? 'text-green-400' : 'text-yellow-400'
                  } />
                </div>
                <h3 className="font-medium text-sm truncate flex-1">{ds.dataset_name}</h3>
              </div>
              <div className="flex items-center gap-2 text-[11px] text-gray-500">
                <span>{ds.point_count ? `${(ds.point_count / 1000000).toFixed(2)}M pts` : 'Pending'}</span>
                <span className="w-1 h-1 rounded-full bg-gray-600" />
                <span className={
                  ds.status === 'completed' || ds.status === 'processed'
                    ? 'text-green-400' 
                    : ds.status === 'processing' ? 'text-blue-400' : 'text-yellow-400'
                }>
                  {ds.status}
                </span>
              </div>
            </div>
          ))}
          {!isLoading && datasets.length === 0 && (
            <div className="text-center py-8">
              <Database size={32} className="mx-auto text-gray-700 mb-2" />
              <p className="text-xs text-gray-500">No datasets available</p>
            </div>
          )}
        </div>
      </div>

      {/* Zone Tools Panel */}
      {selectedDataset && (
        <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/80 backdrop-blur-sm rounded-2xl p-4 border border-gray-700/50 shadow-xl">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-indigo-500/20 flex items-center justify-center">
                <Layers size={14} className="text-indigo-400" />
              </div>
              <h3 className="font-semibold text-sm">Zone Tools</h3>
            </div>
            <button 
              onClick={() => { setSelectedDataset(null); clearBoundingBox(); setExtractError(''); }} 
              className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-500 hover:text-gray-300 transition-colors"
            >
              <X size={14} />
            </button>
          </div>

          {/* Elevation Filters */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Min Z</label>
              <input 
                type="number" 
                value={zFilters.min || ''}
                onChange={(e) => setZFilters({ min: e.target.value })}
                className="w-full bg-gray-900/70 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 focus:outline-none transition-all"
                placeholder="No limit"
              />
            </div>
            <div>
              <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Max Z</label>
              <input 
                type="number" 
                value={zFilters.max || ''}
                onChange={(e) => setZFilters({ max: e.target.value })}
                className="w-full bg-gray-900/70 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 focus:outline-none transition-all"
                placeholder="No limit"
              />
            </div>
          </div>

          {/* Bounding Box Info */}
          {boundingBox && (
            <div className="bg-gray-900/60 rounded-xl p-3 mb-4 border border-gray-700/30">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2 font-medium">Selected Region</p>
              <p className="text-xs font-mono text-green-400/80 leading-relaxed">
                {boundingBox.south.toFixed(4)}°, {boundingBox.west.toFixed(4)}°
                <span className="mx-2 text-gray-600">→</span>
                {boundingBox.north.toFixed(4)}°, {boundingBox.east.toFixed(4)}°
              </p>
            </div>
          )}

          {/* Error Message */}
          {extractError && (
            <div className="flex items-center gap-2 mb-4 p-2.5 rounded-xl bg-red-500/10 border border-red-500/20">
              <AlertTriangle size={14} className="text-red-400 flex-shrink-0" />
              <p className="text-xs text-red-400">{extractError}</p>
            </div>
          )}

          {/* Action Buttons */}
          {boundingBox ? (
            <div className="space-y-2">
              <button 
                onClick={handleExtract}
                disabled={extracting}
                className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 rounded-xl text-sm transition-all duration-200 flex justify-center items-center gap-2 shadow-lg shadow-blue-500/20"
              >
                {extracting ? (
                  <><Loader2 size={14} className="animate-spin" /> Extracting...</>
                ) : (
                  <><Download size={14} /> Extract Subset</>
                )}
              </button>
              <button 
                onClick={async () => {
                  if (!selectedDataset?.id || !boundingBox) return;
                  setPreparingPreview(true);
                  try {
                    const res = await getCropPreviewUrl(boundingBox);
                    const url = res.data.url;
                    window.open(
                      `/viewer?urls=${encodeURIComponent(JSON.stringify([url]))}`,
                      '_blank'
                    );
                  } catch (err) {
                    console.error('Failed to prepare preview:', err);
                    setExtractError('Failed to prepare 3D preview.');
                  } finally {
                    setPreparingPreview(false);
                  }
                }}
                disabled={preparingPreview}
                className="w-full bg-gray-700/70 hover:bg-gray-600 disabled:opacity-50 text-white font-medium py-2 px-4 rounded-xl text-sm transition-all duration-200 flex justify-center items-center gap-2"
              >
                {preparingPreview ? (
                  <><Loader2 size={14} className="animate-spin" /> Preparing...</>
                ) : (
                  <><Eye size={14} /> View 3D Preview</>
                )}
              </button>
              <button 
                onClick={() => { clearBoundingBox(); setExtractError(''); }}
                className="w-full text-gray-500 hover:text-gray-300 font-medium py-1.5 px-4 rounded-xl text-xs transition-colors"
              >
                Clear Selection
              </button>
            </div>
          ) : (
            <div className="text-center py-4 border border-dashed border-gray-700/50 rounded-xl bg-gray-800/20">
              <p className="text-xs text-gray-500">Draw a rectangle on the map</p>
              <p className="text-[10px] text-gray-600">to extract a zone</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}